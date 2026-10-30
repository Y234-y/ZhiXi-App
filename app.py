import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import json
import re
import requests

# 引入你的底层模块
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_chat
from report_utils import generate_word_report
from predict_utils import create_forecast_chart
from agent_utils import execute_ai_code

# 1. 页面配置
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊", initial_sidebar_state="collapsed")

# 2. 全局 CSS 样式美化
st.markdown("""
<style>
    .stApp { background: radial-gradient(circle at 15% 50%, rgba(0, 75, 135, 0.04) 0%, transparent 50%), radial-gradient(circle at 85% 30%, rgba(95, 158, 160, 0.06) 0%, transparent 50%), #f8fafc; }
    header {visibility: hidden;}
    [data-testid="stFileUploader"] > div { border: 2px dashed #94a3b8 !important; border-radius: 12px !important; background: rgba(255,255,255,0.6) !important; }
    [data-testid="stFileUploader"] > div:hover { border-color: #004b87 !important; }
    .stButton>button[kind="primary"] { background: linear-gradient(135deg, #004b87 0%, #0066cc 100%) !important; color: white !important; border: none; }
    [data-testid="stSidebar"] { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# 文本净化函数 (用于Word导出)
def clean_text_for_word(text):
    if not text: return "暂无分析内容"
    text = re.sub(r'#+\s', '', text).replace('**', '').replace('|', ' ')
    return re.sub(r'\n+', '\n', text)

# 3. 状态初始化
if "use_demo" not in st.session_state: st.session_state.use_demo = False
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "auto_charts" not in st.session_state: st.session_state.auto_charts = []
if "pred_chart" not in st.session_state: st.session_state.pred_chart = None
if "copy_text" not in st.session_state: st.session_state.copy_text = ""

try: api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception: api_key = ""
model_name = "deepseek-chat"

# 4. 数据加载逻辑
df = None
has_data = st.session_state.use_demo
date_cols = []
num_cols = []
col_types = {}

if has_data:
    try:
        if st.session_state.get("demo_type") == "电商":
            np.random.seed(42)
            days = pd.date_range("2024-01-01", periods=90, freq="D")
            df_raw = pd.DataFrame({"日期": days.astype(str), "类目": np.random.choice(["女装", "数码"], 90), "销售额": np.random.randint(1000, 10000, 90), "退款金额(元)": np.random.randint(100, 2000, 90)})
        elif st.session_state.get("demo_type") == "成绩":
            np.random.seed(10)
            n = 125
            df_raw = pd.DataFrame({"班级": ["高二2班"] * n, "姓名": [f"学生_{i}" for i in range(n)], "选考总分": np.random.randint(390, 600, n), "语文": np.random.randint(44, 123, n), "数学": np.random.randint(34, 112, n), "英语": np.random.randint(76, 136, n)})
        else:
            df_raw = st.session_state.get("user_df", pd.DataFrame())

        if not df_raw.empty:
            df = clean_dataframe(df_raw, strip_space=True, na_strategy="不处理", drop_outliers=False)
            col_types = analyze_columns(df)
            df = force_convert_numeric(df, col_types)
            st.session_state.auto_charts = auto_recommend_charts(df, col_types)
            
            # 🌟 修复：在这里把日期和数值列取出来，供底部对话使用
            date_cols = [c for c, t in col_types.items() if t == "datetime"]
            num_cols = [c for c, t in col_types.items() if t == "numeric"]
            
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        st.session_state.use_demo = False
# ==========================================
# 5. 渲染：无数据时的极简首页
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
                            dfs = []
                            for f in uploaded_files:
                                period_name = f.name.rsplit('.', 1)[0]
                                temp_df = load_single_file(f)
                                temp_df["数据周期"] = period_name
                                dfs.append(temp_df)
                            df_raw = pd.concat(dfs, ignore_index=True, sort=False)
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
    c1.info("📈 **电商运营助理**\n\n传店铺流水，自动揪出退货率异常，生成汇报周报。")
    c2.info("🏪 **线下门店店长**\n\n传门店业绩，对比同期升降，直接制定下周排班动作。")
    c3.info("💬 **客服/行政主管**\n\n传投诉记录，一键汇总负面反馈，生成改进措施。")

# ==========================================
# 6. 渲染：有数据时的侧边栏
# ==========================================
else:
    with st.sidebar:
        st.markdown("### 🛠️ 操作面板")
        with st.container(border=True):
            st.markdown("**📥 导出报表**")
            if st.button("一键生成 Word", use_container_width=True, type="primary"):
                latest_ai_text = st.session_state.chat_history[-1]["content"] if st.session_state.chat_history else "暂无"
                word_data = generate_word_report(df, clean_text_for_word(latest_ai_text), st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                st.download_button("⬇️ 点击下载报告", data=word_data, file_name="分析报告.docx", use_container_width=True)
                st.markdown("<span style='background:#dcfce7; color:#166534; padding:4px 8px; border-radius:4px; font-size:12px;'>✅ 已生成Word报告</span>", unsafe_allow_html=True)

        st.divider()
        st.markdown("**💬 快速汇报**")
        if st.button("一键生成群聊话术", use_container_width=True):
            if st.session_state.chat_history:
                latest_ai = st.session_state.chat_history[-1]["content"]
                prompt = f"请把以下分析报告，压缩成一段适合发在微信群里的工作汇报，字数150字以内，直接说业绩结果和下一步行动，适当使用职场emoji：\n\n{latest_ai}"
                with st.spinner("正在生成群聊话术..."):
                    chat_copy = st.write_stream(call_llm_chat(api_key, model_name, "无", [], prompt, "你是职场汇报专家"))
                    st.session_state.copy_text = chat_copy
        
        if st.session_state.get("copy_text"):
            st.text_area("复制以下文本发给领导：", st.session_state.copy_text, height=150)

        st.divider()
        if st.button("🔄 清空并返回", use_container_width=True):
            st.session_state.use_demo = False
            st.session_state.chat_history = []
            st.session_state.pred_chart = None
            st.session_state.copy_text = ""
            st.rerun()
        # ==========================================
    # 7. 渲染：有数据时的主内容区
    # ==========================================
    _, col_main, _ = st.columns([1, 8, 1])
    
    with col_main:
        # 预测大屏
        if st.session_state.get("pred_chart"):
            st.markdown("### 📈 AI 趋势预测大屏")
            st.plotly_chart(st.session_state.pred_chart, use_container_width=True)
            if st.button("❌ 关闭预测图"): st.session_state.pred_chart = None; st.rerun()
            st.divider()

        # 渲染对话历史
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
        
                # 🌟 终极过滤：干掉大模型画的字符草图
                clean_content = msg["content"]
                if msg["role"] == "assistant":
            # 1. 删掉代码块
                    clean_content = re.sub(r'```.*?```', '\n*(📊 图表已由系统自动渲染，见下方)*\n', clean_content, flags=re.DOTALL)
            # 2. 删掉用 | 和 + 拼出来的丑图
                    lines = clean_content.split('\n')
                    filtered_lines = []
                    for line in lines:
                        if line.count('|') > 2 or line.count('+') > 2:
                            continue
                        filtered_lines.append(line)
                    clean_content = '\n'.join(filtered_lines)
        
        # 渲染净化后的文字
                st.markdown(clean_content)
        
        # 🌟 自动出真图的逻辑保留
                if "import matplotlib.pyplot as plt" in msg["content"] or "```python" in msg["content"] or "图表" in msg["content"]:
                    st.markdown("<div style='background:#f8fafc; padding:10px; border-radius:10px; border-left:4px solid #004b87; margin-top:10px; margin-bottom:10px;'><b>🖼️ 系统真实渲染图表：</b></div>", unsafe_allow_html=True)
                    if st.session_state.auto_charts:
                        for i in range(0, min(2, len(st.session_state.auto_charts))):
                            title, fig = st.session_state.auto_charts[i]
                            st.plotly_chart(fig, use_container_width=True)
# ==========================================
# 8. 底部输入框（顶格写）
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
                st.success("✅ 底层代码执行完毕！")
                st.code(str(res))
                ai_reply_text = f"✅ 代码执行结果：\n\n{res}"
            else:
                summary = build_data_summary(df, col_types)
                ai_reply_text = st.write_stream(call_llm_chat(api_key, model_name, summary, st.session_state.chat_history[-10:-1], user_input, "你是资深数据分析师"))
                
                if "导出" in user_input or "报告" in user_input:
                    st.markdown("---")
                    st.markdown("📥 **已为您生成 Word 报告：**")
                    word_data = generate_word_report(df, clean_text_for_word(ai_reply_text), st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                    st.download_button("⬇️ 点击下载分析报告.docx", data=word_data, file_name="分析报告.docx")
                    ai_reply_text += "\n\n*(✅ 已同步生成 Word 报告)*"

        if ai_reply_text:
            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply_text, "fig": ai_fig})
        st.rerun()
