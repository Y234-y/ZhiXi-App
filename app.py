import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import json
import re
import requests
from io import StringIO

from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_chat
from report_utils import generate_word_report
from predict_utils import create_forecast_chart
from agent_utils import execute_ai_code

# 1. 页面配置与 CSS
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    .stApp { background: radial-gradient(circle at 15% 50%, rgba(0, 75, 135, 0.04) 0%, transparent 50%), radial-gradient(circle at 85% 30%, rgba(95, 158, 160, 0.06) 0%, transparent 50%), #f8fafc; }
    header {visibility: hidden;}
    [data-testid="stFileUploader"] > div { border: 2px dashed #94a3b8 !important; border-radius: 12px !important; background: rgba(255,255,255,0.6) !important; }
</style>
""", unsafe_allow_html=True)

# 文本净化函数 (用于Word导出)
def clean_text_for_word(text):
    if not text: return "暂无分析内容"
    text = re.sub(r'#+\s', '', text).replace('**', '').replace('|', ' ')
    return re.sub(r'\n+', '\n', text)

# 2. 状态初始化与 Key
if "use_demo" not in st.session_state: st.session_state.use_demo = False
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "auto_charts" not in st.session_state: st.session_state.auto_charts = []
if "pred_chart" not in st.session_state: st.session_state.pred_chart = None

try: api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception: api_key = ""
model_name = "deepseek-chat"

# 3. 数据读取逻辑
df = None
has_data = st.session_state.use_demo
if has_data:
    try:
        if st.session_state.get("demo_type") == "电商":
            np.random.seed(42)
            days = pd.date_range("2024-01-01", periods=90, freq="D")
            df_raw = pd.DataFrame({"日期": days.astype(str), "类目": np.random.choice(["女装", "数码"], 90), "销售额": np.random.randint(1000, 10000, 90)})
        elif st.session_state.get("demo_type") == "成绩":
            df_raw = pd.DataFrame({"班级": np.random.choice(["一班", "二班"], 50), "语文": np.random.randint(60, 100, 50), "数学": np.random.randint(50, 100, 50)})
        else:
            df_raw = st.session_state.get("user_df", pd.DataFrame())

        if not df_raw.empty:
            df = clean_dataframe(df_raw, strip_space=True, na_strategy="不处理", drop_outliers=False)
            col_types = analyze_columns(df)
            df = force_convert_numeric(df, col_types)
            st.session_state.auto_charts = auto_recommend_charts(df, col_types)
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        st.session_state.use_demo = False
# ==========================================
# 4. 渲染：纯居中极简首页
# ==========================================
if not has_data:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #004b87; font-size: 3.5rem; font-weight: 800;'>智析 DataSight</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; font-size: 1.1rem; margin-bottom: 3rem;'>请在下方上传数据，开启您的 AI 数据之旅。</p >", unsafe_allow_html=True)
    
    c_empty1, c_center, c_empty2 = st.columns([1, 2, 1])
    with c_center:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center; color: #004b87;'>📂 拖拽或点击上传数据</h4>", unsafe_allow_html=True)
            uploaded_files = st.file_uploader("上传", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            
            if uploaded_files:
                if st.button("🚀 开始解析文件", use_container_width=True, type="primary"):
                    with st.spinner("解析中..."):
                        try:
                            dfs = [load_single_file(f) for f in uploaded_files]
                            df_raw = dfs[0] if len(dfs)==1 else pd.concat(dfs, ignore_index=True, sort=False)
                            st.session_state.user_df = clean_dataframe(df_raw, True, "不处理", False)
                            st.session_state.use_demo = True
                            st.session_state.demo_type = "真实数据"
                            st.rerun()
                        except Exception as e:
                            st.error(f"失败: {e}")
            
            st.markdown("<p style='text-align: center; color: #aaa; margin: 15px 0;'>—— 或直接体验内置数据 ——</p >", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button("📈 电商数据", use_container_width=True):
                st.session_state.use_demo = True; st.session_state.demo_type = "电商"; st.rerun()
            if col2.button("🎓 学生成绩", use_container_width=True):
                st.session_state.use_demo = True; st.session_state.demo_type = "成绩"; st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.info("📊 **一键出图**\n\n上传表格，自动推荐最合适的图表")
    c2.info("🔮 **趋势预测**\n\nAI 自动拟合历史数据，预测未来走向")
    c3.info("📝 **智能洞察**\n\n用大白话提问，AI 帮你写汇报")
# ==========================================
# 5. 渲染：有数据时的工作台
# ==========================================
else:
    # 侧边栏
    with st.sidebar:
        st.markdown("### ⚙️ 操作面板")
        with st.expander("📥 导出报表", expanded=True):
            if st.button("一键生成 Word", use_container_width=True, type="primary"):
                latest_ai_text = st.session_state.chat_history[-1]["content"] if st.session_state.chat_history else "暂无"
                word_data = generate_word_report(df, clean_text_for_word(latest_ai_text), st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                st.download_button("⬇️ 点击下载", data=word_data, file_name="报告.docx", use_container_width=True)
        if st.button("↩️ 清空并返回", use_container_width=True):
            st.session_state.use_demo = False; st.session_state.chat_history = []; st.session_state.pred_chart = None; st.rerun()

    # 主展示区
    if st.session_state.get("pred_chart"):
        st.markdown("### 📈 AI 趋势预测大屏")
        st.plotly_chart(st.session_state.pred_chart, use_container_width=True)
        if st.button("❌ 关闭预测图"):
            st.session_state.pred_chart = None; st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("fig") is not None:
                st.plotly_chart(msg["fig"], use_container_width=True)

# ==========================================
# 6. 底部输入框（AI 对话框）- 顶格写
# ==========================================
if st.session_state.get("use_demo"):
    user_input = st.chat_input("向 AI 提问，例如：帮我分析一下利润下滑的原因...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)
        
        ai_reply_text = ""
        ai_fig = None
        with st.chat_message("assistant"):
            if "预测" in user_input or "未来" in user_input:
                st.info("🤖 收到指令！正在启动预测引擎...")
                date_cols = [c for c, t in col_types.items() if t == "datetime"]
                num_cols = [c for c, t in col_types.items() if t == "numeric"]
                if date_cols and num_cols:
                    days = int(re.search(r'(\d+)\s*天', user_input).group(1)) if re.search(r'(\d+)\s*天', user_input) else 7
                    ai_fig, msg = create_forecast_chart(df, date_cols[0], num_cols[0], periods=days)
                    if ai_fig:
                        st.session_state.pred_chart = ai_fig
                        ai_reply_text = f"✅ 已生成未来 {days} 天的预测图表，请看主屏幕大图。"
                    else: ai_reply_text = f"❌ 预测失败：{msg}"
                else: ai_reply_text = "❌ 缺少时间或数值列。"
                st.markdown(ai_reply_text)
            elif any(kw in user_input for kw in ["筛选", "找出", "哪个"]):
                st.markdown("🤖 正在生成 Pandas 代码并执行...")
                res = execute_ai_code(api_key, model_name, user_input, df)
                st.code(str(res))
                ai_reply_text = f"✅ 执行结果：\n\n{res}"
            else:
                summary = build_data_summary(df, col_types)
                ai_reply_text = st.write_stream(call_llm_chat(api_key, model_name, summary, st.session_state.chat_history[-10:-1], user_input, "你是资深数据分析师"))
                if "导出" in user_input or "报告" in user_input:
                    word_data = generate_word_report(df, clean_text_for_word(ai_reply_text), st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                    st.download_button("⬇️ 点击下载分析报告.docx", data=word_data, file_name="报告.docx")
                    ai_reply_text += "\n\n*(✅ 已生成 Word 报告)*"

        if ai_reply_text:
            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply_text, "fig": ai_fig})
        st.rerun()
