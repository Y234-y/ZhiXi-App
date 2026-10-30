import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 导入你的自定义模块 (确保文件名一致)
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_chat
from report_utils import generate_word_report
# ==========================================
# 1. 页面配置与高级 CSS 引擎
# ==========================================
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* 隐藏顶部默认白条，防遮挡 */
    header {visibility: hidden;}
    
    /* 极光渐变背景（科技蓝 + 水墨青） */
    .stApp {
        background: radial-gradient(circle at 15% 50%, rgba(0, 75, 135, 0.04) 0%, transparent 50%),
                    radial-gradient(circle at 85% 30%, rgba(95, 158, 160, 0.06) 0%, transparent 50%),
                    #f8fafc;
    }
    
    /* 大标题排版 */
    .main-title { text-align: center; color: #004b87; font-weight: 900; font-size: 3.5rem; margin-top: 4rem; margin-bottom: 0.5rem; letter-spacing: 2px; }
    .sub-title { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
    
    /* 🚀 虚线拖拽上传区美化 */
    [data-testid="stFileUploader"] > div {
        border: 2px dashed #94a3b8 !important;
        border-radius: 12px !important;
        background: rgba(255,255,255,0.4) !important;
        transition: all 0.3s ease;
    }
    [data-testid="stFileUploader"] > div:hover {
        border-color: #004b87 !important;
        background: rgba(0, 75, 135, 0.02) !important;
    }
    
    /* 🚀 主按钮渐变特效 */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #004b87 0%, #0066cc 100%) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(0, 75, 135, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 75, 135, 0.4) !important;
    }
    
    /* 🚀 底部 AI 对话框悬浮阴影 */
    [data-testid="stChatInput"] {
        border-radius: 15px !important;
        box-shadow: 0 8px 30px rgba(0,0,0,0.06) !important;
        border: 1px solid #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# 状态初始化
if "use_demo" not in st.session_state: st.session_state.use_demo = False
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "auto_charts" not in st.session_state: st.session_state.auto_charts = []

# 读取 API Key
try: api_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception: api_key = ""
model_name = "deepseek-chat"

# ==========================================
# 2. 核心数据加载逻辑
# ==========================================
df = None
has_data = st.session_state.use_demo

if has_data:
    try:
        if st.session_state.use_demo:
            if st.session_state.demo_type == "电商":
                np.random.seed(42)
                days = pd.date_range("2024-01-01", periods=90, freq="D")
                df_raw = pd.DataFrame({"日期": days.astype(str), "商品类目": np.random.choice(["女装", "数码", "美妆"], 90), "销售额(元)": np.random.randint(1000, 10000, 90), "退款金额(元)": np.random.randint(100, 2000, 90), "数据周期": ""})
                df_raw.loc[:29, "数据周期"] = "1月"; df_raw.loc[30:59, "数据周期"] = "2月"; df_raw.loc[60:, "数据周期"] = "3月"
            else:
                df_raw = pd.DataFrame({"班级": np.random.choice(["高一1班", "高一2班"], 50), "语文": np.random.randint(60, 100, 50), "数学": np.random.randint(50, 100, 50)})
            
        # 清洗数据
        df = clean_dataframe(df_raw, False, False, True)
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
    except Exception as e:
        st.error(f"数据解析失败：{e}")
        st.session_state.use_demo = False
# ==========================================
# 3. 渲染：无数据时的极简首页 (包含真实文件上传)
# ==========================================
if not has_data:
    st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        # 使用原生 border 容器，配合上面的 CSS 虚线特效
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; color: #004b87; margin-bottom: 0;'>📂 拖拽 Excel 开始分析</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>支持 .xlsx, .csv 格式文件</p >", unsafe_allow_html=True)
            
            # 将上传框放在这里（替换侧边栏）
            uploaded_files = st.file_uploader("上传文件", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
            
            # 如果上传了文件，触发数据加载
            if uploaded_files:
                try:
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
                    
                    # 用 hack 方式标记有数据，并刷新
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "真实数据"
                    st.rerun()
                except Exception as e:
                    st.error(f"解析文件失败：{e}")

            st.markdown("<p style='text-align: center; color: #a0b0c0; font-size: 14px; margin: 15px 0;'>—— 或者一键体验内置场景 ——</p >", unsafe_allow_html=True)
            
            # 🚀 体验按钮 (带有发光和渐变特效)
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📈 电商店铺诊断", use_container_width=True, type="primary"):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "电商"
                    st.rerun()
            with col_btn2:
                if st.button("🎓 学生成绩分析", use_container_width=True):
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "成绩"
                    st.rerun()

    # 底部输入框
    st.markdown("<br>", unsafe_allow_html=True)
    user_input = st.chat_input("或者直接告诉我你想分析什么...")
    # ... 前面是获取 user_input 的逻辑
    if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        # ==========================================
        # 🌟 Agent 路由：如果用户意图是“预测”
        # ==========================================
        if "预测" in user_input or "未来" in user_input:
            st.markdown("🤖 *收到指令！正在启动 AI 预测引擎...*")
            
            # 1. 找时间列和数值列
            date_cols = [c for c, t in col_types.items() if t == "datetime"]
            num_cols = [c for c, t in col_types.items() if t == "numeric"]
            
            if not date_cols or not num_cols:
                st.error("抱歉，当前数据缺少时间列或数值列，无法进行趋势预测。")
            else:
                # 2. 简单的意图识别：提取要预测的列（默认取第一个数值列）
                target_col = num_cols[0] 
                for col in num_cols:
                    if col in user_input:
                        target_col = col
                        break
                
                # 3. 简单提取天数（默认预测7天）
                days = 7
                import re
                match = re.search(r'(\d+)\s*天', user_input)
                if match:
                    days = int(match.group(1))
                
                st.info(f"📊 正在为您预测 **{target_col}** 未来 **{days}** 天的走势...")
                
                # 4. 调用你的底层预测模块
                fig_pred, msg = create_forecast_chart(df, date_cols[0], target_col, periods=days)
                
                if fig_pred:
                    # 直接把图画在对话框里！
                    st.plotly_chart(fig_pred, use_container_width=True)
                    
                    # 5. 让 AI 看着图写分析总结
                    with st.spinner("AI 正在生成预测分析报告..."):
                        prompt = f"用户要求预测 {target_col} 的未来趋势。系统刚刚生成了一张预测图，显示整体呈【上升/下降】趋势（由于你无法直接看图，请用通用的商业预测话术）。请写一段专业的预测结论和备货建议。"
                        ai_response = st.write_stream(
                            call_llm_chat(api_key, model_name, "数据已载入", [], prompt, "你是一个商业预测专家")
                        )
                else:
                    st.error(msg)

        # ==========================================
        # 🌟 普通对话：走原来的分析逻辑
        # ==========================================
        else:
            summary = build_data_summary(df, col_types)
            recent_history = st.session_state.chat_history[-10:]
            ai_response = st.write_stream(
                call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_input, PROMPT_GENERAL)
            )
    
    st.session_state.chat_history.append({"role": "assistant", "content": "执行完毕"})
    st.rerun()
# ==========================================
# 4. 渲染：有数据时的三栏工作台
# ==========================================
if has_data and df is not None:
    c_title, c_reset = st.columns([8, 2])
    with c_title:
        st.markdown(f"<h2 style='margin:0; color:#004b87;'>📊 数据分析工作台 ({st.session_state.demo_type})</h2>", unsafe_allow_html=True)
    with c_reset:
        if st.button("↩️ 返回首页", use_container_width=True):
            st.session_state.use_demo = False
            st.rerun()

    st.divider()
    col_left, col_center, col_right = st.columns([1, 2.5, 1.5])

    with col_left:
    with st.container(border=True):
        st.subheader("🧹 高级数据清洗")
        st.markdown("**📝 文本处理**")
        strip_space = st.checkbox("去除文本首尾空格", value=True)
        st.markdown("**🩹 缺失值处理**")
        na_strategy = st.selectbox("处理策略", ["不处理", "删除包含缺失的行", "数值填均值", "数值填中位数"])
        st.markdown("**🚨 异常值处理**")
        drop_outliers = st.checkbox("剔除极端异常值(3σ)", value=False)
        
        st.divider()
        st.metric("数据行数", df.shape[0])
        st.metric("数据列数", df.shape[1])
    # 中间：AI 对话
    with col_center:
        with st.container(border=True):
            st.subheader("💬 AI 数据分析师")
            with st.expander("🔍 预览前 10 行数据"):
                st.dataframe(df.head(10), use_container_width=True)
                
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
                # 注意这里需要你确认 ai_utils.py 里 call_llm_chat 的最后一个参数
                ai_response = st.write_stream(call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_input, "你是一个资深数据分析师"))
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            st.rerun()

    # 右侧：智能图表
    with col_right:
    with st.container(border=True):
        st.subheader("📈 智能图表")
        # 确保 st.session_state.auto_charts 里有图
        if st.session_state.auto_charts:
            title, fig = st.session_state.auto_charts[0]
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无图表")
            fig = None
        st.divider()
        
        # 🌟 王炸：Word 导出按钮
        if st.button("📥 一键生成标准 Word 报表", use_container_width=True, type="primary"):
            with st.spinner("正在生成企业级诊断报告..."):
                # 获取当前 AI 的分析结果（如果没有，给个默认的）
                current_ai = st.session_state.chat_history[-1]["content"] if st.session_state.chat_history else "暂无分析"
                word_data = generate_word_report(df, current_ai, fig)
                st.download_button(
                    label="⬇️ 点击下载 Word 报告.docx",
                    data=word_data,
                    file_name="智析_商业分析报告.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
