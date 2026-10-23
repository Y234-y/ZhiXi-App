import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import base64
from io import StringIO

st.set_page_config(page_title="智析 — 智能数据可视化与解读助手", layout="wide", page_icon="📊")

# ========== Session State 初始化 ==========
defaults = {
    "ai_result": "", 
    "manual_fig": None, 
    "manual_title": "", 
    "auto_charts": [], 
    "df_sig": "",
    "chat_history": []  # 保存多轮对话历史
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ========== 数据读取工具 ==========
def read_csv_smart(file):
    for enc in ["utf-8", "gbk", "gb18030", "utf-8-sig"]:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    file.seek(0)
    return pd.read_csv(file, encoding="utf-8", errors="replace")

import re # 如果文件开头没引入 re，记得加上

def load_single_file(file, sheet_name=None):
    name = file.name.lower()
    if name.endswith(".csv"):
        return read_csv_smart(file)
    
    df_raw = pd.read_excel(file, sheet_name=sheet_name or 0, header=None)
    
    # 1. 找真正的表头行
    header_row_idx = 0
    for i in range(min(10, len(df_raw))):
        row_str = " ".join([str(x) for x in df_raw.iloc[i].values if pd.notna(x)])
        if any(kw in row_str for kw in ["姓名", "班级", "总分", "学号", "日期"]):
            header_row_idx = i
            break
            
    headers = []
    for col in range(df_raw.shape[1]):
        h1 = str(df_raw.iloc[header_row_idx, col]).strip() if pd.notna(df_raw.iloc[header_row_idx, col]) else ""
        h2 = ""
        if header_row_idx + 1 < len(df_raw):
            h2 = str(df_raw.iloc[header_row_idx + 1, col]).strip() if pd.notna(df_raw.iloc[header_row_idx + 1, col]) else ""
        
        if "Unnamed" in h1: h1 = ""
        if "Unnamed" in h2: h2 = ""

        final_h = h1
        
        # 2. 智能拼接（防止把第一行数据当表头）
        if h1 in ["姓名", "班级", "学号", "选科", "考号"]:
            final_h = h1
        elif h2 and h2 != h1:
            if not h2.isdigit() and len(h2) <= 4:
                final_h = f"{h1}_{h2}" if h1 else h2
            
        # 3. 处理空列名
        if not final_h:
            final_h = f"空列_{col}"
            
        headers.append(final_h)
        
    # 4. 列名去重
    final_headers = []
    counts = {}
    for h in headers:
        if h in counts:
            counts[h] += 1
            final_headers.append(f"{h}_{counts[h]}")
        else:
            counts[h] = 1
            final_headers.append(h)
            
    # 5. 判断数据从哪行开始
    data_start_row = header_row_idx + 1
    if header_row_idx + 1 < len(df_raw):
        second_row_numeric_ratio = pd.to_numeric(df_raw.iloc[header_row_idx + 1], errors='coerce').notna().mean()
        if second_row_numeric_ratio < 0.3:
            data_start_row = header_row_idx + 2
            
    # 6. 组装最终数据
    df = df_raw.iloc[data_start_row:].copy()
    df.columns = final_headers
    df = df.reset_index(drop=True)
    
    # 🌟 新增：安全回退机制
    # 如果智能解析后，数据行数连1行都没有，说明猜错了，直接回退到默认读法！
    if len(df) == 0:
        df = pd.read_excel(file, sheet_name=sheet_name or 0)
        
    return df
# ========== 类型识别与清洗逻辑 ==========
TIME_KEYWORDS = ["date", "time", "日期", "时间", "年", "月", "日", "dt", "timestamp"]
ID_KEYWORDS = ["id", "编号", "序号", "学号", "工号"]

def detect_column_type(series: pd.Series, col_name: str = ""):
    # 🌟 新增：如果传入的是多列 DataFrame，强行取第一列
    if isinstance(series, pd.DataFrame):
        if series.shape[1] > 0:
            series = series.iloc[:, 0]
        else:
            return "empty"

    s = series.dropna()
    if len(s) == 0: return "empty"
    if pd.api.types.is_numeric_dtype(s):
        if s.nunique() / len(s) > 0.9 and any(k in str(col_name).lower() for k in ID_KEYWORDS):
            return "id"
        return "numeric"
    numeric_ratio = pd.to_numeric(s, errors="coerce").notna().mean()
    if numeric_ratio > 0.8: return "numeric"
    name_hint = any(kw in str(col_name).lower() for kw in TIME_KEYWORDS)
    has_sep = s.astype(str).str.contains(r"[-/:年月日]", regex=True).mean() > 0.5
    if name_hint or has_sep:
        dt_ratio = pd.to_datetime(s, errors="coerce").notna().mean()
        if dt_ratio > 0.8: return "datetime"
    unique_ratio = s.nunique() / len(s)
    if s.nunique() <= 50 or unique_ratio < 0.5: return "categorical"
    return "text"  
def analyze_columns(df):
    return {c: detect_column_type(df[c], c) for c in df.columns}

def clean_dataframe(df, drop_dup, drop_na_rows, fill_na_num):
    df = df.copy()
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    if drop_dup: df = df.drop_duplicates()
    if drop_na_rows: df = df.dropna()
    if fill_na_num:
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                df[c] = df[c].fillna(df[c].mean())
    return df

def force_convert_numeric(df, col_types):
    df = df.copy()
    for col, t in col_types.items():
        if t == "numeric":
            df[col] = df[col].astype(str).str.extract(r'(-?\d+\.?\d*)')[0]
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df
# ========== 自动图表推荐 ==========
def auto_recommend_charts(df, col_types):
    charts = []
    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    cat_cols = [c for c, t in col_types.items() if t == "categorical" and c != "数据周期"]
    date_cols = [c for c, t in col_types.items() if t == "datetime"]
    has_period = "数据周期" in df.columns

    # 1) 多表对比：分组柱状图
    if has_period and cat_cols and numeric_cols:
        c, n = cat_cols[0], numeric_cols[0]
        try:
            top_cats = df[c].value_counts().nlargest(10).index
            agg = df[df[c].isin(top_cats)].groupby(["数据周期", c])[n].mean().reset_index()
            fig = px.bar(agg, x=c, y=n, color="数据周期", barmode="group", title=f"各 {c} 的 {n} 周期对比", text_auto=".2f")
            fig.update_layout(height=400, xaxis_tickangle=-30, margin=dict(l=20, r=20, t=50, b=80))
            charts.append((f"{c} 周期对比柱状图", fig))
        except Exception: pass

    # 2) 多表对比：多线趋势图
    if has_period and date_cols and numeric_cols:
        d, n = date_cols[0], numeric_cols[0]
        try:
            temp = df.dropna(subset=[d, n]).copy()
            temp[d] = pd.to_datetime(temp[d])
            temp = temp.sort_values(d)
            fig = px.line(temp, x=d, y=n, color="数据周期", markers=True, title=f"{n} 趋势多线对比图")
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
            charts.append((f"{n} 趋势多线对比图", fig))
        except Exception: pass

    # 3) 数值列直方图
    for col in numeric_cols[:1]:
        fig = px.histogram(df, x=col, color="数据周期" if has_period else None, nbins=20, title=f"{col} 分布")
        fig.update_layout(bargap=0.1, height=350, margin=dict(l=20, r=20, t=40, b=20))
        charts.append((f"{col} 分布直方图", fig))

    # 4) 单表柱状图
    if not has_period and cat_cols and numeric_cols:
        c, n = cat_cols[0], numeric_cols[0]
        try:
            agg = df.groupby(c)[n].mean().reset_index().sort_values(n, ascending=False).head(15)
            fig = px.bar(agg, x=c, y=n, title=f"各 {c} 的平均 {n}", text_auto=".2f")
            fig.update_layout(height=350, xaxis_tickangle=-30, margin=dict(l=20, r=20, t=40, b=80))
            charts.append((f"{c} 对比 {n} 柱状图", fig))
        except Exception: pass

    # 5) 散点图
    if len(numeric_cols) >= 2:
        x, y = numeric_cols[0], numeric_cols[1]
        try:
            fig = px.scatter(df, x=x, y=y, color="数据周期" if has_period else None, title=f"{x} 与 {y} 的关系", opacity=0.7)
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            charts.append((f"{x}-{y} 散点图", fig))
        except Exception: pass
    return charts
# ========== AI 逻辑 ==========
def build_data_summary(df, col_types, charts):
    parts = [f"数据集规模：{df.shape[0]} 行 × {df.shape[1]} 列", f"列类型：{col_types}"]
    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    cat_cols = [c for c, t in col_types.items() if t == "categorical" and c != "数据周期"]

    if "数据周期" in df.columns:
        periods = df["数据周期"].unique().tolist()
        parts.append(f"【特别注意】多期对比数据，周期有：{periods}")
        if numeric_cols:
            pivot = df.groupby("数据周期")[numeric_cols].mean().round(2).to_string()
            parts.append(f"各周期指标均值对比：\n{pivot}")
            if len(periods) == 2:
                p1, p2 = periods[0], periods[1]
                try:
                    change = ((df[df["数据周期"]==p2][numeric_cols].mean() - df[df["数据周期"]==p1][numeric_cols].mean()) / df[df["数据周期"]==p1][numeric_cols].mean() * 100).round(2)
                    parts.append(f"{p2} 相比 {p1} 的变化率(%)：\n{change.to_string()}")
                except Exception: pass
    if numeric_cols: parts.append(f"整体数值统计：\n{df[numeric_cols].describe().round(2).to_string()}")
    for c in cat_cols[:3]:
        try: parts.append(f"分类列「{c}」Top5：{df[c].value_counts().head(5).to_dict()}")
        except Exception: pass
    miss = df.isnull().sum(); miss = miss[miss > 0]
    parts.append(f"缺失值：{miss.to_dict() if len(miss) else '无'}")
    return "\n".join(parts)

SYSTEM_PROMPT = """你是一位面向非技术用户的资深数据分析师。请基于数据摘要输出报告：
## 1. 数据整体概况
## 2. 关键发现（列出2-4条，引用具体数字。如果包含“数据周期”，重点进行【横向对比分析】，指出环比变化率，并使用“环比上升/下降”等业务词汇）
## 3. 异常与风险提示
## 4. 建议
要求：禁止编造，语言通俗。"""

def call_llm_analysis(api_key, model, data_summary):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"分析数据：\n{data_summary}"}], "temperature": 0.3}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e: return f"❌ AI 调用失败：{e}"

