"""单元测试：文本分块逻辑。"""

from src.services.ingestion import _split_text


class TestSplitText:
    """_split_text 纯逻辑测试，无外部依赖。"""

    def test_short_text_no_split(self):
        """短文本不会被切分。"""
        text = "这是一段简短的测试文本。"
        chunks = _split_text(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self):
        """空文本返回空列表。"""
        assert _split_text("") == []
        assert _split_text("   \n\n  ") == []

    def test_split_by_paragraph(self):
        """段落边界处切分。"""
        text = "第一段内容。" * 30 + "\n\n" + "第二段内容。" * 30
        chunks = _split_text(text, chunk_size=100, chunk_overlap=10)
        assert len(chunks) >= 2

    def test_long_paragraph_forced_split(self):
        """超长段落（无段落边界）会被强制切分。"""
        # 一个很长的句子，超过 chunk_size
        text = "A" * 1200
        chunks = _split_text(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 2
        # 总覆盖应该接近原文长度
        total = sum(len(c) for c in chunks)
        assert total >= 1100  # 允许少量丢失

    def test_overlap_presence(self):
        """相邻 chunk 之间有重叠内容。"""
        text = "信号" * 200 + "\n\n" + "系统" * 200
        chunks = _split_text(text, chunk_size=100, chunk_overlap=20)
        if len(chunks) >= 2:
            # 第一个 chunk 的末尾应该出现在第二个 chunk 开头附近
            tail = chunks[0][-20:]
            assert tail in chunks[1]

    def test_chunks_not_exceed_size(self):
        """每个 chunk 长度不超过 chunk_size（或略微超出因单词边界）。"""
        text = "傅里叶变换是信号处理的核心工具。" * 50
        chunks = _split_text(text, chunk_size=200, chunk_overlap=30)
        for c in chunks:
            # 允许略微超出（因为句子边界不可切分时保留完整句子）
            assert len(c) <= 250  # chunk_size + 缓冲

    def test_chinese_text(self):
        """中文文本正常分块。"""
        text = "傅里叶变换是一种将信号从时域转换到频域的数学工具。" * 20
        chunks = _split_text(text, chunk_size=300, chunk_overlap=30)
        assert len(chunks) >= 1
        for c in chunks:
            assert len(c) > 0
