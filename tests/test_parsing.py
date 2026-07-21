"""文档解析单元测试。"""

from pathlib import Path

import pytest

from src.exceptions import BadRequestException, UnsupportedFormatException
from src.services.parsing import parse_file


class TestParsePlain:
    def test_parse_markdown(self, sample_md_file):
        doc = parse_file(sample_md_file)
        assert "测试文档" in doc.full_text
        assert len(doc.pages) == 1
        assert doc.pages[0].page is None

    def test_parse_txt(self, sample_txt_file):
        doc = parse_file(sample_txt_file)
        assert "纯文本" in doc.full_text

    def test_parse_txt_utf8_bom(self, temp_dir):
        p = temp_dir / "bom.txt"
        p.write_bytes("\ufeff带BOM的内容".encode("utf-8-sig"))
        assert "带BOM的内容" in parse_file(str(p)).full_text

    def test_empty_file_raises(self, temp_dir):
        p = temp_dir / "empty.txt"
        p.write_text("   \n", encoding="utf-8")
        with pytest.raises(BadRequestException):
            parse_file(str(p))

    def test_unsupported_format(self, temp_dir):
        p = temp_dir / "data.bin"
        p.write_bytes(b"\x00\x01")
        with pytest.raises(UnsupportedFormatException):
            parse_file(str(p))


class TestParseDocx:
    def test_parse_docx(self, temp_dir):
        from docx import Document

        path = temp_dir / "notes.docx"
        doc = Document()
        doc.add_heading("傅里叶变换", level=1)
        doc.add_paragraph("连续时间傅里叶变换的定义。")
        doc.save(str(path))

        parsed = parse_file(str(path))
        assert "傅里叶变换" in parsed.full_text
        assert "连续时间" in parsed.full_text

    def test_docx_header_footer_and_table_order(self, temp_dir):
        from docx import Document

        path = temp_dir / "hf.docx"
        doc = Document()
        section = doc.sections[0]
        section.header.paragraphs[0].text = "课程页眉：信号与系统"
        section.footer.paragraphs[0].text = "页脚版权"
        doc.add_paragraph("段落甲")
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "表左"
        table.rows[0].cells[1].text = "表右"
        doc.add_paragraph("段落乙")
        doc.save(str(path))

        text = parse_file(str(path)).full_text
        assert "课程页眉：信号与系统" in text
        assert "页脚版权" in text
        assert "段落甲" in text
        assert "表左" in text and "表右" in text
        assert "段落乙" in text
        # 表格夹在两段之间，不应整段挪到文末
        assert text.index("段落甲") < text.index("表左") < text.index("段落乙")

    def test_docx_textbox(self, temp_dir):
        from docx import Document
        from docx.oxml import parse_xml

        path = temp_dir / "txbx.docx"
        doc = Document()
        doc.add_paragraph("正文段落")

        # 最小合法文本框片段（含 VML 命名空间）
        p = doc.add_paragraph()
        r = p.add_run()
        pict = parse_xml(
            '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            ' xmlns:v="urn:schemas-microsoft-com:vml">'
            "<v:shape><v:textbox>"
            "<w:txbxContent><w:p><w:r><w:t>文本框里的卷积定理</w:t></w:r></w:p></w:txbxContent>"
            "</v:textbox></v:shape></w:pict>"
        )
        r._r.append(pict)
        doc.save(str(path))

        text = parse_file(str(path)).full_text
        assert "正文段落" in text
        assert "文本框里的卷积定理" in text


class TestParsePptx:
    def test_parse_pptx(self, temp_dir):
        from pptx import Presentation

        path = temp_dir / "slides.pptx"
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "采样定理"
        slide.placeholders[1].text = "奈奎斯特频率 fs/2"
        prs.save(str(path))

        parsed = parse_file(str(path))
        assert "采样定理" in parsed.full_text
        assert parsed.pages[0].page == 1

    def test_pptx_notes_and_table(self, temp_dir):
        from pptx import Presentation
        from pptx.util import Inches

        path = temp_dir / "notes_table.pptx"
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # blank
        slide.shapes.title.text = "卷积"
        rows, cols = 2, 2
        table = slide.shapes.add_table(rows, cols, Inches(1), Inches(2), Inches(4), Inches(1)).table
        table.cell(0, 0).text = "时域"
        table.cell(0, 1).text = "频域"
        table.cell(1, 0).text = "卷积"
        table.cell(1, 1).text = "相乘"
        notes = slide.notes_slide.notes_text_frame
        notes.text = "讲义备注：对偶关系"
        prs.save(str(path))

        parsed = parse_file(str(path))
        text = parsed.full_text
        assert "卷积" in text
        assert "时域" in text and "频域" in text
        assert "讲义备注：对偶关系" in text
        assert "[备注]" in text
