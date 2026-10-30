import streamlit as st
import pandas as pd
import numpy as np
import re

# 导入所有自定义模块
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_chat
from report_utils import generate_word_report
from predict_utils import create_forecast_chart
from agent_utils import execute_ai_code

# 1. 页面配置与高级 CSS
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    header {visibility: hidden;}
    .stApp { background: radial-gradient(circle at 15% 50%, rgba(0, 75, 135, 0.04) 0%, transparent 50%), radial-gradient(circle at 85% 30%, rgba(95, 158, 160, 0.06) 0%, transparent 50%), #f8fafc; }
    .main-title { text-align: center; color: #004b87; font-weight: 900; font-size: 3.5rem; margin-top: 4rem; letter-spacing: 2px; }
    .sub-title { text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
    [data-testid="stFileUploader"] > div { border: 2px dashed #94a3b8 !important; border-radius: 12px !important; background: rgba(255,255,255,0.4) !important; }
    [data-testid="stFileUploader"] > div:hover { border-color: #004b87 !important; }
    .stButton>button[kind="primary"] { background: linear-gradient(135deg, #004b87 0%, #0066cc 100%) !important; color: white !important; box-shadow: 0 4px 15px rgba(0, 75, 135, 0.2) !important; }
</style>
""", unsafe_allow_html=True)

# 2. 状态初始化
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
        # 🌟 1. 如果选的是内置示例
        if st.session_state.get("demo_type") == "电商":
            np.random.seed(42)
            days = pd.date_range("2024-01-01", periods=90, freq="D")
            df_raw = pd.DataFrame({"日期": days.astype(str), "类目": np.random.choice(["女装", "数码"], 90), "销售额": np.random.randint(1000, 10000, 90), "数据周期": ""})
            df_raw.loc[:29, "数据周期"] = "1月"; df_raw.loc[30:59, "数据周期"] = "2月"; df_raw.loc[60:, "数据周期"] = "3月"
            
            df = clean_dataframe(df_raw, strip_space=True, na_strategy="不处理", drop_outliers=False)
            col_types = analyze_columns(df)
            df = force_convert_numeric(df, col_types)
            st.session_state.auto_charts = auto_recommend_charts(df, col_types)

        elif st.session_state.get("demo_type") == "成绩":
            df_raw = pd.DataFrame({"班级": np.random.choice(["一班", "二班"], 50), "语文": np.random.randint(60, 100, 50), "数学": np.random.randint(50, 100, 50)})
            
            df = clean_dataframe(df_raw, strip_space=True, na_strategy="不处理", drop_outliers=False)
            col_types = analyze_columns(df)
            df = force_convert_numeric(df, col_types)
            st.session_state.auto_charts = auto_recommend_charts(df, col_types)

        # 🌟 2. 如果上传的是真实数据（从缓存里直接拿，绝不丢失！）
        elif st.session_state.get("demo_type") == "真实数据":
            df = st.session_state.get("user_df", None)
            if df is not None:
                col_types = analyze_columns(df)
                df = force_convert_numeric(df, col_types)
                st.session_state.auto_charts = auto_recommend_charts(df, col_types)
            else:
                # 如果缓存里真没有，退回首页
                st.session_state.use_demo = False
                st.rerun()
                
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        st.session_state.use_demo = False
if not has_data:
    st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; color: #004b87; margin-bottom: 0;'>📂 拖拽 Excel 开始分析</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>支持 .xlsx, .csv 格式</p >", unsafe_allow_html=True)
            
           # 1. 先把上传框放出来（不要在里面立刻处理数据）
           uploaded_files = st.file_uploader("上传", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)

           # 2. 只有用户点了按钮，才真正开始读取数据
           if uploaded_files:
               if st.button("🚀 开始数据解析", use_container_width=True, type="primary"):
                   with st.spinner("正在读取并清洗数据，请稍候..."):
                       try:
                           dfs = [load_single_file(f) for f in uploaded_files]
                           df_raw = dfs[0] if len(dfs)==1 else pd.concat(dfs, ignore_index=True, sort=False)
                           df = clean_dataframe(df_raw, True, "不处理", False)
                
                           # 存下清理好的数据，防止跳转后丢失
                           st.session_state.user_df = df
                           st.session_state.use_demo = True
                           st.session_state.demo_type = "真实数据"
                           st.rerun()
                       except Exception as e:
                            st.error(f"读取失败：{e}")
            
            st.markdown("<p style='text-align: center; color: #a0b0c0; margin: 15px 0;'>—— 或者一键体验内置场景 ——</p >", unsafe_allow_html=True)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📈 电商店铺诊断", use_container_width=True, type="primary"):
                    st.session_state.use_demo = True; st.session_state.demo_type = "电商"; st.rerun()
            with col_btn2:
                if st.button("🎓 学生成绩分析", use_container_width=True):
                    st.session_state.use_demo = True; st.session_state.demo_type = "成绩"; st.rerun()
# 5. 渲染：有数据时的三栏工作台
if has_data and df is not None:
    c_title, c_reset = st.columns([8, 2])
    with c_title: st.markdown(f"<h2 style='color:#004b87;'>📊 分析工作台 ({st.session_state.get('demo_type')})</h2>", unsafe_allow_html=True)
    with c_reset:
        if st.button("↩️ 返回首页", use_container_width=True):
            st.session_state.use_demo = False
            st.rerun()

    st.divider()
    col_left, col_center, col_right = st.columns([1, 2.5, 1.5])

    # --- 左侧：工具箱 ---
    with col_left:
        with st.container(border=True):
            st.subheader("🧹 数据清洗")
            st.checkbox("去除首尾空格", value=True)
            st.selectbox("缺失值处理", ["不处理", "填均值", "填中位数"])
            st.checkbox("剔除极端异常值(3σ)")
            st.metric("当前数据行数", df.shape[0])

    # --- 中间：主展示 & 对话 & Agent 路由 ---
    with col_center:
        with st.container(border=True):
            # 优先展示预测大图
            if st.session_state.pred_chart:
                st.markdown("### 📈 AI 趋势预测大屏")
                st.plotly_chart(st.session_state.pred_chart, use_container_width=True)
                if st.button("❌ 关闭预测图，返回对话", use_container_width=True):
                    st.session_state.pred_chart = None
                    st.rerun()
                st.divider()
            else:
                st.subheader("💬 AI 数据分析师")
                with st.expander("🔍 预览前 10 行数据"): st.dataframe(df.head(10))
            
            # 历史对话
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
        # 底部输入框
        user_input = st.chat_input("向我提问，或者让我预测未来趋势...")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"): st.markdown(user_input)
            
            with st.chat_message("assistant"):
                # 🌟 路由 1：预测
                if "预测" in user_input or "未来" in user_input:
                    st.info("🤖 收到指令！正在启动预测引擎...")
                    date_cols = [c for c, t in col_types.items() if t == "datetime"]
                    num_cols = [c for c, t in col_types.items() if t == "numeric"]
                    if date_cols and num_cols:
                        days = 7
                        match = re.search(r'(\d+)\s*天', user_input)
                        if match: days = int(match.group(1))
                        fig_pred, msg = create_forecast_chart(df, date_cols[0], num_cols[0], periods=days)
                        if fig_pred:
                            st.session_state.pred_chart = fig_pred
                            st.rerun()
                    else:
                        st.error("缺少日期或数值列，无法预测。")
                        
                # 🌟 路由 2：导出
                elif "导出" in user_input or "报告" in user_input:
                    st.write("🤖 正在为您生成 Word 报表...")
                    word_data = generate_word_report(df, "AI自动分析结论", st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None)
                    st.download_button("⬇️ 点击下载报告", data=word_data, file_name="分析报告.docx")
                    
                # 🌟 路由 3：Code Interpreter (写代码)
                elif any(kw in user_input for kw in ["筛选", "找出", "哪个"]):
                    st.markdown("🤖 正在生成 Pandas 代码并执行...")
                    res = execute_ai_code(api_key, model_name, user_input, df)
                    st.success("✅ 底层代码执行完毕！")
                    st.code(str(res))
                    
                # 🌟 路由 4：普通聊天
                else:
                    summary = build_data_summary(df, col_types)
                    st.write_stream(call_llm_chat(api_key, model_name, summary, st.session_state.chat_history[-10:-1], user_input, "你是资深数据分析师"))
            
            st.session_state.chat_history.append({"role": "assistant", "content": "✅ 操作完成"})
            st.rerun()

    # --- 右侧：控制台（推送到中间） ---
    with col_right:
        with st.container(border=True):
            st.subheader("📈 操作中心")
            # 基础图表展示
            if st.session_state.auto_charts:
                st.plotly_chart(st.session_state.auto_charts[0][1], use_container_width=True)
            
            st.divider()
            st.markdown("**🔮 快捷趋势预测**")
            date_cols = [c for c, t in col_types.items() if t == "datetime"]
            num_cols = [c for c, t in col_types.items() if t == "numeric"]
            if date_cols and num_cols:
                pred_col = st.selectbox("选择指标", num_cols)
                pred_days = st.slider("预测天数", 7, 30, 7)
                if st.button("生成预测图", use_container_width=True):
                    fig_pred, msg = create_forecast_chart(df, date_cols[0], pred_col, periods=pred_days)
                    if fig_pred:
                        st.session_state.pred_chart = fig_pred
                        st.rerun() # 推送到中间大屏
            
            st.divider()
            if st.button("📥 一键导出 Word 报表", use_container_width=True, type="primary"):
                word_data = generate_word_report(df, "分析报告内容", st.session_state.pred_chart or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                st.download_button("⬇️ 点击下载", data=word_data, file_name="分析报告.docx", use_container_width=True)
