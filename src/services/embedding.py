"""Embedding 客户端：入库与检索共用，与 LLM 对话分离。"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol, runtime_checkable

from src.config import EmbeddingConfig, LLMConfig, config

logger = logging.getLogger(__name__)

_BATCH_SIZE = 64


@runtime_checkable
class EmbeddingClient(Protocol):
    """向量化抽象接口。"""

    provider: str
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def warmup(self) -> None:
        ...

    def status(self) -> str:
        """轻量状态：not_ready | ok | unavailable（不触发加载或网络请求）。"""
        ...


class LocalEmbeddingClient:
    """本地 sentence-transformers 模型。"""

    provider = "local"

    def __init__(self, model_name: str):
        self.model = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("加载本地 Embedding 模型: %s", self.model)
            self._model = SentenceTransformer(self.model)
            logger.info("Embedding 维度: %d", self._model.get_embedding_dimension())

    def warmup(self) -> None:
        self._load()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        vectors = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def status(self) -> str:
        return "ok" if self._model is not None else "not_ready"

    def health_check(self) -> bool:
        return self.status() == "ok"


class OpenAIEmbeddingClient:
    """OpenAI 兼容 Embedding API（独立 api_key / base_url）。"""

    provider = "openai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 60):
        from openai import OpenAI

        self.model = model
        self._client = None
        self._warmed = False
        if api_key:
            from src.services.http_client import create_openai_http_client

            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=1,
                http_client=create_openai_http_client(timeout),
            )
            logger.info("Embedding API 已配置: %s @ %s", model, base_url)

    def warmup(self) -> None:
        if self._client:
            self.embed(["ping"])
            self._warmed = True

    def status(self) -> str:
        if self._client is None:
            return "unavailable"
        return "ok"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client is None:
            raise RuntimeError("Embedding API 未配置：请设置 EMBEDDING_API_KEY 或 LLM_API_KEY")

        out: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(resp.data, key=lambda item: item.index)
            out.extend(item.embedding for item in ordered)
        self._warmed = True
        return out

    def health_check(self) -> bool:
        return self.status() == "ok"


def create_embedding_client(
    emb_cfg: EmbeddingConfig,
    llm_cfg: LLMConfig,
) -> EmbeddingClient:
    provider = emb_cfg.provider.strip().lower()
    if provider == "openai":
        return OpenAIEmbeddingClient(
            api_key=emb_cfg.resolve_api_key(llm_cfg),
            base_url=emb_cfg.resolve_base_url(llm_cfg),
            model=emb_cfg.model,
            timeout=emb_cfg.timeout,
        )
    if provider == "local":
        return LocalEmbeddingClient(model_name=emb_cfg.model)
    raise ValueError(f"未知 EMBEDDING_PROVIDER: {emb_cfg.provider!r}，可选 local / openai")


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    """进程内单例。"""
    return create_embedding_client(config.embedding, config.llm)


def reset_embedding_client() -> None:
    from src.services.retrieval import clear_query_embed_cache

    get_embedding_client.cache_clear()
    clear_query_embed_cache()
