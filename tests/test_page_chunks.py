"""PDF 按页分块：chunk 携带 page 元数据。"""

from src.services.ingestion import _chunk_document
from src.services.parsing import ParsedDocument, ParsedPage


class TestPageChunking:
    def test_chunks_carry_page_number(self):
        parsed = ParsedDocument([
            ParsedPage(page=1, text="第一页内容。" * 30),
            ParsedPage(page=2, text="第二页内容。" * 30),
        ])
        chunks = _chunk_document(parsed, chunk_size=100, chunk_overlap=10)
        pages = {p for _, p in chunks}
        assert 1 in pages
        assert 2 in pages

    def test_plain_text_no_page(self):
        parsed = ParsedDocument([ParsedPage(page=None, text="无页码文档。" * 10)])
        chunks = _chunk_document(parsed, chunk_size=200, chunk_overlap=20)
        assert all(p is None for _, p in chunks)
