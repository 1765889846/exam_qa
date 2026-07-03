"""检索：向量相似度搜索。"""

import logging

from src.config import config
from src.exceptions import ServiceUnavailableException
from src.services.embedding import get_embedding_client
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    vs: ChromaVectorStore,
    top_k: int | None = None,
) -> list[dict]:
    """向量检索：将问题向量化后在 ChromaDB 中搜索 top_k 个最相似 chunk。"""
    if top_k is None:
        top_k = config.retrieval.top_k

    if not query.strip():
        logger.warning("检索 query 为空")
        return []

    try:
        query_vec = get_embedding_client().embed([query])[0]
    except Exception as e:
        logger.error("检索向量化失败: %s", e)
        raise ServiceUnavailableException("向量化服务不可用", detail=str(e)) from e

    results = vs.search(query_vec, top_k=top_k)

    logger.info(
        "检索完成: query='%s...' top_k=%d hits=%d",
        query[:40], top_k, len(results),
    )
    if results:
        logger.info("最高分: %.4f, 最低分: %.4f", results[0]["score"], results[-1]["score"])

    return results
