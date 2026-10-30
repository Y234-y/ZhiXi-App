# business_rules.py

# 业务指标字典库：定义不同行业的核心指标、预警阈值和建议
BUSINESS_RULES = {
    "电商运营": {
        "keywords": ["退款", "退货", "销售额", "转化率", "UV", "客单价", "GMV", "推广花费"],
        "metrics": {
            "退款/退货率": {"keywords": ["退款", "退货"], "red_line": 0.1, "advice": "退款率过高，立即核查商品详情页是否有夸大宣传，或物流包装是否存在破损问题。"},
            "转化率": {"keywords": ["转化"], "red_line": 0.02, "advice": "转化率跌破 2% 警戒线，建议立刻检查竞品价格，优化主图与详情页，或排查是否有差评置顶。"},
            "投放ROI": {"keywords": ["推广", "花费", "ROI"], "red_line": 2.0, "advice": "投产比（ROI）异常，立即暂停表现最差的直通车计划，优化投放人群标签。"}
        }
    },
    "门店零售": {
        "keywords": ["门店", "客单价", "进店", "营业额", "库存", "连带率"],
        "metrics": {
            "客单价": {"keywords": ["客单"], "red_line": 50, "advice": "客单价偏低，收银台可增加‘满减凑单’或口香糖等小商品连带销售。"},
            "滞销库存": {"keywords": ["库存", "库"], "red_line": 100, "advice": "部分商品库存过高，建议本周策划临期打折或作为会员赠品消化库存。"}
        }
    },
    "客服售后": {
        "keywords": ["投诉", "工单", "差评", "响应时间", "解决率"],
        "metrics": {
            "投诉/差评量": {"keywords": ["投诉", "差评"], "red_line": 5, "advice": "负面反馈激增，请主管安排专员回访，优先处理涉及产品质量的客诉，避免平台扣分。"},
            "响应时长": {"keywords": ["响应", "时间"], "red_line": 120, "advice": "平均响应时长超标，建议组长重新调整排班，高峰期增加客服在线人数。"}
        }
    }
}

def analyze_business_health(df):
    """
    业务诊断引擎：扫描数据集，识别业务场景，并输出健康度诊断报告
    """
    cols_str = " ".join([str(c) for c in df.columns])
    diagnosis = []
    detected_domain = "通用业务"

    # 1. 识别业务场景
    for domain, rules in BUSINESS_RULES.items():
        # 如果列名里命中了该行业的 2 个以上关键词，就认为属于该业务
        hit_count = sum(1 for kw in rules["keywords"] if kw in cols_str)
        if hit_count >= 2:
            detected_domain = domain
            diagnosis.append(f"系统识别当前业务场景为：【{domain}】")
            
            # 2. 动态计算指标并比对红线
            for metric_name, m_rule in rules["metrics"].items():
                target_cols = [c for c in df.columns if any(kw in str(c) for kw in m_rule["keywords"])]
                
                if target_cols:
                    col = target_cols[0]
                    try:
                        # 简单按均值或求和测算
                        val = df[col].mean() if "率" in str(col) else df[col].sum()
                        diagnosis.append(f"🔍 检测到关键指标【{metric_name}】，当前值为 {val:.2f}")
                        
                        # 触发预警
                        if "率" in str(col) and val > m_rule["red_line"] * 100: 
                            diagnosis.append(f"🚨 【业务红线预警】：{m_rule['advice']}")
                        elif "率" not in str(col) and val > m_rule["red_line"] * 10: 
                            diagnosis.append(f"🚨 【业务红线预警】：{m_rule['advice']}")
                    except:
                        pass
            break 
            
    if not diagnosis:
        diagnosis.append("系统识别当前业务场景为：通用数据分析。")
        
    return detected_domain, "\n".join(diagnosis)
