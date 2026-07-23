"""FastAPI Depends 工厂：注入存储、LLM、Embedding、目录单例。"""

from functools import lru_cache
import logging

from src.config import config
from src.services.embedding import EmbeddingClient, get_embedding_client as _get_embedding_client
from src.services.llm import OpenAIClient
from src.services.storage.catalog_store import CatalogStore
from src.services.storage.doc_store import SQLiteDocStore
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@lru_cache()
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(persist_path=config.storage.chroma_path)


@lru_cache()
def get_doc_store() -> SQLiteDocStore:
    return SQLiteDocStore(db_path=config.storage.sqlite_path)


@lru_cache()
def get_catalog_store() -> CatalogStore:
    return CatalogStore(db_path=config.storage.sqlite_path)


@lru_cache()
def get_llm_client() -> OpenAIClient:
    return OpenAIClient(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        model=config.llm.model,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
        timeout=config.llm.timeout,
    )


def get_embedding_client() -> EmbeddingClient:
    """Depends 注入用；单例由 services.embedding 管理。"""
    return _get_embedding_client()


def reload_services() -> None:
    """配置变更后清空单例缓存。"""
    from src.services.embedding import reset_embedding_client
    from src.services.rerank import clear_reranker

    get_vector_store.cache_clear()
    get_doc_store.cache_clear()
    get_catalog_store.cache_clear()
    get_llm_client.cache_clear()
    reset_embedding_client()
    clear_reranker()


async def get_current_user() -> None:
    """鉴权占位。MVP 固定返回 None。"""
    return None
