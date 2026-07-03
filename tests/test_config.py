"""配置解析单元测试。"""

from src.config import EmbeddingConfig, LLMConfig


class TestEmbeddingConfig:
    def test_resolve_falls_back_to_llm(self):
        llm = LLMConfig(api_key="llm-key", base_url="https://llm.example/v1")
        emb = EmbeddingConfig(api_key="", base_url="")
        assert emb.resolve_api_key(llm) == "llm-key"
        assert emb.resolve_base_url(llm) == "https://llm.example/v1"

    def test_resolve_uses_embedding_overrides(self):
        llm = LLMConfig(api_key="llm-key", base_url="https://llm.example/v1")
        emb = EmbeddingConfig(
            api_key="emb-key",
            base_url="https://emb.example/v1",
        )
        assert emb.resolve_api_key(llm) == "emb-key"
        assert emb.resolve_base_url(llm) == "https://emb.example/v1"


class TestAppConfigValidate:
    def test_valid_config(self):
        from src.config import AppConfig

        AppConfig().validate()

    def test_invalid_embedding_provider(self):
        from src.config import AppConfig, EmbeddingConfig

        cfg = AppConfig(embedding=EmbeddingConfig(provider="invalid"))
        try:
            cfg.validate()
            assert False, "should raise"
        except ValueError as e:
            assert "EMBEDDING_PROVIDER" in str(e)

    def test_invalid_chunk_overlap(self):
        from src.config import AppConfig, ChunkConfig

        cfg = AppConfig(chunk=ChunkConfig(chunk_size=100, chunk_overlap=100))
        try:
            cfg.validate()
            assert False, "should raise"
        except ValueError as e:
            assert "chunk_overlap" in str(e)