def call_llm_chat(api_key, model, data_summary, chat_history, user_query):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": f"你是一位资深数据分析师。这是当前数据集的核心摘要：\n\n{data_summary}\n\n请结合上述数据，用通俗易懂的语言回答用户的问题。不要编造数据中没有的信息。"}]
    for msg in chat_history: messages.append(msg)
    messages.append({"role": "user", "content": user_query})
    payload = {"model": model, "messages": messages, "temperature": 0.3}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e: return f"❌ 对话调用失败：{e}"

def fig_to_base64(fig):
    try:
        img = fig.to_image(format="png", width=900, height=450, scale=2)
        return base64.b64encode(img).decode()
    except Exception: return None
    # ========== 侧边栏设置 ==========
st.sidebar.header("⚙️ 设置")
try:
    default_key = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    default_key = ""

api_key = st.sidebar.text_input("DeepSeek API Key", type="password", value=default_key, help="在 platform.deepseek.com 获取").strip()
model_name = st.sidebar.selectbox("选择模型", ["deepseek-chat", "deepseek-reasoner"])
enable_chat = st.sidebar.toggle("开启 AI 多轮对话（探讨数据）", value=False, help="开启后，可以在分析报告下方继续向 AI 提问")
uploaded_files = st.sidebar.file_uploader("上传数据文件（可多选进行对比）", type=["xlsx", "xls", "csv"], accept_multiple_files=True)
# ✨ 新增：内置示例数据选择器
st.sidebar.markdown("---")
st.sidebar.subheader("✨ 没有数据？试试内置示例")
demo_option = st.sidebar.selectbox(
    "选择体验场景",
    ["不使用示例", "📈 电商三个月销售对比", "🎓 学生期末成绩分析", "🌐 网站流量趋势分析"]
)
st.sidebar.divider()
st.sidebar.header("🧹 数据清洗（可选）")
drop_dup = st.sidebar.checkbox("删除完全重复行", value=False)
drop_na_rows = st.sidebar.checkbox("删除含缺失值的行", value=False)
fill_na_num = st.sidebar.checkbox("数值列缺失值填均值", value=False)
st.sidebar.caption("💡 提示：多文件对比请确保各表字段名（列名）一致，系统会以文件名作为周期标签。")

