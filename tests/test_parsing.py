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
