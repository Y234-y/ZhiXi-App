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

# 🌟 页面配置：默认收起侧边栏，实现极简居中
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊", initial_sidebar_state="collapsed")

# 🌟 注入高级科技感 CSS
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认的顶部白条，防止标题被切 */
    header {visibility: hidden;}
    
    /* 极光渐变背景（科技蓝 + 水墨青） */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgba(0, 75, 135, 0.05) 0%, transparent 40%),
                    radial-gradient(circle at 90% 80%, rgba(95, 158, 160, 0.08) 0%, transparent 40%),
                    #f7f9f8;
    }
    
    /* 大标题排版 */
    .main-title { 
        text-align: center; 
        color: #004b87; 
        font-weight: 900; 
        font-size: 3.5rem; 
        margin-top: 4rem; 
        margin-bottom: 0.5rem;
        letter-spacing: 2px;
    }
    .sub-title { 
        text-align: center; 
        color: #6c757d; 
        font-size: 1.2rem; 
        margin-bottom: 2rem; 
    }
    
    /* 毛玻璃卡片特效（覆盖 Streamlit 原生的 container） */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.8) !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.08) !important;
        padding: 2.5rem 2rem !important;
    }
    
    /* 按钮特效 */
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    
    /* 底部对话框美化 */
    [data-testid="stChatInput"] {
        border-radius: 15px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
        border: 1px solid #e0e0e0 !important;
    }
</style>
""", unsafe_allow_html=True)
# 状态初始化
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "auto_charts" not in st.session_state: st.session_state.auto_charts = []

# 后台静默读取 API Key
try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    api_key = ""
model_name = "deepseek-chat"

# ==========================================
# ==========================================
# 核心 UI：大标题
# ==========================================
st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)

# ==========================================
# 沉浸式居中交互区 (当没有数据时)
# ==========================================
if "use_demo" not in st.session_state: st.session_state.use_demo = False

if not st.session_state.use_demo:
    # 用空行把卡片往下压，制造呼吸感
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # 将页面分为三列，只取中间那一列，实现居中
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        # 使用原生边框容器
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; margin-bottom: 0px;'>📂 拖拽 Excel 开始体验</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>支持 .xlsx, .csv 格式文件</p >", unsafe_allow_html=True)
            
            # 上传组件
            uploaded_files = st.file_uploader("上传文件", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            
            st.divider()
            
            # 快捷体验按钮
            st.markdown("<p style='text-align: center; color: #666; font-size: 14px; margin-bottom: 10px;'>✨ 或者一键体验内置场景</p >", unsafe_allow_html=True)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📈 体验电商诊断", use_container_width=True):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "电商"
                    st.rerun()
            with col_btn2:
                if st.button("🎓 体验成绩分析", use_container_width=True):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "成绩"
                    st.rerun()

    # 底部的输入框 (悬浮在最下面)
    st.markdown("<br>", unsafe_allow_html=True)
    user_input = st.chat_input("或者直接告诉我你想分析什么...")
    if user_input:
        st.warning("💡 请先在上方卡片上传数据，或点击体验按钮哦！")

# ==========================================
# 有数据后的三栏工作台
# ==========================================
if st.session_state.use_demo or (('uploaded_files' in locals() or 'uploaded_files' in globals()) and uploaded_files):
    # --- 1. 数据加载逻辑 ---
    try:
        if st.session_state.use_demo:
            if st.session_state.demo_type == "电商":
                np.random.seed(42)
                days = pd.date_range("2024-01-01", periods=90, freq="D")
                data = {"日期": days.astype(str), "商品类目": np.random.choice(["女装", "数码配件", "美妆"], 90),
                        "销售额(元)": np.random.randint(1000, 10000, 90), "退款金额(元)": np.random.randint(100, 2000, 90), "数据周期": ""}
                df_raw = pd.DataFrame(data)
                df_raw.loc[:29, "数据周期"] = "1月"; df_raw.loc[30:59, "数据周期"] = "2月"; df_raw.loc[60:, "数据周期"] = "3月"
            else:
                df_raw = pd.DataFrame({"班级": np.random.choice(["高一1班", "高一2班"], 50), "语文": np.random.randint(60, 100, 50), "数学": np.random.randint(50, 100, 50)})
        else:
            dfs = []
            for file in uploaded_files:
                label = file.name.rsplit('.', 1)[0]
                temp_df = load_single_file(file)
                temp_df.columns = temp_df.columns.str.strip()
                if len(uploaded_files) > 1: temp_df["数据周期"] = label
                dfs.append(temp_df)
            df_raw = dfs[0] if len(dfs)== 1 else pd.concat(dfs, ignore_index=True, sort=False)
            
        df = clean_dataframe(df_raw, False, False, True)
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
        
        # --- 2. 渲染三栏工作台 ---
        c_title, c_reset = st.columns([8, 2])
        with c_title:
            st.markdown("<h3 style='margin:0; color:#004b87;'>📊 数据分析工作台</h3>", unsafe_allow_html=True)
        with c_reset:
            if st.button("↩️ 返回首页", use_container_width=True):
                st.session_state.use_demo = False
                st.rerun()

        st.divider()
        col_left, col_center, col_right = st.columns([1, 2.5, 1.5])

        with col_left:
            with st.container(border=True):
                st.subheader("🧹 工具箱")
                st.checkbox("删除完全重复行", value=True)
                st.checkbox("数值列缺失值填均值", value=True)
                st.divider()
                st.subheader("指标总览")
                st.metric("数据行数", df.shape[0])
                st.metric("数据列数", df.shape[1])

        with col_center:
            with st.container(border=True):
                st.subheader("💬 AI 数据分析师")
                with st.expander("🔍 预览前 10 行数据"):
                    st.dataframe(df.head(10), use_container_width=True)
                    
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                        
            user_input = st.chat_input("向 AI 提问，例如：帮我找出异常商品...")
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
                
    except Exception as e:
        st.error(f"数据加载或解析失败：{e}")