# ========== 主流程与文件读取 ==========
st.title("📊 智析 — 智能数据可视化助手")

if not uploaded_files and demo_option == "不使用示例":
    st.info("👈 请在左侧边栏上传 1 个或多个 Excel/CSV 文件开始使用。")
    st.markdown("💡 **或者，点击左侧边栏的『试试内置示例』直接体验！**")
    st.stop()

# ========== 多文件读取与合并 ==========
try:
    if demo_option != "不使用示例":
        # 🌟 如果选了示例，直接生成数据，不读文件
        if demo_option == "📈 电商三个月销售对比":
            df_jan = pd.DataFrame({
                "日期": pd.date_range("2024-01-01", periods=20, freq="D").astype(str),
                "商品类别": np.random.choice(["电子产品", "办公用品", "家居家具"], 20),
                "销售员": np.random.choice(["张三", "李四", "王五"], 20),
                "销售额": np.random.randint(1000, 8000, 20),
                "利润": np.random.randint(200, 3000, 20),
                "数据周期": "1月"
            })
            df_feb = pd.DataFrame({
                "日期": pd.date_range("2024-02-01", periods=20, freq="D").astype(str),
                "商品类别": np.random.choice(["电子产品", "办公用品", "家居家具"], 20),
                "销售员": np.random.choice(["张三", "李四", "王五"], 20),
                "销售额": np.random.randint(1500, 9000, 20),
                "利润": np.random.randint(300, 3500, 20),
                "数据周期": "2月"
            })
            df_mar = pd.DataFrame({
                "日期": pd.date_range("2024-03-01", periods=20, freq="D").astype(str),
                "商品类别": np.random.choice(["电子产品", "办公用品", "家居家具"], 20),
                "销售员": np.random.choice(["张三", "李四", "王五"], 20),
                "销售额": np.random.randint(2000, 12000, 20),
                "利润": np.random.randint(500, 5000, 20),
                "数据周期": "3月"
            })
            # 故意造一个异常大单（15万），看 AI 能不能发现
            df_mar.loc[0, "销售额"] = 150000 
            df_mar.loc[0, "利润"] = 40000
            df_raw = pd.concat([df_jan, df_feb, df_mar], ignore_index=True)
            
        elif demo_option == "🎓 学生期末成绩分析":
            df_raw = pd.DataFrame({
                "班级": np.random.choice(["高一1班", "高一2班", "高一3班"], 50),
                "姓名": [f"学生_{i}" for i in range(50)],
                "语文": np.random.randint(60, 100, 50),
                "数学": np.random.randint(50, 100, 50),
                "英语": np.random.randint(60, 100, 50),
                "总分": 0
            })
            df_raw["总分"] = df_raw["语文"] + df_raw["数学"] + df_raw["英语"]
            # 故意造几个缺失值和异常值
            df_raw.loc[2, "数学"] = np.nan
            df_raw.loc[5, "总分"] = 999
            
        elif demo_option == "🌐 网站流量趋势分析":
            dates = pd.date_range("2024-01-01", periods=60, freq="D")
            df_raw = pd.DataFrame({
                "日期": dates.astype(str),
                "访问量(PV)": np.random.randint(1000, 5000, 60) + np.arange(60) * 50,
                "独立访客(UV)": np.random.randint(500, 2000, 60),
                "转化率(%)": np.random.uniform(1.5, 5.5, 60).round(2)
            })
            
        # 伪造数据签名，强制刷新
        file_sig = f"demo_{demo_option}"
        
    else:
        # 原来的多文件读取逻辑
        dfs = []
        for file in uploaded_files:
            label = file.name.rsplit('.', 1)[0] 
            sheet_name = 0
            if file.name.lower().endswith((".xlsx", ".xls")) and len(uploaded_files) == 1:
                xls = pd.ExcelFile(file)
                if len(xls.sheet_names) > 1: sheet_name = st.sidebar.selectbox("选择工作表", xls.sheet_names)
                file.seek(0)
            temp_df = load_single_file(file, sheet_name)
            temp_df.columns = temp_df.columns.str.strip()
            if len(uploaded_files) > 1: temp_df["数据周期"] = label
            dfs.append(temp_df)
        df_raw = dfs[0] if len(dfs)== 1 else pd.concat(dfs, ignore_index=True, sort=False)
        file_sig = "|".join([f.name for f in uploaded_files])

