import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
from io import StringIO
from openpyxl.styles import Font, PatternFill, Alignment

# 🌟 导入拆分出的模块 (请确保这4个文件在同一目录下)
from config import CUSTOM_CSS, PROMPT_GENERAL, PROMPT_ECOMMERCE
from data_utils import load_single_file, analyze_columns, clean_dataframe, force_convert_numeric
from chart_utils import auto_recommend_charts
from ai_utils import build_data_summary, call_llm_analysis, call_llm_chat, fig_to_base64

# ==========================================
# 1. 页面配置与初始化
# ==========================================
st.set_page_config(page_title="智析 — 智能数据可视化与解读助手", layout="wide", page_icon="📊")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

defaults = {"ai_result": "", "manual_fig": None, "manual_title": "", "auto_charts": [], "df_sig": "", "chat_history": []}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 2. 侧边栏 UI
# ==========================================
st.sidebar.header("⚙️ 设置")
try: default_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception: default_key = ""

api_key = st.sidebar.text_input("DeepSeek API Key", type="password", value=default_key).strip()
model_name = st.sidebar.selectbox("选择模型", ["deepseek-chat", "deepseek-reasoner"])
enable_chat = st.sidebar.toggle("开启 AI 多轮对话（探讨数据）", value=False)

st.sidebar.markdown("---")
demo_option = st.sidebar.selectbox(
    "✨ 没有数据？试试内置示例", 
    ["不使用示例", "📈 电商店铺一季度销售诊断", "🎓 学生期末成绩分析(复杂版)", "🏫 校园社团活动数据(复杂版)"]
)
uploaded_files = st.sidebar.file_uploader("上传数据文件（可多选进行对比）", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

st.sidebar.divider()
st.sidebar.header("🧹 数据清洗（可选）")
drop_dup = st.sidebar.checkbox("删除完全重复行", value=False)
drop_na_rows = st.sidebar.checkbox("删除含缺失值的行", value=False)
fill_na_num = st.sidebar.checkbox("数值列缺失值填均值", value=False)

# 🌟 侧边栏底部：下载高级电商模板
st.sidebar.divider()
st.sidebar.subheader("📥 下载高级电商数据模板")

@st.cache_data
def get_template_data():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    data = {
        "日期": dates.astype(str), "商品类目": np.random.choice(["女装", "数码配件", "美妆护肤"], 90),
        "推广渠道": np.random.choice(["直通车", "引力魔方", "自然流量"], 90), "访客数(UV)": np.random.randint(200, 1500, 90),
        "支付转化率(%)": np.random.uniform(1.0, 5.5, 90).round(2), "客单价(元)": np.random.randint(50, 300, 90),
        "销售额(元)": 0, "退款金额(元)": 0, "推广花费(元)": 0, "数据周期": ""
    }
    df = pd.DataFrame(data)
    df["销售额(元)"] = (df["访客数(UV)"] * (df["支付转化率(%)"]/100) * df["客单价(元)"]).round(2)
    df["退款金额(元)"] = (df["销售额(元)"] * np.random.uniform(0.05, 0.25, 90)).round(2)
    df["推广花费(元)"] = (df["销售额(元)"] * np.random.uniform(0.1, 0.3, 90)).round(2)
    df.loc[:29, "数据周期"] = "1月"
    df.loc[30:59, "数据周期"] = "2月"
    df.loc[60:, "数据周期"] = "3月"
    return df

template_df = get_template_data()
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    template_df.to_excel(writer, index=False, sheet_name='电商运营数据')
    worksheet = writer.sheets['电商运营数据']
    header_fill = PatternFill(start_color='004B87', end_color='004B87', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    for col_num, value in enumerate(template_df.columns, 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for col in worksheet.columns:
        max_length = 0
        column = col[0].column_letter 
        for cell in col:
            try:
                if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            except: pass
        worksheet.column_dimensions[column].width = (max_length + 2)

st.sidebar.download_button(
    label="⬇️ 下载标准 Excel 模板",
    data=buffer.getvalue(),
    file_name="智析_电商标准数据模板.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

# ==========================================
# 3. 主流程
# ==========================================
st.title("📊 智析 — 智能数据可视化助手")
if not uploaded_files and demo_option == "不使用示例":
    # 🌟 高级引导与规范卡片
    st.markdown("""
    <div style="background-color: #e6f0fa; border-left: 5px solid #004b87; padding: 12px 20px; border-radius: 6px; margin-bottom: 20px; color: #004b87; font-size: 15px; font-weight: 500;">
        👈 请在左侧边栏上传 1 个或多个 Excel/CSV 文件开始使用。
    </div>
    <div style="background-color: #f7f9f8; border-left: 5px solid #004b87; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 20px; display: flex; align-items: flex-start;">
        <div style="font-size: 24px; margin-right: 15px;">🚀</div>
        <div>
            <h4 style="margin: 0 0 5px 0; color: #004b87; font-size: 16px;">极速体验通道</h4>
            <p style="margin: 0; color: #555; font-size: 14px; line-height: 1.5;">手头没有合适的数据？或者想直接看效果？<br>请在左侧边栏的 <b>『✨ 没有数据？试试内置示例』</b> 中选择一个场景，一键生成分析报告。</p >
        </div>
    </div>
    <div style="background-color: #e8f0ef; border-left: 5px solid #5f9ea0; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); display: flex; align-items: flex-start;">
        <div style="font-size: 24px; margin-right: 15px;">🛡️</div>
        <div>
            <h4 style="margin: 0 0 5px 0; color: #3e7375; font-size: 16px;">数据格式规范指南</h4>
            <p style="margin: 0 0 8px 0; color: #555; font-size: 14px;">为了确保 AI 分析的 100% 准确，请在上传前检查 Excel：</p >
            <ul style="margin: 0; padding-left: 20px; color: #555; font-size: 13px; line-height: 1.6;">
                <li><b>单行表头</b>：第一行必须是列名，避免双层表头导致错位。</li>
                <li><b>去掉合并单元格</b>：系统无法识别，建议提前拆分。</li>
                <li><b>清理脏数据</b>：将“缺考”、“未扫”等文字直接留空，以免影响图表计算。</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

try:
    if demo_option != "不使用示例":
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
            df_demo.loc[:29, "数据周期"] = "1月"
            df_demo.loc[30:59, "数据周期"] = "2月"
            df_demo.loc[60:, "数据周期"] = "3月"
            df_demo.loc[70:80, "退款金额(元)"] *= 3
            df_demo.loc[35:45, "推广花费(元)"] *= 2.5
            df_raw = df_demo
            
        elif demo_option == "🎓 学生期末成绩分析(复杂版)":
            np.random.seed(10)
            n = 80
            df_raw = pd.DataFrame({
                "学号": [f"2023{i:03d}" for i in range(1, n+1)],
                "班级": np.random.choice(["高一1班", "高一2班", "高一3班", "高一4班"], n),
                "姓名": [f"学生_{i}" for i in range(n)],
                "语文": np.random.randint(60, 100, n), "数学": np.random.randint(40, 100, n),
                "英语": np.random.randint(55, 100, n), "物理": np.random.randint(30, 100, n),
                "历史": np.random.randint(50, 100, n), "总分": 0
            })
            df_raw["总分"] = df_raw[["语文", "数学", "英语", "物理", "历史"]].sum(axis=1)
            df_raw.loc[10:15, "数学"] = np.nan
            df_raw.loc[20, "物理"] = 250
            
        elif demo_option == "🏫 校园社团活动数据(复杂版)":
            np.random.seed(99)
            n = 100
            df_raw = pd.DataFrame({
                "报名日期": pd.date_range("2024-09-01", periods=n, freq="D").astype(str),
                "学号": [f"2023{np.random.randint(100, 999)}" for _ in range(n)],
                "申请部门": np.random.choice(["外联部", "宣传部", "技术部", "活动部", "秘书处"], n),
                "面试得分": np.random.randint(60, 100, n),
                "是否录用": np.random.choice(["是", "否"], n, p=[0.3, 0.7]),
                "活动预算(元)": np.random.randint(100, 5000, n),
                "实际花费(元)": 0
            })
            df_raw["实际花费(元)"] = (df_raw["活动预算(元)"] * np.random.uniform(0.5, 1.4, n)).round(2)
            df_raw.loc[5:10, "面试得分"] = np.nan

    else:
        dfs = []
        for file in uploaded_files:
            label = file.name.rsplit('.', 1)[0]
            temp_df = load_single_file(file)
            temp_df.columns = temp_df.columns.str.strip()
            if len(uploaded_files) > 1: temp_df["数据周期"] = label
            dfs.append(temp_df)
        if len(dfs) == 1: df_raw = dfs[0]
        elif len(dfs) > 1: df_raw = pd.concat(dfs, ignore_index=True, sort=False)
        else: df_raw = pd.DataFrame()

except Exception as e:
    st.error(f"数据读取或生成失败：{e}"); st.stop()

# 数据清洗与智能路由
df = clean_dataframe(df_raw, drop_dup, drop_na_rows, fill_na_num)
col_types = analyze_columns(df)
df = force_convert_numeric(df, col_types)

is_ecommerce = False
if demo_option == "📈 电商店铺一季度销售诊断": is_ecommerce = True
elif any(word in str(df.columns) for word in ["销售额", "退款", "转化率", "客单价"]): is_ecommerce = True
SYSTEM_PROMPT = PROMPT_ECOMMERCE if is_ecommerce else PROMPT_GENERAL

# 重置缓存
file_sig = "|".join([f.name for f in uploaded_files]) + str(demo_option)
sig = f"{file_sig}|{df.shape}|{list(df.columns)}"
if st.session_state.df_sig != sig:
    st.session_state.df_sig = sig
    st.session_state.auto_charts = auto_recommend_charts(df, col_types)
    st.session_state.manual_fig = None
    st.session_state.ai_result = ""
    st.session_state.chat_history = [] 

# 顶部指标卡
row_count, col_count = df.shape[0], df.shape[1]
num_count = sum(1 for t in col_types.values() if t == "numeric")
cat_count = sum(1 for t in col_types.values() if t == "categorical")
st.markdown(f"""
<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 25px;">
    <div style="flex: 1; min-width: 40%; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #004b87;"><p style="margin: 0; font-size: 14px; color: #555;">总行数</p ><p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #004b87;">{row_count}</p ></div>
    <div style="flex: 1; min-width: 40%; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #004b87;"><p style="margin: 0; font-size: 14px; color: #555;">总列数</p ><p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #004b87;">{col_count}</p ></div>
    <div style="flex: 1; min-width: 40%; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #5f9ea0;"><p style="margin: 0; font-size: 14px; color: #555;">数值列</p ><p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #5f9ea0;">{num_count}</p ></div>
    <div style="flex: 1; min-width: 40%; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid #5f9ea0;"><p style="margin: 0; font-size: 14px; color: #555;">分类列</p ><p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #5f9ea0;">{cat_count}</p ></div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📋 数据预览", "📈 自动图表", "🛠️ 自定义图表", "🤖 AI 分析 & 导出"])
with tab1:
    st.subheader("数据预览（前 20 行）")
    st.dataframe(df.head(20), use_container_width=True)

with tab2:
    st.subheader("系统自动推荐图表")
    charts = st.session_state.auto_charts
    if not charts: st.warning("未识别到可绘图字段。")
    else:
        for i in range(0, len(charts), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(charts):
                    with cols[j]:
                        st.markdown(f"**{charts[i+j][0]}**")
                        st.plotly_chart(charts[i+j][1], use_container_width=True, key=f"auto_{i}_{j}")

with tab3:
    st.subheader("手动自定义图表")
    chart_options = {"柱状图": "柱状图 (用于分类对比)", "折线图": "折线图 (用于看时间趋势)", "散点图": "散点图 (用于看两变量关系)", "直方图": "直方图 (用于看数值分布)", "箱线图": "箱线图 (用于看分散度与异常)", "饼图": "饼图 (用于看占比)"}
    all_cols = list(df.columns)
    c1, c2, c3 = st.columns(3)
    x_sel = c1.selectbox("X 轴字段", all_cols)
    y_sel = c2.selectbox("Y 轴字段", all_cols)
    chart_type = c3.selectbox("图表类型", options=list(chart_options.keys()), format_func=lambda x: chart_options[x])

    chart_tips = {
        "柱状图": "💡 适合：对比不同类别的数据（如：各班级的平均分对比）。X轴选分类，Y轴选数值。",
        "折线图": "💡 适合：展示随时间变化的趋势（如：1-6月的销售额走势）。X轴通常选时间，Y轴选数值。",
        "散点图": "💡 适合：查看两个数值之间的关联关系（如：语文成绩和数学成绩的关系）。X轴和Y轴都要选数值。",
        "直方图": "💡 适合：查看数值的分布区间（如：看看哪个分数段的人最多）。X轴请选要分析的数值列，Y轴可忽略。",
        "箱线图": "💡 适合：查看数据的分散程度和异常值（如：看看各班成绩的差距大不大）。X轴选分类，Y轴选数值。",
        "饼图": "💡 适合：查看各部分占总体的比例（如：男女比例、各科目的分数占比）。X轴选分类列即可。"
    }
    st.info(chart_tips.get(chart_type, ""))

    if st.button("生成自定义图表", type="primary"):
        try:
            has_period = "数据周期" in df.columns
            color_col = "数据周期" if has_period else None
            if chart_type == "柱状图":
                if x_sel in ["姓名", "学号", "ID", "id", "编号"]:
                    fig = px.bar(df, x=x_sel, y=y_sel, color=color_col, barmode="group", title=f"{x_sel} 对比 {y_sel}") if has_period else px.bar(df, x=x_sel, y=y_sel, title=f"{x_sel} 对比 {y_sel}")
                elif has_period and x_sel != "数据周期":
                    agg = df.groupby(["数据周期", x_sel])[y_sel].mean().reset_index().sort_values(y_sel, ascending=False).head(50)
                    fig = px.bar(agg, x=x_sel, y=y_sel, color="数据周期", barmode="group", title=f"{x_sel} 对比 {y_sel}")
                else:
                    agg = df.groupby(x_sel)[y_sel].mean().reset_index().sort_values(y_sel, ascending=False).head(50)
                    fig = px.bar(agg, x=x_sel, y=y_sel, title=f"{x_sel} 对比 {y_sel}")
            elif chart_type == "折线图":
                temp = df.dropna(subset=[x_sel, y_sel]).copy()
                try: temp[x_sel] = pd.to_datetime(temp[x_sel]); temp = temp.sort_values(x_sel)
                except Exception: pass
                fig = px.line(temp, x=x_sel, y=y_sel, color=color_col, markers=True)
            elif chart_type == "散点图": 
                fig = px.scatter(df, x=x_sel, y=y_sel, color=color_col, opacity=0.7)
            elif chart_type == "直方图": 
                if x_sel in ["姓名", "学号", "ID", "id", "编号"]:
                    fig = px.histogram(df, x=y_sel, color=color_col, nbins=20, barmode="group", title=f"{y_sel} 分布")
                else:
                    fig = px.histogram(df, x=x_sel, color=color_col, nbins=20, barmode="group", title=f"{x_sel} 分布对比")
            elif chart_type == "箱线图": 
                fig = px.box(df, x=x_sel, y=y_sel, color=color_col)
            elif chart_type == "饼图":
                vc = df[x_sel].value_counts().head(10).reset_index(); vc.columns = [x_sel, "count"]
                fig = px.pie(vc, names=x_sel, values="count")
            
            fig.update_xaxes(tickangle=-45)
            fig.update_layout(height=450)
            st.session_state.manual_fig = fig
            st.session_state.manual_title = f"自定义｜{chart_type}：{x_sel} × {y_sel}"
        except Exception as e: 
            st.error(f"生成失败：{e}")
            
    if st.session_state.manual_fig is not None:
        st.markdown(f"**{st.session_state.manual_title}**")
        st.plotly_chart(st.session_state.manual_fig, use_container_width=True, key="manual_chart")
with tab4:
    st.subheader("🤖 AI 智能分析")
    if not api_key: 
        st.info("请在侧边栏填入 DeepSeek API Key。")
    else:
        if st.button("生成初始分析报告", type="primary"):
            with st.spinner("AI 正在解析数据..."):
                summary = build_data_summary(df, col_types)
            st.session_state.ai_result = st.write_stream(
                call_llm_analysis(api_key, model_name, summary, SYSTEM_PROMPT)
            )
        elif st.session_state.ai_result:
            st.markdown(st.session_state.ai_result)
            
        if enable_chat and st.session_state.ai_result:
            st.divider()
            st.markdown("### 💬 针对报告继续追问")
            for chat in st.session_state.chat_history:
                with st.chat_message(chat["role"]): st.markdown(chat["content"])
            
            with st.form(key="chat_form", clear_on_submit=True):
                user_query = st.text_input("输入你的问题：", placeholder="例如：哪个月份的利润最高？")
                submit_chat = st.form_submit_button("发送")
                if submit_chat and user_query:
                    st.session_state.chat_history.append({"role": "user", "content": user_query})
                    with st.chat_message("user"): st.markdown(user_query)
                    with st.chat_message("assistant"):
                        summary = build_data_summary(df, col_types)
                        recent_history = st.session_state.chat_history[-10:] 
                        ai_response = st.write_stream(
                            call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_query, SYSTEM_PROMPT)
                        )
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    st.rerun()

    st.divider()
    st.subheader("📥 导出 Markdown 报告")
    
    if st.button("生成并下载报告"):
        md = StringIO()
        md.write("# 智析 — 数据分析报告\n\n")
        if demo_option != "不使用示例":
            md.write(f"> 数据文件：内置示例数据（{demo_option}）\n")
        else:
            md.write(f"> 数据文件：{len(uploaded_files)}个文件合并对比\n")
            
        md.write(f"> 规模：{df.shape[0]} 行 × {df.shape[1]} 列\n\n")
        md.write("## 1. 数据概览\n")
        md.write(f"- 列类型：{col_types}\n")
        md.write("## 2. 自动图表\n")
        
        for title, fig in st.session_state.auto_charts:
            md.write(f"### {title}\n")
            b64 = fig_to_base64(fig)
            if b64: 
                md.write(f"![{title}](data:image/png;base64,{b64})\n\n")
            else: 
                md.write("（图表请回网页查看）\n\n")
                
        md.write("## 3. AI 分析结论\n\n")
        md.write(st.session_state.ai_result or "未生成。\n")
        
        if enable_chat and st.session_state.chat_history:
            md.write("## 4. 追问记录\n\n")
            for chat in st.session_state.chat_history:
                role_name = "🙋 用户" if chat["role"] == "user" else "🤖 AI"
                md.write(f"**{role_name}**: {chat['content']}\n\n")
                
        st.download_button("⬇️ 下载 .md 文件", data=md.getvalue(), file_name="智析_分析报告.md", mime="text/markdown")

st.markdown("---")
st.caption("智析 v3.0 Empowering Everyone with AI Data Insights")
