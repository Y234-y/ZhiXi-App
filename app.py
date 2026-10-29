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
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 极简的全局样式
st.markdown("""
<style>
    .stApp { background-color: #f7f9f8; }
    .main-title { text-align: center; color: #004b87; font-weight: 800; font-size: 3rem; margin-top: 3rem; margin-bottom: 0.5rem; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.2rem; margin-bottom: 4rem; }
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
# 核心 UI：大标题
# ==========================================
st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)

# ==========================================
# 逻辑分流：是否已经有数据
# ==========================================
df = None

# 我们用一个 Session State 来记录是否处于“体验示例”状态
if "use_demo" not in st.session_state: st.session_state.use_demo = False

# 如果侧边栏没有上传文件，也没有体验示例，那数据就是 None
# 我们需要先在主界面接收文件，所以先把读取逻辑放在这里，等待文件传入
# ==========================================
# UI 渲染区 (极简沉浸式)
# ==========================================

# 核心判断逻辑：如果没数据，显示欢迎页
if not st.session_state.use_demo:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        # 加一个大号图标镇场子
        st.markdown("<div style='text-align: center; font-size: 4rem; margin-bottom: 1rem;'>🤖</div>", unsafe_allow_html=True)
        
        # 使用带有边框的卡片
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; color: #004b87; margin-bottom: 0;'>拖拽 Excel 开始体验</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>支持 .xlsx, .csv 格式，或点击下方一键体验</p >", unsafe_allow_html=True)
            
            # 上传组件
            uploaded_files = st.file_uploader("上传文件", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            
            st.divider()
            
            # 🌟 重点：不用下拉框，用三个快捷按钮替代
            st.markdown("<p style='text-align: center; color: #666; font-size: 14px; margin-bottom: 10px;'>没有数据？点击体验内置场景</p >", unsafe_allow_html=True)
            
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if st.button("📈 体验电商销售数据", use_container_width=True):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "📈 电商店铺一季度销售诊断"
                    st.rerun()
            with btn_c2:
                if st.button("🎓 体验成绩分析数据", use_container_width=True):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "🎓 学生期末成绩分析"
                    st.rerun()

    # 底部输入框
    user_input = st.chat_input("或者直接告诉我你想分析什么...")
    if user_input:
        st.warning("💡 请先在上方卡片上传数据，或点击快捷按钮体验哦！")

# ==========================================
# 如果有数据了（上传了或者选了示例）
# ==========================================
if st.session_state.use_demo or (('uploaded_files' in locals() or 'uploaded_files' in globals()) and uploaded_files):
    try:
        # --- 数据加载逻辑 ---
        if st.session_state.use_demo:
            demo_type = st.session_state.demo_type
            if demo_type == "📈 电商店铺一季度销售诊断":
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
            
        # 清洗数据
        df = clean_dataframe(df_raw, False, False, True)
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
        
        # ================= 数据加载完毕，渲染三栏工作台 =================
        
        c_title, c_reset = st.columns([8, 2])
        with c_title:
            st.markdown("<h3 style='margin:0; color:#004b87;'>数据分析工作台</h3>", unsafe_allow_html=True)
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
                st.subheader("📊 核心指标")
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

    except Exception as e:
        st.error(f"数据读取或解析失败：{e}")