except Exception as e:
    st.error(f"文件读取或合并失败：{e}"); st.stop()
if df_raw.empty:
    st.warning("文件为空或无可读数据。"); st.stop()

df = clean_dataframe(df_raw, drop_dup, drop_na_rows, fill_na_num)
col_types = analyze_columns(df)
df = force_convert_numeric(df, col_types)

# 数据签名重置缓存
file_sig = "|".join([f.name for f in uploaded_files])
sig = f"{file_sig}|{df.shape}|{list(df.columns)}|{drop_dup}{drop_na_rows}{fill_na_num}"
if st.session_state.df_sig != sig:
    st.session_state.df_sig = sig
    st.session_state.auto_charts = auto_recommend_charts(df, col_types)
    st.session_state.manual_fig = None
    st.session_state.ai_result = ""
    st.session_state.chat_history = [] 

# 顶部指标
c1, c2, c3, c4 = st.columns(4)
c1.metric("总行数", df.shape[0]); c2.metric("总列数", df.shape[1])
c3.metric("数值列", sum(1 for t in col_types.values() if t == "numeric"))
c4.metric("分类列", sum(1 for t in col_types.values() if t == "categorical"))
tab1, tab2, tab3, tab4 = st.tabs(["📋 数据预览", "📈 自动图表", "🛠️ 自定义图表", "🤖 AI 分析 & 导出"])

