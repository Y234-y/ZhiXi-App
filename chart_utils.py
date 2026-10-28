# chart_utils.py
import plotly.express as px

def auto_recommend_charts(df, col_types):
    charts = []
    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    cat_cols = [c for c, t in col_types.items() if t == "categorical" and c != "数据周期"]
    date_cols = [c for c, t in col_types.items() if t == "datetime"]
    has_period = "数据周期" in df.columns

    if has_period and cat_cols and numeric_cols:
        c, n = cat_cols[0], numeric_cols[0]
        try:
            top_cats = df[c].value_counts().nlargest(10).index
            agg = df[df[c].isin(top_cats)].groupby(["数据周期", c])[n].mean().reset_index()
            fig = px.bar(agg, x=c, y=n, color="数据周期", barmode="group", title=f"各 {c} 的 {n} 周期对比", text_auto=".2f")
            fig.update_layout(height=400, xaxis_tickangle=-30, margin=dict(l=20, r=20, t=50, b=80))
            charts.append((f"{c} 周期对比柱状图", fig))
        except Exception: pass

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

    for col in numeric_cols[:1]:
        fig = px.histogram(df, x=col, color="数据周期" if has_period else None, nbins=20, title=f"{col} 分布")
        fig.update_layout(bargap=0.1, height=350, margin=dict(l=20, r=20, t=40, b=20))
        charts.append((f"{col} 分布直方图", fig))

    if not has_period and cat_cols and numeric_cols:
        c, n = cat_cols[0], numeric_cols[0]
        try:
            agg = df.groupby(c)[n].mean().reset_index().sort_values(n, ascending=False).head(15)
            fig = px.bar(agg, x=c, y=n, title=f"各 {c} 的平均 {n}", text_auto=".2f")
            fig.update_layout(height=350, xaxis_tickangle=-30, margin=dict(l=20, r=20, t=40, b=80))
            charts.append((f"{c} 对比 {n} 柱状图", fig))
        except Exception: pass

    if len(numeric_cols) >= 2:
        x, y = numeric_cols[0], numeric_cols[1]
        try:
            fig = px.scatter(df, x=x, y=y, color="数据周期" if has_period else None, title=f"{x} 与 {y} 的关系", opacity=0.7)
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            charts.append((f"{x}-{y} 散点图", fig))
        except Exception: pass
    return charts
