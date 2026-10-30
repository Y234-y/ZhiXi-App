import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import json
import re
import requests
from io import StringIO

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
    /* 背景：极淡的渐变，不抢正文风头 */
    .stApp { background: linear-gradient(135deg, #f8fafc 0%, #f0f4f8 100%); }
    header { visibility: hidden; }
    
    /* 全局正文字体行高，缓解阅读疲劳 */
    .stMarkdown p, .stMarkdown li { line-height: 1.8; color: #333; font-size: 15px; }
    
    /* 标题层级优化：加图标和间距 */
    .stMarkdown h1 { font-size: 2.2rem !important; color: #004b87 !important; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-top: 30px; }
    .stMarkdown h2 { font-size: 1.8rem !important; color: #004b87 !important; margin-top: 25px; }
    .stMarkdown h3 { font-size: 1.4rem !important; color: #005a9e !important; margin-top: 20px; }

    /* Markdown 代码块美化 */
    pre { background-color: #f8fafc !important; border: 1px solid #e2e8f0 !important; border-radius: 10px !important; padding: 15px !important; }
    code { color: #005a9e !important; background-color: #f0f4f8 !important; padding: 2px 6px !important; border-radius: 4px !important; }

    /* Markdown 表格美化 (关键：隔行变色、深蓝表头) */
    table { border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    th { background-color: #004b87 !important; color: white !important; padding: 12px 15px !important; text-align: left; border: none; }
    td { padding: 10px 15px !important; border-bottom: 1px solid #e2e8f0; }
    tr:nth-child(even) { background-color: #f8fafc; }
    tr:hover { background-color: #e6f0fa; }

    /* 底部 AI 输入框 */
    [data-testid="stChatInput"] { border-radius: 12px !important; box-shadow: 0 8px 30px rgba(0,0,0,0.06) !important; border: 1px solid #cbd5e1 !important; }
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

try: api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception: api_key = ""
model_name = "deepseek-chat"
# ==========================================
# 4. 数据加载
# ==========================================
df = None
if st.session_state.use_demo:
    try:
        if st.session_state.get("demo_type") == "电商":
            np.random.seed(42)
            days = pd.date_range("2024-01-01", periods=90, freq="D")
            df_raw = pd.DataFrame({"日期": days.astype(str), "类目": np.random.choice(["女装", "数码"], 90), "销售额": np.random.randint(1000, 10000, 90)})
        elif st.session_state.get("demo_type") == "成绩":
            # 制造一些复杂成绩数据
            np.random.seed(10)
            n = 125
            df_raw = pd.DataFrame({
                "班级": ["高二2班"] * n,
                "姓名": [f"学生_{i}" for i in range(n)],
                "选考总分": np.random.randint(390, 600, n),
                "语文": np.random.randint(44, 123, n), "数学": np.random.randint(34, 112, n),
                "英语": np.random.randint(76, 136, n), "政治": np.random.randint(48, 95, n),
                "历史": np.random.randint(49, 81, n), "地理": np.random.randint(42, 95, n)
            })
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
# 5. 渲染：极简首页
# ==========================================
if not st.session_state.use_demo:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, c_center, _ = st.columns([1, 2, 1])
    with c_center:
        st.markdown("<h1 style='text-align: center; border: none; font-size: 3.5rem;'>智析 DataSight</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.2rem; margin-bottom: 3rem;'>零门槛的 AI 数据可视化与洞察助手</p >", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center; color: #004b87;'>📂 拖拽或点击上传数据</h4>", unsafe_allow_html=True)
            uploaded_files = st.file_uploader("上传", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            if uploaded_files:
                if st.button("🚀 开始解析文件", use_container_width=True, type="primary"):
                    with st.spinner("解析中..."):
                        dfs = [load_single_file(f) for f in uploaded_files]
                        df_raw = dfs[0] if len(dfs)==1 else pd.concat(dfs, ignore_index=True, sort=False)
                        st.session_state.user_df = clean_dataframe(df_raw, True, "不处理", False)
                        st.session_state.use_demo = True
                        st.session_state.demo_type = "真实数据"
                        st.rerun()
            
            st.markdown("<p style='text-align: center; color: #94a3b8; margin: 15px 0;'>—— 或直接体验内置数据 ——</p >", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("📈 电商数据", use_container_width=True):
                st.session_state.use_demo = True; st.session_state.demo_type = "电商"; st.rerun()
            if c2.button("🎓 学生成绩", use_container_width=True):
                st.session_state.use_demo = True; st.session_state.demo_type = "成绩"; st.rerun()
# ==========================================
# 6. 渲染：数据工作台
# ==========================================
if st.session_state.use_demo and df is not None:
    
    # --- 侧边栏优化 ---
    with st.sidebar:
        st.markdown("### 🛠️ 操作面板")
        with st.container(border=True):
            st.markdown("**📥 导出报表**")
            if st.button("一键生成 Word", use_container_width=True, type="primary"):
                latest_ai_text = st.session_state.chat_history[-1]["content"] if st.session_state.chat_history else "暂无"
                word_data = generate_word_report(df, clean_text_for_word(latest_ai_text), st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                st.download_button("⬇️ 点击下载报告", data=word_data, file_name="分析报告.docx", use_container_width=True)
                # 状态提示徽章
                st.markdown("<span style='background:#dcfce7; color:#166534; padding:4px 8px; border-radius:4px; font-size:12px;'>✅ 已生成Word报告</span>", unsafe_allow_html=True)

        st.divider()
        if st.button("🔄 清空并返回", use_container_width=True):
            st.session_state.use_demo = False; st.session_state.chat_history = []; st.session_state.pred_chart = None; st.rerun()

    # --- 主内容区居中限制 ---
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
                st.markdown(msg["content"])
                
                # 🌟 核心杀手锏：如果 AI 吐出了代码，直接把底层图画出来！
                if "import matplotlib.pyplot as plt" in msg["content"] or "```python" in msg["content"]:
                    st.markdown("<div style='background:#f8fafc; padding:15px; border-radius:10px; border-left:4px solid #004b87; margin-top:15px;'><b>🖼️ 系统自动渲染的交互式图表：</b></div>", unsafe_allow_html=True)
                    if st.session_state.auto_charts:
                        # 最多展示前两张，并排展示
                        for i in range(0, min(2, len(st.session_state.auto_charts))):
                            title, fig = st.session_state.auto_charts[i]
                            st.plotly_chart(fig, use_container_width=True)

        # --- 底部输入框 + 快捷提问 ---
        st.markdown("<hr style='margin-top: 40px; border: 0.5px solid #e2e8f0;'>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size: 13px; color: #64748b; margin-bottom: 5px;'>📌 快捷提问：</p >", unsafe_allow_html=True)
        qc1, qc2, qc3 = st.columns(3)
        quick_prompt = ""
        if qc1.button("细化教学建议", use_container_width=True): quick_prompt = "帮我再细化一下针对低分学生的教学建议。"
        if qc2.button("分析数学低分", use_container_width=True): quick_prompt = "单独分析一下数学成绩低于60分的学生情况。"
        if qc3.button("生成PPT文案", use_container_width=True): quick_prompt = "请把刚才的分析结论，转换成适合放在PPT汇报上的短句。"
        
        user_input = st.chat_input("向 AI 提问，或点击上方快捷按钮...")
        if quick_prompt: user_input = quick_prompt
        
        # 处理提问
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"): st.markdown(user_input)
            
            ai_reply_text = ""
            with st.chat_message("assistant"):
                if "预测" in user_input or "未来" in user_input:
                    date_cols = [c for c, t in col_types.items() if t == "datetime"]
                    num_cols = [c for c, t in col_types.items() if t == "numeric"]
                    if date_cols and num_cols:
                        days = int(re.search(r'(\d+)\s*天', user_input).group(1)) if re.search(r'(\d+)\s*天', user_input) else 7
                        ai_fig, msg = create_forecast_chart(df, date_cols[0], num_cols[0], periods=days)
                        if ai_fig: st.session_state.pred_chart = ai_fig; ai_reply_text = f"✅ 已生成预测图。"
                        else: ai_reply_text = f"❌ {msg}"
                    st.markdown(ai_reply_text)
                else:
                    summary = build_data_summary(df, col_types)
                    ai_reply_text = st.write_stream(call_llm_chat(api_key, model_name, summary, st.session_state.chat_history[-10:-1], user_input, "你是资深数据分析师"))
            
            if ai_reply_text:
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply_text})
            st.rerun()
