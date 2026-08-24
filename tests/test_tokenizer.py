"""中文分词模块测试。"""

import pytest
from src.services.tokenizer import ChineseTokenizer, tokenize, _get_tokenizer, _cached_jieba_cut
from src.services import tokenizer as tokenizer_mod


class TestTokenizeFallback:
    """jieba 不可用时的回退行为测试。"""

    def test_empty_and_whitespace(self):
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_english_words(self):
        toks = tokenize("Hello World convolution")
        assert "hello" in toks
        assert "world" in toks
        assert "convolution" in toks

    def test_mixed_cjk_and_english(self):
        toks = tokenize("卷积定理 Convolution")
        # 回退模式下应有字符 unigrams + bigrams + 英文词
        assert "convolution" in toks
        # 回退模式的 bigram
        assert "卷积" in toks or "积定" in toks or "定理" in toks

    def test_numbers(self):
        toks = tokenize("test123 456abc 7.8")
        assert "test123" in toks
        assert "456abc" in toks
        # "7" and "8" are separate numeric tokens
        assert "7" in toks
        assert "8" in toks

    def test_no_duplicates(self):
        toks = tokenize("测试 测试 test test")
        # 应去重
        assert len([t for t in toks if t == "test"]) == 1


class TestTokenizerModule:
    """tokenizer 模块功能测试。"""

    def test_chinese_tokenizer_singleton(self):
        t1 = ChineseTokenizer()
        t2 = ChineseTokenizer()
        assert t1 is t2

    def test_get_tokenizer_returns_singleton(self):
        t1 = _get_tokenizer()
        t2 = _get_tokenizer()
        assert t1 is t2

    def test_fallback_without_jieba(self, monkeypatch):
        """模拟 jieba 不可用时的行为。"""
        # 重置单例以模拟无 jieba 环境
        monkeypatch.setattr(ChineseTokenizer, "_loaded", False)
        monkeypatch.setattr(ChineseTokenizer, "_instance", None)
        # 阻止 jieba 导入
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jieba":
                raise ImportError("Mock: jieba not available")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        tok = ChineseTokenizer()
        assert tok.available is False
        assert tok.cut("卷积定理") == []
        assert tok.cut_for_search("卷积定理") == []

    @pytest.mark.skipif(
        ChineseTokenizer().available,
        reason="jieba 已安装时跳过（此测试仅验证无 jieba 回退）",
    )
    def test_cached_jieba_cut_no_jieba(self):
        # jieba 未安装时缓存返回空
        from src.services.tokenizer import _cached_jieba_cut
        _cached_jieba_cut.cache_clear()
        result = _cached_jieba_cut("卷积定理")
        assert result == ()


class TestTokenizeWithJieba:
    """jieba 相关行为测试（仅在 jieba 可用时生效）。"""

    @pytest.mark.skipif(
        not ChineseTokenizer().available,
        reason="jieba 未安装",
    )
    def test_jieba_cut_for_search(self):
        tok = ChineseTokenizer()
        words = tok.cut_for_search("卷积定理和傅里叶变换")
        assert len(words) > 0
        # 搜索引擎模式下应有更细粒度的切分
        assert any("卷积" in w for w in words)

    @pytest.mark.skipif(
        not ChineseTokenizer().available,
        reason="jieba 未安装",
    )
    def test_tokenize_with_jieba_includes_bigrams(self):
        toks = tokenize("卷积定理", keep_bigrams=True)
        assert "卷积" in toks
        assert "定理" in toks
        # bigram 补充
        assert "积定" in toks

    @pytest.mark.skipif(
        not ChineseTokenizer().available,
        reason="jieba 未安装",
    )
    def test_tokenize_without_bigrams(self):
        toks = tokenize("卷积定理", keep_bigrams=False)
        assert "卷积" in toks
        assert "定理" in toks
        # 无 bigram
        assert "积定" not in toks

    @pytest.mark.skipif(
        not ChineseTokenizer().available,
        reason="jieba 未安装",
    )
    def test_add_custom_word(self):
        tok = ChineseTokenizer()
        tok.add_word("紫薇星", freq=100)
        words = tok.cut("紫薇星傅里叶变换")
        assert "紫薇星" in words
