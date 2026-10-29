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
# UI 渲染区
# ==========================================

# 如果还没有数据（既没传文件，也没点示例）
# 注意：因为没侧边栏，我们在这里接收上传
if not st.session_state.use_demo:
    # 用一个居中的列布局来限制宽度，让卡片显得精致
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # 这是中间的大卡片
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; color: #004b87;'>拖拽 Excel 开始体验</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>支持 .xlsx, .csv 格式</p >", unsafe_allow_html=True)
            
            # 核心：将上传框移到中间卡片内
            uploaded_files = st.file_uploader("上传文件", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            
            st.divider()
            st.markdown("<p style='text-align: center; font-size: 14px;'>没有数据？试试一键载入内置示例</p >", unsafe_allow_html=True)
            
            # 示例选择下拉框
            demo_option = st.selectbox("选择示例数据", ["不使用示例", "📈 电商店铺一季度销售诊断", "🎓 学生期末成绩分析"], label_visibility="collapsed")
            
            # 如果选了示例，改变状态并刷新
            if demo_option != "不使用示例":
                st.session_state.use_demo = True
                st.session_state.demo_type = demo_option
                st.rerun()

    # 底部对话框输入
    user_input = st.chat_input("在这里输入你的需求，或者先去上方拖拽文件...")
    if user_input:
        st.warning("💡 请先在上方卡片上传数据或选择示例哦！")

# ==========================================
# 如果有数据了（上传了或者选了示例）
# ==========================================
if st.session_state.use_demo or (('uploaded_files' in locals() or 'uploaded_files' in globals()) and uploaded_files):
    # --- 数据读取逻辑 ---
    try:
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
        df = clean_dataframe(df_raw, False, False, True) # 默认做一些温和清洗
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
        
        # ================= 以下渲染三栏分析界面 =================
        
        # 顶部状态栏
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
                # 把原本在侧边栏的清洗选项移到这里
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
                    
                # 历史对话
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                        
            # 中间的输入框
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

st.markdown("---")
st.caption("智析 DataSight v3.6｜沉浸式极简版")
