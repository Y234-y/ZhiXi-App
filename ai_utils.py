# ai_utils.py
import pandas as pd
import requests
import json
import base64

def build_data_summary(df, col_types):
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

def call_llm_analysis(api_key, model, data_summary, system_prompt):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"分析数据：\n{data_summary}"}], "stream": True, "temperature": 0.3}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60, stream=True)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str == "[DONE]": break
                    try:
                        content = json.loads(data_str)["choices"][0]["delta"].get("content", "")
                        if content: yield content
                    except json.JSONDecodeError: continue
    except Exception as e: yield f"❌ AI 调用失败：{e}"

def call_llm_chat(api_key, model, data_summary, chat_history, user_query, system_prompt):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # 🌟 核心修改：把数据摘要（data_summary）强行拼接到系统提示词里！
    full_system_prompt = f"""{system_prompt}
    
【当前数据集的核心摘要如下，请严格基于此回答，不要反问用户】：
{data_summary}
"""
    
    messages = [{"role": "system", "content": full_system_prompt}]  # 这里用 full_system_prompt
    
    for msg in chat_history: messages.append(msg)
    messages.append({"role": "user", "content": user_query})
    
    payload = {"model": model, "messages": messages, "temperature": 0.3, "stream": True}
    payload = {"model": model, "messages": messages, "temperature": 0.3, "stream": True}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60, stream=True)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str == "[DONE]": break
                    try:
                        content = json.loads(data_str)["choices"][0]["delta"].get("content", "")
                        if content: yield content
                    except json.JSONDecodeError: continue
    except Exception as e: yield f"❌ 对话调用失败：{e}"

def fig_to_base64(fig):
    try:
        img = fig.to_image(format="png", width=900, height=450, scale=2)
        return base64.b64encode(img).decode()
    except Exception: return None
