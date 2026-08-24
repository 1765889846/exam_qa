"""上传解析：产品支持的格式（MD/TXT/DOCX/PPTX）+ 拒答空文件。"""

import pytest

from src.exceptions import BadRequestException, UnsupportedFormatException
from src.services.parsing import parse_file


class TestParsePlain:
    def test_parse_markdown(self, sample_md_file):
        doc = parse_file(sample_md_file)
        assert "测试文档" in doc.full_text
        assert len(doc.pages) == 1

    def test_parse_txt(self, sample_txt_file):
        assert "纯文本" in parse_file(sample_txt_file).full_text

    def test_empty_and_unsupported(self, temp_dir):
        empty = temp_dir / "empty.txt"
        empty.write_text("   \n", encoding="utf-8")
        with pytest.raises(BadRequestException):
            parse_file(str(empty))
        bad = temp_dir / "data.bin"
        bad.write_bytes(b"\x00\x01")
        with pytest.raises(UnsupportedFormatException):
            parse_file(str(bad))


class TestParseOffice:
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

    def test_parse_pptx_fallback_without_converter(self, temp_dir, monkeypatch):
        """无 LibreOffice/PowerPoint 时必须回退 python-pptx 提取。"""
        from pptx import Presentation
        from src.services import parsing

        path = temp_dir / "fallback.pptx"
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "回退测试"
        prs.save(str(path))

        monkeypatch.setattr(parsing, "_convert_pptx_to_pdf", lambda p: None)
        parsed = parse_file(str(path))
        assert "回退测试" in parsed.full_text
        assert parsed.pages[0].page == 1
