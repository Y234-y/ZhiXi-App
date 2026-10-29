import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io

# 导入自定义模块
from config import CUSTOM_CSS, PROMPT_GENERAL, PROMPT_ECOMMERCE
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_analysis, call_llm_chat, fig_to_base64

# 页面配置
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 注入极简的全局样式（去掉花哨的毛玻璃，保留高级色调）
st.markdown("""
<style>
    .stApp { background-color: #f7f9f8; }
    .main-title { text-align: center; color: #004b87; font-weight: 800; font-size: 2.8rem; margin-top: 2rem; margin-bottom: 0.5rem; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 3rem; }
</style>
""", unsafe_allow_html=True)

# 状态初始化
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "auto_charts" not in st.session_state: st.session_state.auto_charts = []

# 侧边栏
st.sidebar.header("⚙️ 系统状态")
try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    st.sidebar.success("✅ AI 多引擎调度已就绪")
except Exception:
    api_key = ""
    st.sidebar.error("❌ AI 引擎未配置")

model_name = "deepseek-chat" # 简化处理
demo_option = st.sidebar.selectbox("✨ 试试内置示例", ["不使用示例", "📈 电商店铺一季度销售诊断", "🎓 学生期末成绩分析"])
uploaded_files = st.sidebar.file_uploader("上传数据文件", type=["xlsx", "csv"], accept_multiple_files=True)

st.sidebar.divider()
drop_dup = st.sidebar.checkbox("删除完全重复行", value=False)
fill_na_num = st.sidebar.checkbox("数值列缺失值填均值", value=False)

# ==========================================
# 数据读取逻辑
# ==========================================
df = None
if demo_option != "不使用示例" or uploaded_files:
    try:
        if demo_option == "📈 电商店铺一季度销售诊断":
            # 生成电商数据
            np.random.seed(42)
            days = pd.date_range("2024-01-01", periods=90, freq="D")
            data = {"日期": days.astype(str), "商品类目": np.random.choice(["女装", "数码配件", "美妆"], 90),
                    "销售额(元)": np.random.randint(1000, 10000, 90), "退款金额(元)": np.random.randint(100, 2000, 90), "数据周期": ""}
            df_raw = pd.DataFrame(data)
            df_raw.loc[:29, "数据周期"] = "1月"; df_raw.loc[30:59, "数据周期"] = "2月"; df_raw.loc[60:, "数据周期"] = "3月"
        elif demo_option == "🎓 学生期末成绩分析":
            # 生成成绩数据
            df_raw = pd.DataFrame({"班级": np.random.choice(["高一1班", "高一2班"], 50), "语文": np.random.randint(60, 100, 50), "数学": np.random.randint(50, 100, 50)})
        else:
            # 读取真实文件
            dfs = []
            for file in uploaded_files:
                label = file.name.rsplit('.', 1)[0]
                temp_df = load_single_file(file)
                temp_df.columns = temp_df.columns.str.strip()
                if len(uploaded_files) > 1: temp_df["数据周期"] = label
                dfs.append(temp_df)
            df_raw = dfs[0] if len(dfs)== 1 else pd.concat(dfs, ignore_index=True, sort=False)
            
        df = clean_dataframe(df_raw, drop_dup, False, fill_na_num)
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
    except Exception as e:
        st.error(f"数据读取失败：{e}")
        df = None
# ==========================================
# UI 渲染
# ==========================================
st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)

if df is None:
    # 【无数据状态】给上方留出大量空白，把中间内容往下压
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # 使用 Streamlit 原生带边框容器
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; color: #004b87;'>拖拽 Excel 开始体验</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>支持 .xlsx, .csv 格式，或在左侧选择示例</p >", unsafe_allow_html=True)
            # 将上传框直接放进卡片里，替代侧边栏上传（提升体验）
            st.file_uploader("上传文件", type=["xlsx", "csv"], label_visibility="collapsed")
            
    # 底部输入框
    user_input = st.chat_input("在这里输入你的需求，或先去左侧上传文件...")
    if user_input:
        st.warning("💡 请先上传数据，或选择【内置示例】哦！")

else:
    # 【有数据状态】三栏布局
    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_center, col_right = st.columns([1, 2.5, 1.5])

    with col_left:
        with st.container(border=True):
            st.subheader("📊 核心指标")
            st.metric("数据行数", df.shape[0])
            st.metric("数据列数", df.shape[1])
            st.caption("🧹 已应用数据清洗规则")

    with col_center:
        with st.container(border=True):
            st.subheader("💬 AI 数据分析师")
            
            with st.expander("🔍 预览前 10 行数据"):
                st.dataframe(df.head(10), use_container_width=True)
                
            # 渲染历史对话
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
        # 底部输入框
        user_input = st.chat_input("向 AI 提问，例如：帮我找出利润异常的商品...")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                summary = build_data_summary(df, col_types)
                recent_history = st.session_state.chat_history[-10:]
                ai_response = st.write_stream(call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_input, PROMPT_GENERAL))
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            st.rerun()

    with col_right:
        with st.container(border=True):
            st.subheader("📈 智能图表")
            if st.session_state.auto_charts:
                title, fig = st.session_state.auto_charts[0]
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无图表")
                
            st.divider()
            st.button("📥 一键导出报告", use_container_width=True, type="primary")

st.markdown("---")
st.caption("智析 DataSight v3.5｜现代 AI Copilot 布局")
