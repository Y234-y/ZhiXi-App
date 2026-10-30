import pandas as pd
import requests
import json
import re
from business_rules import analyze_business_health  # 🌟 引入你的行业大脑

# 🌟 顶级“业务老油条”人设
SYSTEM_PROMPT = """你是一位极其资深的企业业务带教主管（老油条）。现在你要指导一位基层员工分析数据。

请严格遵循以下原则：
1. 绝对不要讲空话（如“加强管理”、“优化策略”）。
2. 必须结合系统给出的【业务规则引擎诊断结果】，优先处理高危预警项。
3. 如果数据包含周期，必须指出是上升还是下降。

请按以下结构输出：
## 📊 1. 业务大盘表现
（用 1-2 句话总结，比如：整体业绩向好，但某类产品退款率偏高。）

## 🚨 2. 当前致命隐患
（直接点名痛点，结合业务规则库给出的预警，输出 2 条最需要关注的问题。例如：“上个月退货率已触发 15% 的红色警报，可能是款式尺码偏差导致。”）

## ✅ 3. 给基层员工的行动清单（最重要！）
（直接给出下一步动作，例如：
1. 今天内：去后台把退货率超过 20% 的 3 个 SKU 挑出来，提交下架整改。
2. 本周内：针对华东区转化率下滑，联系美工修改主图。

## 💬 4. 向上汇报话术
（模拟员工口吻，写一段可以直接发在微信群里给老板的汇报）"""

def build_data_summary(df, col_types):
    parts = [f"数据集规模：{df.shape[0]} 行 × {df.shape[1]} 列"]
    cols_str = " ".join([str(c) for c in df.columns])
    
    # 🌟 1. 注入业务诊断引擎结果
    domain, diagnosis_text = analyze_business_health(df)
    parts.append(f"【系统业务规则引擎诊断结果】：\n{diagnosis_text}")

    # 🌟 2. 多期对比与环比计算
    if "数据周期" in df.columns:
        periods = df["数据周期"].unique().tolist()
        parts.append(f"【⏱️多期对比】包含周期：{periods}")
        num_cols = [c for c, t in col_types.items() if t == "numeric" and "名次" not in c]
        
        if len(periods) == 2 and num_cols:
            p1, p2 = periods[0], periods[1]
            try:
                pivot = df.groupby("数据周期")[num_cols].mean().round(2).to_string()
                parts.append(f"各周期核心均值对比：\n{pivot}")
                change = ((df[df["数据周期"]==p2][num_cols].mean() - df[df["数据周期"]==p1][num_cols].mean()) / df[df["数据周期"]==p1][num_cols].mean() * 100).round(2)
                parts.append(f"{p2} 相比 {p1} 的变化率(%)：\n{change.to_string()}")
            except: pass

    # 🌟 3. 基础统计
    num_cols = [c for c, t in col_types.items() if t == "numeric"]
    if num_cols:
        parts.append(f"整体数值均值：\n{df[num_cols].mean().round(2).to_string()}")
        
    return "\n".join(parts)

# 流式输出函数（保持不变）
def call_llm_chat(api_key, model, data_summary, chat_history, user_query, system_prompt):
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    full_system_prompt = f"{system_prompt}\n\n【当前数据集及业务规则摘要】：\n{data_summary}\n\n请严格基于上述数据回答，绝对不要反问用户。"
    
    messages = [{"role": "system", "content": full_system_prompt}]
    for msg in chat_history: messages.append(msg)
    messages.append({"role": "user", "content": user_query})
    
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
    except Exception as e:
        yield f"❌ AI 调用失败：{e}"
