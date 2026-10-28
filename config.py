# config.py

# 1. 主题 CSS 样式
CUSTOM_CSS = """
<style>
    .stApp { background-color: #f7f9f8; }
    [data-testid="stSidebar"] { background-color: #e8f0ef; border-right: 2px solid #d0dedb; }
    h1, h2, h3 { color: #004b87 !important; font-family: "STSong", "SimSun", "Microsoft YaHei", serif; font-weight: bold; }
    .stButton>button { background: linear-gradient(135deg, #004b87, #0066cc); color: white; border-radius: 8px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stPlotlyChart { box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-radius: 10px; padding: 10px; background-color: white; }
    /* 手机端指标卡两列排布 */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.5rem !important; }
        [data-testid="stHorizontalBlock"] > div { width: calc(50% - 0.25rem) !important; flex: none !important; }
        [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    }
</style>
"""

# 2. 通用版 Prompt（用于 AIGC 赛、成绩表等）
PROMPT_GENERAL = """你是一位面向非技术用户的资深数据分析师。请基于数据摘要输出报告：
## 1. 数据整体概况
## 2. 关键发现（列出2-4条，引用具体数字。如果包含“数据周期”，重点进行【横向对比分析】，指出环比变化率）
## 3. 异常与风险提示
## 4. 建议
要求：禁止编造，语言通俗。"""

# 3. 电商专属版 Prompt（用于电商赛、店铺诊断）
PROMPT_ECOMMERCE = """你是一位资深的电商数据分析师（业务专家）。请基于用户提供的数据摘要，输出通俗易懂的电商业务诊断报告，严格遵循以下结构：
## 1. 店铺整体概况
- 一句话说明当前周期内的总销售额、整体转化率和平均客单价。
- 重点指出数据质量（如：是否有退款率异常、推广花费占比是否健康）。
## 2. 核心业务发现（含环比对比）
- **趋势与类目**：指出哪个类目是利润奶牛，哪个类目在拖后腿。重点指出环比上升或下降的趋势。
- **流量与转化**：分析不同推广渠道的 ROI（投入产出比），指出哪里烧钱快但没效果。
- **退款与风险**：如果退款金额偏高，必须单独点名并提示风险。
## 3. 运营优化建议
- 针对发现的异常，给出 2-3 条切实可行的电商运营建议。
要求：禁止编造，必须使用电商行业术语（如：UV、ROI、转化率、客单价）。"""
