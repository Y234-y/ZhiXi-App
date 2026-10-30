# agent_utils.py
import requests
import json
import pandas as pd
import numpy as np
import re

def execute_ai_code(api_key, model, user_query, df):
    """
    让 AI 自己写 Pandas 代码并在本地执行
    """
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # 告诉 AI 当前的表结构，以及它必须遵守的规则
    cols_info = ", ".join([f"'{c}'({df[c].dtype})" for c in df.columns])
    system_prompt = f"""你是一个高级 Python 数据分析师。当前有一个名为 `df` 的 Pandas 数据框，列信息如下：
{cols_info}

请根据用户的问题，编写一段极其精简的 Python 代码来计算结果。
【严格规则】：
1. 不要使用 `import` 引入任何库（`pd` 和 `np` 已经可用）。
2. 不要使用 `print`，只需将最终的计算结果（如一个数字、一个列表、或一个小表格）赋值给变量 `result`。
3. 代码必须包含在 ```python 和 ``` 之间。不要输出任何解释性文字。
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.1
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        ai_reply = resp.json()["choices"][0]["message"]["content"]
        
        # 提取代码块
        code_match = re.search(r'```python\n(.*?)\n```', ai_reply, re.DOTALL)
        if not code_match: return "❌ AI 未能生成有效的代码。"
        
        code = code_match.group(1)
        
        # 🌟 核心：在安全的沙盒中执行代码
        local_vars = {"df": df, "pd": pd, "np": np}
        try:
            exec(code, {"__builtins__": {}}, local_vars)
            result = local_vars.get("result", "执行成功，但未返回结果。")
            return result
        except Exception as e:
            return f"❌ 代码执行报错：{e}，请尝试换个问法。"
            
    except Exception as e:
        return f"❌ 请求 AI 失败：{e}"
