import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import json
import requests
from io import StringIO

# 导入自定义模块
from config import CUSTOM_CSS, PROMPT_GENERAL, PROMPT_ECOMMERCE
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_analysis, call_llm_chat, fig_to_base64

# ==========================================
# 1. 页面配置与高级 CSS 样式注入
# ==========================================
st.set_page_config(page_title="智析 DataSight", layout="wide", page_icon="📊")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 注入毛玻璃高级样式
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f4f7f9 0%, #e8f0ef 100%); }
    .main-title { text-align: center; color: #004b87; font-family: 'PingFang SC', sans-serif; font-weight: 800; font-size: 3rem; margin-bottom: 0.5rem; letter-spacing: 2px; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 2rem; }
    .glass-card { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 16px; padding: 25px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.05); margin-bottom: 20px; }
    .tag { display: inline-block; background: #e6f0fa; color: #004b87; padding: 6px 16px; border-radius: 20px; font-size: 13px; margin: 0 5px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# 状态初始化
defaults = {"ai_result": "", "manual_fig": None, "manual_title": "", "auto_charts": [], "df_sig": "", "chat_history": []}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 2. 侧边栏 UI (隐藏 Key、多模型、上传、清洗)
# ==========================================
st.sidebar.header("⚙️ 系统状态")
try:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    st.sidebar.success("✅ AI 多引擎调度已就绪")
except Exception:
    api_key = ""
    st.sidebar.error("❌ AI 引擎未配置")

model_name_raw = st.sidebar.selectbox("🧠 当前调度引擎", ["deepseek-chat (默认)", "qwen-max (通义)", "moonshot-v1 (Kimi)"])
model_name = "deepseek-chat" if "deepseek" in model_name_raw else ("qwen-max" if "qwen" in model_name_raw else "moonshot-v1-8k")

st.sidebar.markdown("---")
demo_option = st.sidebar.selectbox(
    "✨ 没有数据？试试内置示例", 
    ["不使用示例", "📈 电商店铺一季度销售诊断", "🎓 学生期末成绩分析", "🏫 校园社团活动数据"]
)
uploaded_files = st.sidebar.file_uploader("上传数据文件（可多选）", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

st.sidebar.divider()
st.sidebar.header("🧹 数据清洗（可选）")
drop_dup = st.sidebar.checkbox("删除完全重复行", value=False)
drop_na_rows = st.sidebar.checkbox("删除含缺失值的行", value=False)
fill_na_num = st.sidebar.checkbox("数值列缺失值填均值", value=False)

# ==========================================
# 3. 数据读取与生成逻辑前置 (防止 df 未定义)
# ==========================================
df = None
if demo_option != "不使用示例" or uploaded_files:
    try:
        if demo_option != "不使用示例":
            # --- 内置示例数据生成 ---
            if demo_option == "📈 电商店铺一季度销售诊断":
                np.random.seed(42) 
                days = pd.date_range("2024-01-01", periods=90, freq="D")
                data = {
                    "日期": days.astype(str), "商品类目": np.random.choice(["女装", "数码配件", "美妆护肤"], 90),
                    "推广渠道": np.random.choice(["直通车", "引力魔方", "自然流量"], 90),
                    "访客数(UV)": np.random.randint(200, 1500, 90), "支付转化率(%)": np.random.uniform(1.0, 5.5, 90).round(2),
                    "客单价(元)": np.random.randint(50, 300, 90), "销售额(元)": 0, "退款金额(元)": 0, "推广花费(元)": 0, "数据周期": ""
                }
                df_demo = pd.DataFrame(data)
                df_demo["销售额(元)"] = (df_demo["访客数(UV)"] * (df_demo["支付转化率(%)"]/100) * df_demo["客单价(元)"]).round(2)
                df_demo["退款金额(元)"] = (df_demo["销售额(元)"] * np.random.uniform(0.05, 0.25, 90)).round(2)
                df_demo["推广花费(元)"] = (df_demo["销售额(元)"] * np.random.uniform(0.1, 0.3, 90)).round(2)
                df_demo.loc[:29, "数据周期"] = "1月"; df_demo.loc[30:59, "数据周期"] = "2月"; df_demo.loc[60:, "数据周期"] = "3月"
                df_demo.loc[70:80, "退款金额(元)"] *= 3
                df_demo.loc[35:45, "推广花费(元)"] *= 2.5
                df_raw = df_demo
            elif demo_option == "🎓 学生期末成绩分析":
                np.random.seed(10)
                n = 80
                df_raw = pd.DataFrame({
                    "学号": [f"2023{i:03d}" for i in range(1, n+1)],
                    "班级": np.random.choice(["高一1班", "高一2班", "高一3班", "高一4班"], n),
                    "姓名": [f"学生_{i}" for i in range(n)],
                    "语文": np.random.randint(60, 100, n), "数学": np.random.randint(40, 100, n),
                    "英语": np.random.randint(55, 100, n), "物理": np.random.randint(30, 100, n), "总分": 0
                })
                df_raw["总分"] = df_raw[["语文", "数学", "英语", "物理"]].sum(axis=1)
                df_raw.loc[10:15, "数学"] = np.nan
                df_raw.loc[20, "物理"] = 250
            elif demo_option == "🏫 校园社团活动数据":
                np.random.seed(99)
                n = 100
                df_raw = pd.DataFrame({
                    "报名日期": pd.date_range("2024-09-01", periods=n, freq="D").astype(str),
                    "申请部门": np.random.choice(["外联部", "宣传部", "技术部", "活动部"], n),
                    "面试得分": np.random.randint(60, 100, n),
                    "活动预算(元)": np.random.randint(100, 5000, n),
                })
        else:
            # --- 读取真实文件 ---
            dfs = []
            for file in uploaded_files:
                label = file.name.rsplit('.', 1)[0]
                temp_df = load_single_file(file)
                temp_df.columns = temp_df.columns.str.strip()
                if len(uploaded_files) > 1: temp_df["数据周期"] = label
                dfs.append(temp_df)
            df_raw = dfs[0] if len(dfs)== 1 else pd.concat(dfs, ignore_index=True, sort=False)
            
        # 清洗数据并生成图表缓存
        df = clean_dataframe(df_raw, drop_dup, drop_na_rows, fill_na_num)
        col_types = analyze_columns(df)
        df = force_convert_numeric(df, col_types)
        
        if "df_sig" not in st.session_state or st.session_state.df_sig != str(df.shape):
            st.session_state.df_sig = str(df.shape)
            st.session_state.auto_charts = auto_recommend_charts(df, col_types)
            
    except Exception as e:
        st.error(f"数据读取或解析失败：{e}")
        df = None
# ==========================================
# 4. 主界面渲染 (居中留白 + 三栏布局)
# ==========================================

# 顶部大标题
st.markdown("<div class='main-title'>智析 DataSight</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>零门槛的 AI 数据可视化与洞察助手</div>", unsafe_allow_html=True)

if df is None:
    # ============ 无数据状态：居中下沉引导区 ============
    # 用 st.markdown 塞入大量空行，把内容往下压
    st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div class="glass-card" style="text-align: center; padding-top: 30px; padding-bottom: 30px;">
            <div style="margin-bottom: 30px;">
                <span class="tag">📊 自动图表</span>
                <span class="tag">🤖 AI 智能诊断</span>
                <span class="tag">📥 导出报表</span>
            </div>
            <h3 style="color: #004b87; font-size: 1.5rem; margin-bottom: 10px;">拖拽 Excel 开始体验</h3>
            <p style="color: #888; font-size: 1rem;">支持 .xlsx, .xls, .csv 格式<br>或者直接对我说：<b>“帮我分析一下电商销售数据”</b></p >
        </div>
        """, unsafe_allow_html=True)
        
        # 底部对话输入框
        user_input = st.chat_input("在这里输入你的需求，或者先去左侧上传文件...")
        if user_input:
            st.warning("💡 请先在左侧边栏上传文件，或选择【内置示例】哦！")

else:
    # ============ 有数据状态：三栏专业布局 ============
    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_center, col_right = st.columns([1, 2.5, 1.5])

    with col_left:
        st.markdown("<div class='glass-card' style='padding: 20px;'>", unsafe_allow_html=True)
        st.subheader("🧹 数据清洗状态")
        st.write(f"✅ 删除重复行：{'已开启' if drop_dup else '未开启'}")
        st.write(f"✅ 缺失值处理：{'已开启' if fill_na_num else '未开启'}")
        
        st.divider()
        st.subheader("📊 核心指标")
        st.metric("数据总行数", df.shape[0])
        st.metric("数据总列数", df.shape[1])
        st.markdown("</div>", unsafe_allow_html=True)

    with col_center:
        st.markdown("<div class='glass-card' style='padding-bottom: 10px;'>", unsafe_allow_html=True)
        st.subheader("💬 AI 数据分析师")
        
        with st.expander("🔍 预览当前数据 (前 10 行)", expanded=False):
            st.dataframe(df.head(10), use_container_width=True)
            
        # 聊天历史记录
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 中间底部的输入框
        user_input = st.chat_input("向 AI 提问，例如：帮我找出利润异常的商品...")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                summary = build_data_summary(df, col_types)
                recent_history = st.session_state.chat_history[-10:]
                ai_response = st.write_stream(
                    call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_input, SYSTEM_PROMPT)
                )
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            st.rerun()

    with col_right:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.subheader("📈 智能图表")
        if st.session_state.auto_charts:
            title, fig = st.session_state.auto_charts[0]
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无推荐图表")
            
        st.divider()
        st.button("📥 一键导出定制化报告", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("智析 DataSight v3.0 交互版")
