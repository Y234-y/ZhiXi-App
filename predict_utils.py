# predict_utils.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def create_forecast_chart(df, time_col, value_col, periods=7):
    try:
        temp = df.copy()
        temp[time_col] = pd.to_datetime(temp[time_col])
        # 按时间聚合求和
        temp = temp.groupby(time_col)[value_col].sum().reset_index()
        temp = temp.sort_values(time_col)
        
        if len(temp) < 5: 
            return None, "数据量太少，至少需要 5 个数据点"
        
        # 转换索引用于拟合
        x = np.arange(len(temp))
        y = temp[value_col].values
        
        # 1. 线性拟合预测 (核心逻辑)
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        
        future_x = np.arange(len(temp), len(temp) + periods)
        future_y = p(future_x)
        
        # 2. 计算标准差作为置信区间 (让线条变粗，有阴影)
        std_err = np.std(y - p(x)) # 残差的标准差
        upper_bound = future_y + std_err
        lower_bound = future_y - std_err
        
        # 构造未来的日期
        last_date = temp[time_col].max()
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=periods)
        
        # 3. 开始画图
        fig = go.Figure()
        
        # 历史真实数据 (细线，带点)
        fig.add_trace(go.Scatter(
            x=temp[time_col], y=temp[value_col], 
            mode='lines+markers', name='历史真实数据',
            line=dict(color='#004b87', width=2)
        ))
        
        # 预测虚线 (粗线，高亮)
        fig.add_trace(go.Scatter(
            x=future_dates, y=future_y, 
            mode='lines+markers', name='AI 趋势预测',
            line=dict(color='#ff7f0e', width=3, dash='dash')
        ))
        
        # 🌟 王炸：预测置信区间 (半透明阴影)
        fig.add_trace(go.Scatter(
            x=list(future_dates) + list(future_dates)[::-1],
            y=list(upper_bound) + list(lower_bound)[::-1],
            fill='toself',
            fillcolor='rgba(255, 127, 14, 0.15)', # 半透明橙色
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='预测误差范围'
        ))
        
        fig.update_layout(
            title=f"AI 趋势预测：未来 {periods} 天 {value_col} 走势",
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig, "预测成功"
    except Exception as e:
        return None, f"预测失败：{e}"
