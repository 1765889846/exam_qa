"""检索：向量 + BM25（按 course_id）→ RRF → 阈值过滤。"""

from __future__ import annotations

import logging
import math
from collections import Counter
from functools import lru_cache

from src.config import config
from src.exceptions import BadRequestException, ServiceUnavailableException
from src.services.embedding import get_embedding_client
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

RRF_K = 60

from src.services.tokenizer import tokenize  # noqa: E402


@lru_cache(maxsize=256)
def _cached_query_vec(cache_key: str, normalized_query: str) -> tuple[float, ...]:
    vec = get_embedding_client().embed([normalized_query])[0]
    return tuple(float(x) for x in vec)


def _embed_cache_key() -> str:
    emb = config.embedding
    return f"{emb.provider}|{emb.model}"


def clear_query_embed_cache() -> None:
    _cached_query_vec.cache_clear()


class _BM25:
    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = corpus_tokens
        self.n = len(corpus_tokens)
        self.doc_len = [len(t) for t in corpus_tokens]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        df: Counter[str] = Counter()
        for toks in corpus_tokens:
            df.update(set(toks))
        self.idf = {
            t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()
        }

    def scores(self, query_tokens: list[str]) -> list[float]:
        if not self.n or not query_tokens:
            return [0.0] * self.n
        out: list[float] = []
        for i, toks in enumerate(self.corpus_tokens):
            tf = Counter(toks)
            dl = self.doc_len[i]
            s = 0.0
            for q in query_tokens:
                if q not in tf:
                    continue
                freq = tf[q]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0))
                s += self.idf.get(q, 0.0) * (freq * (self.k1 + 1)) / denom
            out.append(s)
        return out


def rrf_fuse(*ranked_lists: list[dict], k: int = RRF_K, top_k: int) -> list[dict]:
    scores: dict[str, float] = {}
    best: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            cid = hit["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            prev = best.get(cid)
            if prev is None or hit.get("score", 0) > prev.get("score", 0):
                best[cid] = hit
    return [
        best[cid]
        for cid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    ]


def _vector_search(query: str, vs: ChromaVectorStore, course_id: str, top_k: int) -> list[dict]:
    try:
        query_vec = list(_cached_query_vec(_embed_cache_key(), query))
    except Exception as e:
        logger.error("检索向量化失败: %s", e)
        raise ServiceUnavailableException("向量化服务不可用", detail=str(e)) from e
    return vs.search(query_vec, top_k=top_k, course_id=course_id)


_BM25_CACHE: dict[str, tuple[list[dict], _BM25]] = {}


def _bm25_for_course(vs: ChromaVectorStore, course_id: str) -> tuple[list[dict], _BM25]:
    """按 course_id 缓存语料与倒排索引，避免每次检索全量拉取并重建。"""
    cached = _BM25_CACHE.get(course_id)
    if cached is not None:
        return cached
    corpus = vs.get_by_course_id(course_id)
    entry = (corpus, _BM25([tokenize(c.get("text", "")) for c in corpus]))
    _BM25_CACHE[course_id] = entry
    return entry


def invalidate_bm25_cache(course_id: str | None = None) -> None:
    """使 BM25 语料缓存失效；course_id 为空时清空全部课程缓存。"""
    if course_id is None:
        _BM25_CACHE.clear()
    else:
        _BM25_CACHE.pop(course_id, None)


def _bm25_search(query: str, vs: ChromaVectorStore, course_id: str, top_k: int) -> list[dict]:
    corpus, bm25 = _bm25_for_course(vs, course_id)
    if not corpus:
        return []
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    raw = bm25.scores(q_tokens)
    max_s = max(raw) if raw else 0.0
    ranked = sorted(range(len(raw)), key=lambda i: raw[i], reverse=True)
    hits: list[dict] = []
    for i in ranked:
        if raw[i] <= 0 or len(hits) >= top_k:
            break
        hit = dict(corpus[i])
        hit["score"] = (raw[i] / max_s) if max_s > 0 else 0.0
        hits.append(hit)
    return hits


def retrieve(
    query: str,
    vs: ChromaVectorStore,
    course_id: str,
    top_k: int | None = None,
    *,
    score_threshold: float | None = None,
    rerank_enabled: bool | None = None,
) -> list[dict]:
    if top_k is None:
        top_k = config.retrieval.top_k
    if score_threshold is None:
        score_threshold = config.retrieval.score_threshold
    if rerank_enabled is None:
        rerank_enabled = config.retrieval.rerank_enabled
    if top_k <= 0:
        raise BadRequestException("top_k 必须大于 0")

    q = query.strip()
    if not q:
        return []
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")

    # 精排开：宽池 → RRF → CrossEncoder → top_n
    if rerank_enabled:
        pool = max(config.retrieval.rerank_candidates, top_k)
        fuse_k = pool
    else:
        pool = top_k * 2
        fuse_k = top_k

    vec_hits = _vector_search(q, vs, course_id, pool)
    bm25_hits = _bm25_search(q, vs, course_id, pool)
    fused = (
        rrf_fuse(vec_hits, bm25_hits, top_k=fuse_k) if (vec_hits or bm25_hits) else []
    )

    if rerank_enabled and fused:
        from src.services.rerank import rerank as _rerank

        top_n = config.retrieval.rerank_top_n or top_k
        ranked = _rerank(
            q,
            fused,
            top_n,
            model_name=config.retrieval.rerank_model,
        )
        kept = [h for h in ranked if h.get("score", 0) >= score_threshold]
    else:
        kept = [h for h in fused if h.get("score", 0) >= score_threshold]

    logger.info(
        "混合检索: course=%s top_k=%d rerank=%s vec=%d bm25=%d kept=%d",
        course_id,
        top_k,
        rerank_enabled,
        len(vec_hits),
        len(bm25_hits),
        len(kept),
    )
    return kept

