# report_utils.py
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io

def generate_word_report(df, ai_text, chart_fig):
    """
    生成高级定制的 Word 报告
    """
    doc = Document()
    
    # 1. 添加大标题 (居中，加粗，大号字体)
    title = doc.add_heading('智析 DataSight - 商业数据诊断报告', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = None # 重置为默认黑色
    
    doc.add_paragraph("=" * 50) # 分割线
    
    # 2. 插入 AI 分析结论
    doc.add_heading('一、 核心业务洞察', level=1)
    p = doc.add_paragraph(ai_text)
    p.style.font.size = Pt(11)
    
    doc.add_paragraph("\n")
    
    # 3. 插入图表图片
    if chart_fig:
        doc.add_heading('二、 核心数据图表', level=1)
        try:
            # 利用 kaleido 将 Plotly 图表转为静态图片
            img_bytes = chart_fig.to_image(format="png", width=800, height=450, scale=2)
            img_stream = io.BytesIO(img_bytes)
            doc.add_picture(img_stream, width=Inches(6.0))
            # 图表居中
            last_paragraph = doc.paragraphs[-1] 
            last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception as e:
            doc.add_paragraph(f"（图表生成失败: {e}）")
            
    doc.add_paragraph("\n")
    doc.add_paragraph("注：本报告由智析 AI 引擎自动生成，数据计算结果绝对真实。")
    
    # 4. 保存到内存并返回
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
