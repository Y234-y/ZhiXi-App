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

def clean_text_for_word(text):
    if not text: return "暂无分析内容"
    import re
    text = re.sub(r'#+\s', '', text)
    text = text.replace('**', '').replace('|', ' ')
    text = re.sub(r'\n+', '\n', text)
    return text
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
# ==========================================
# 4. 终局形态：左控制台 + 右沉浸式 AI 聊天室
# ==========================================
# 初始化聊天记录
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 永远展示双栏布局，左边占 1.2 份，右边占 4 份
col_left, col_right = st.columns([1.2, 4])

# ================= 左侧：极简控制台 =================
with col_left:
    st.markdown("### 📁 数据源")
    
    # 1. 上传与示例体验
    uploaded_files = st.file_uploader("上传", type=["xlsx", "csv"], label_visibility="collapsed", accept_multiple_files=True)
    
    if uploaded_files and not st.session_state.get("use_demo"):
        if st.button("🚀 开始解析文件", use_container_width=True, type="primary"):
            with st.spinner("解析中..."):
                try:
                    dfs = [load_single_file(f) for f in uploaded_files]
                    df_raw = dfs[0] if len(dfs)==1 else pd.concat(dfs, ignore_index=True, sort=False)
                    df = clean_dataframe(df_raw, True, "不处理", False)
                    st.session_state.user_df = df
                    st.session_state.use_demo = True
                    st.session_state.demo_type = "真实数据"
                    st.rerun()
                except Exception as e:
                    st.error(f"失败: {e}")

    # 如果没有传文件，提供一键体验按钮
    if not st.session_state.get("use_demo"):
        st.markdown("<p style='text-align: center; color: #888; margin: 10px 0;'>或体验内置数据</p >", unsafe_allow_html=True)
        if st.button("📈 电商数据", use_container_width=True):
            st.session_state.use_demo = True; st.session_state.demo_type = "电商"; st.rerun()
        if st.button("🎓 学生成绩", use_container_width=True):
            st.session_state.use_demo = True; st.session_state.demo_type = "成绩"; st.rerun()

    # 2. 如果有数据了，显示功能折叠面板（把之前的右侧功能全塞这里）
    if st.session_state.get("use_demo") and df is not None:
        st.divider()
        st.markdown("### 🛠️ 高级功能")
        
        # 清洗面板
        with st.expander("🧹 数据清洗", expanded=False):
            st.checkbox("去除首尾空格", value=True)
            st.selectbox("缺失值处理", ["不处理", "填均值", "填中位数"])
            st.checkbox("剔除异常值(3σ)")
            st.metric("当前行数", df.shape[0])
            
        # 预测面板
        with st.expander("🔮 快捷预测", expanded=False):
            date_cols = [c for c, t in col_types.items() if t == "datetime"]
            num_cols = [c for c, t in col_types.items() if t == "numeric"]
            if date_cols and num_cols:
                pred_col = st.selectbox("指标", num_cols)
                pred_days = st.slider("天数", 7, 30, 7)
                if st.button("生成预测图", use_container_width=True, type="primary"):
                    fig_pred, msg = create_forecast_chart(df, date_cols[0], pred_col, periods=pred_days)
                    if fig_pred:
                        st.session_state.pred_chart = fig_pred
                        st.rerun()
            else:
                st.caption("数据缺少时间或数值列")
                
        # 导出面板
        with st.expander("📥 导出报表", expanded=False):
            if st.button("一键生成 Word", use_container_width=True, type="primary"):
                # 🌟 核心：去聊天记录里把 AI 刚才说的最后一句话捞出来
                if len(st.session_state.chat_history) > 1:
                    # 找最后一条 role 是 assistant 的内容
                    ai_texts = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "assistant"]
                    latest_ai_text = ai_texts[-1] if ai_texts else ""
                else:
                    latest_ai_text = "尚未进行 AI 分析。"
        
        # 净化文本
        clean_text = clean_text_for_word(latest_ai_text)
        
        # 把净化后的文字传给生成函数
        word_data = generate_word_report(df, clean_text, st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
        st.download_button("⬇️ 点击下载", data=word_data, file_name="分析报告.docx", use_container_width=True)
        # 退出工作台
        if st.button("↩️ 清空并返回", use_container_width=True):
            st.session_state.use_demo = False
            st.session_state.chat_history = []
            st.session_state.pred_chart = None
            st.rerun()

# ================= 右侧：主对话展示区 =================
with col_right:
    if not st.session_state.get("use_demo"):
        # 未加载数据时的空状态
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #004b87; font-size: 3.5rem; font-weight: 800;'>智析 DataSight</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 1.1rem; margin-bottom: 3rem;'>请在左侧选择数据源，开启您的 AI 数据之旅。</p >", unsafe_allow_html=True)
    
        # 🌟 加上三个科技感的引导卡片
        c1, c2, c3 = st.columns(3)
    
        with c1:
            st.markdown("""
            <div style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f0f0f0;">
                <div style="font-size: 30px; margin-bottom: 10px;">📊</div>
                <h4 style="margin: 0; color: #004b87;">一键出图</h4>
                <p style="font-size: 13px; color: #888; margin-top: 5px;">上传表格，自动推荐最合适的柱状图、折线图</p >
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown("""
            <div style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f0f0f0;">
                <div style="font-size: 30px; margin-bottom: 10px;">🔮</div>
                <h4 style="margin: 0; color: #004b87;">趋势预测</h4>
                <p style="font-size: 13px; color: #888; margin-top: 5px;">AI 自动拟合历史数据，预测未来 7-30 天走向</p >
            </div>
            """, unsafe_allow_html=True)
        
        with c3:
            st.markdown("""
            <div style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f0f0f0;">
                <div style="font-size: 30px; margin-bottom: 10px;">📝</div>
                <h4 style="margin: 0; color: #004b87;">智能洞察</h4>
                <p style="font-size: 13px; color: #888; margin-top: 5px;">用大白话提问，AI 帮你写汇报、甚至直接导出 Word</p >
            </div>
            """, unsafe_allow_html=True)
    else:
        # 加载数据后的沉浸式聊天区
        # 1. 先渲染预测图（如果有）
        if st.session_state.get("pred_chart"):
            st.markdown("### 📈 AI 趋势预测大屏")
            st.plotly_chart(st.session_state.pred_chart, use_container_width=True)
            if st.button("❌ 关闭预测图"):
                st.session_state.pred_chart = None
                st.rerun()
            st.divider()

        # 2. 渲染历史对话与图表
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # 如果对话里有图表缓存，直接展示在气泡里
                if msg.get("fig") is not None:
                    st.plotly_chart(msg["fig"], use_container_width=True)

# ==========================================
# 底部输入框（AI 对话框）- 必须顶格写，不能缩进！
# ==========================================
user_input = st.chat_input("向 AI 提问，例如：帮我分析一下利润下滑的原因...")

if user_input:
    # 1. 记录并展示用户提问
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"): 
        st.markdown(user_input)
    
    ai_reply_text = ""
    ai_fig = None
    
    # 2. 展示 AI 回复区
    with st.chat_message("assistant"):
        # 路由 1：预测
        if "预测" in user_input or "未来" in user_input:
            st.info("🤖 收到指令！正在启动预测引擎...")
            if date_cols and num_cols:
                days = 7
                match = re.search(r'(\d+)\s*天', user_input)
                if match: days = int(match.group(1))
                
                ai_fig, msg = create_forecast_chart(df, date_cols[0], num_cols[0], periods=days)
                if ai_fig:
                    st.session_state.pred_chart = ai_fig
                    ai_reply_text = f"✅ 已为您生成未来 {days} 天的预测图表，请看主屏幕大图。"
                else:
                    ai_reply_text = f"❌ 预测失败：{msg}"
            else:
                ai_reply_text = "❌ 数据缺少时间或数值列，无法预测。"
            st.markdown(ai_reply_text)
            
        # 路由 2：Code Interpreter (写代码)
        elif any(kw in user_input for kw in ["筛选", "找出", "哪个"]):
            st.markdown("🤖 正在生成 Pandas 代码并执行...")
            res = execute_ai_code(api_key, model_name, user_input, df)
            st.success("✅ 底层代码执行完毕！")
            st.code(str(res))
            ai_reply_text = f"✅ 代码执行完毕，结果为：\n\n{res}"
            
        # 路由 3：普通对话分析 + 导出缝合
        else:
            summary = build_data_summary(df, col_types)
            # 流式输出文字
            ai_reply_text = st.write_stream(
                call_llm_chat(api_key, model_name, summary, st.session_state.chat_history[-10:-1], user_input, "你是资深数据分析师")
            )
            
            # 如果用户提了导出，立刻弹下载按钮
            if "导出" in user_input or "报告" in user_input:
                st.markdown("---")
                st.markdown("📥 **已为您生成 Word 报告：**")
                
                # 调用刚才加的净化函数
                clean_text = clean_text_for_word(ai_reply_text)
                word_data = generate_word_report(df, clean_text, st.session_state.get("pred_chart") or (st.session_state.auto_charts[0][1] if st.session_state.auto_charts else None))
                
                st.download_button(
                    label="⬇️ 点击下载分析报告.docx", 
                    data=word_data, 
                    file_name="智析_分析报告.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                ai_reply_text += "\n\n*(✅ 已同步生成 Word 报告，请点击上方按钮下载)*"

    # 3. 存入历史记录并刷新
    if ai_reply_text:
        st.session_state.chat_history.append({"role": "assistant", "content": ai_reply_text, "fig": ai_fig})
        
    st.rerun()
       