with tab1:
    st.subheader("数据预览（前 20 行）")
    st.dataframe(df.head(20), use_container_width=True)
    st.subheader("列类型识别")
    type_df = pd.DataFrame({"列名": list(col_types.keys()), "识别类型": list(col_types.values()),
                            "缺失值": [df[c].isnull().sum() for c in df.columns], "唯一值数": [df[c].nunique() for c in df.columns]})
    st.dataframe(type_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("系统自动推荐图表")
    if st.button("🔄 重新生成", key="btn_auto"):
        st.session_state.auto_charts = auto_recommend_charts(df, col_types)
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
    all_cols = list(df.columns)
    c1, c2, c3 = st.columns(3)
    x_sel = c1.selectbox("X 轴字段", all_cols, key="x_sel")
    y_sel = c2.selectbox("Y 轴字段", all_cols, key="y_sel")
    chart_type = c3.selectbox("图表类型", ["柱状图", "折线图", "散点图", "直方图", "箱线图", "饼图"], key="chart_type")

    if st.button("生成自定义图表", type="primary"):
        try:
            has_period = "数据周期" in df.columns
            color_col = "数据周期" if has_period else None
            if chart_type == "柱状图":
                if has_period and x_sel != "数据周期":
                    agg = df.groupby(["数据周期", x_sel])[y_sel].mean().reset_index().sort_values(y_sel, ascending=False).head(20)
                    fig = px.bar(agg, x=x_sel, y=y_sel, color="数据周期", barmode="group", title=f"{x_sel} 对比 {y_sel}")
                else:
                    agg = df.groupby(x_sel)[y_sel].mean().reset_index().sort_values(y_sel, ascending=False).head(20)
                    fig = px.bar(agg, x=x_sel, y=y_sel, title=f"{x_sel} 对比 {y_sel}")
            elif chart_type == "折线图":
                temp = df.dropna(subset=[x_sel, y_sel]).copy()
                try: temp[x_sel] = pd.to_datetime(temp[x_sel]); temp = temp.sort_values(x_sel)
                except Exception: pass
                fig = px.line(temp, x=x_sel, y=y_sel, color=color_col, markers=True)
            elif chart_type == "散点图": fig = px.scatter(df, x=x_sel, y=y_sel, color=color_col, opacity=0.7)
            elif chart_type == "直方图": fig = px.histogram(df, x=x_sel, color=color_col, nbins=20)
            elif chart_type == "箱线图": fig = px.box(df, x=x_sel, y=y_sel, color=color_col)
            elif chart_type == "饼图":
                vc = df[x_sel].value_counts().head(10).reset_index(); vc.columns = [x_sel, "count"]
                fig = px.pie(vc, names=x_sel, values="count")
            fig.update_layout(height=450)
            st.session_state.manual_fig = fig
            st.session_state.manual_title = f"自定义｜{chart_type}：{x_sel} × {y_sel}"
        except Exception as e: st.error(f"生成失败：{e}")
    if st.session_state.manual_fig is not None:
        st.markdown(f"**{st.session_state.manual_title}**")
        st.plotly_chart(st.session_state.manual_fig, use_container_width=True, key="manual_chart")

with tab4:
    st.subheader("🤖 AI 智能分析")
    if not api_key: 
        st.info("请在侧边栏填入 DeepSeek API Key。")
    else:
        if st.button("生成初始分析报告", type="primary", key="btn_ai"):
            with st.spinner("AI 正在解析数据..."):
                summary = build_data_summary(df, col_types, st.session_state.auto_charts)
                st.session_state.ai_result = call_llm_analysis(api_key, model_name, summary)
        
        if st.session_state.ai_result: 
            st.markdown(st.session_state.ai_result)
            
            if enable_chat:
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
                            with st.spinner("思考中..."):
                                summary = build_data_summary(df, col_types, st.session_state.auto_charts)
                                recent_history = st.session_state.chat_history[-10:] 
                                ai_response = call_llm_chat(api_key, model_name, summary, recent_history[:-1], user_query)
                                st.markdown(ai_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                        st.rerun()
        else: 
            st.caption("点击上方按钮生成分析结论。")

    st.divider()
    st.subheader("📥 导出 Markdown 报告")
    
    if st.button("生成并下载报告"):
        md = StringIO()
        md.write("# 智析 — 数据分析报告\n\n")
        
        # 修复报错
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
st.caption("智析 v1.8｜多轮对话 & 示例数据版")
