"""检索：向量相似度搜索，按 course_id 过滤。"""

from __future__ import annotations

import logging
from functools import lru_cache

from src.config import config
from src.exceptions import BadRequestException, ServiceUnavailableException
from src.services.embedding import get_embedding_client
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@lru_cache(maxsize=256)
def _cached_query_vec(cache_key: str, normalized_query: str) -> tuple[float, ...]:
    vec = get_embedding_client().embed([normalized_query])[0]
    return tuple(float(x) for x in vec)


def _embed_cache_key() -> str:
    emb = config.embedding
    return f"{emb.provider}|{emb.model}"


def clear_query_embed_cache() -> None:
    _cached_query_vec.cache_clear()


def retrieve(
    query: str,
    vs: ChromaVectorStore,
    course_id: str,
    top_k: int | None = None,
    *,
    score_threshold: float | None = None,
) -> list[dict]:
    """按课程过滤，取相似度最高的 top_k 条，再按阈值过滤。"""
    if top_k is None:
        top_k = config.retrieval.top_k
    if score_threshold is None:
        score_threshold = config.retrieval.score_threshold
    if top_k <= 0:
        raise BadRequestException("top_k 必须大于 0")

    q = query.strip()
    if not q:
        logger.warning("检索 query 为空")
        return []
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")

    try:
        query_vec = list(_cached_query_vec(_embed_cache_key(), q))
    except Exception as e:
        logger.error("检索向量化失败: %s", e)
        raise ServiceUnavailableException("向量化服务不可用", detail=str(e)) from e

    results = vs.search(query_vec, top_k=top_k, course_id=course_id)
    kept = [h for h in results if h.get("score", 0) >= score_threshold]

    logger.info(
        "检索完成: course_id=%s query='%s...' top_k=%d hits=%d kept=%d threshold=%.2f",
        course_id,
        q[:40],
        top_k,
        len(results),
        len(kept),
        score_threshold,
    )
    return kept
