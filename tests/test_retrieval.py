"""检索主链：course_id 隔离、阈值拒答、BM25/RRF、精排。"""

from unittest.mock import MagicMock, patch

from src.services.rerank import clear_reranker, rerank
from src.services.retrieval import (
    _BM25,
    _bm25_search,
    clear_query_embed_cache,
    invalidate_bm25_cache,
    retrieve,
    rrf_fuse,
    tokenize,
)
from src.services.storage.catalog_store import (
    DEFAULT_COLLEGE_ID,
    DEFAULT_COURSE_ID,
    DEFAULT_COURSE_NAME,
)


def _chunk(doc_id: str, course_id: str, text: str, course: str = "课"):
    return {
        "doc_id": doc_id,
        "source_file": f"{doc_id}.md",
        "chunk_index": 0,
        "course": course,
        "course_id": course_id,
        "college_id": DEFAULT_COLLEGE_ID,
        "text": text,
    }


def test_vector_search_filters_by_course_id(vector_store):
    dim = 8
    vector_store.upsert(
        [_chunk("1", DEFAULT_COURSE_ID, "默认课：傅里叶变换", DEFAULT_COURSE_NAME)],
        [[1.0] + [0.0] * (dim - 1)],
    )
    vector_store.upsert(
        [_chunk("2", "course-ideology-2025", "思政课：考试题型", "思政原理")],
        [[0.0, 1.0] + [0.0] * (dim - 2)],
    )
    q = [1.0] + [0.0] * (dim - 1)
    hits = vector_store.search(q, top_k=5, course_id=DEFAULT_COURSE_ID)
    assert len(hits) == 1
    assert hits[0]["metadata"]["course_id"] == DEFAULT_COURSE_ID
    assert "傅里叶" in hits[0]["text"]
    hits_b = vector_store.search(q, top_k=5, course_id="course-ideology-2025")
    assert len(hits_b) == 1
    assert hits_b[0]["metadata"]["course_id"] == "course-ideology-2025"
    assert vector_store.search(q, top_k=5, course_id="course-nonexistent") == []


def test_search_requires_course_id(vector_store):
    import pytest

    with pytest.raises(ValueError, match="course_id"):
        vector_store.search([0.0] * 8, top_k=5)


def test_bm25_isolated_by_course_id(vector_store):
    dim = 8
    vector_store.upsert(
        [_chunk("1", DEFAULT_COURSE_ID, "默认课专有词：紫薇星傅里叶变换")],
        [[0.1] * dim],
    )
    vector_store.upsert(
        [_chunk("2", "course-ideology-2025", "思政课专有词：论述题")],
        [[0.2] * dim],
    )
    assert len(_bm25_search("紫薇星", vector_store, DEFAULT_COURSE_ID, 5)) == 1
    assert _bm25_search("紫薇星", vector_store, "course-ideology-2025", 5) == []
    assert len(_bm25_search("论述题", vector_store, "course-ideology-2025", 5)) == 1


def test_tokenize_and_bm25_rank():
    toks = tokenize("卷积定理 Convolution")
    assert "卷积" in toks and "convolution" in toks
    scores = _BM25(
        [["傅里叶", "变换"], ["卷积", "定理"], ["采样"]]
    ).scores(["卷积", "定理"])
    assert scores[1] > scores[0]


def test_rrf_prefers_agreement():
    a = [{"id": "x", "score": 0.9, "text": "x"}, {"id": "y", "score": 0.8, "text": "y"}]
    b = [{"id": "y", "score": 0.7, "text": "y"}, {"id": "z", "score": 0.6, "text": "z"}]
    fused = rrf_fuse(a, b, top_k=3)
    assert fused[0]["id"] == "y"
    assert {h["id"] for h in fused} == {"x", "y", "z"}


def test_retrieve_filters_below_threshold():
    clear_query_embed_cache()
    vs = MagicMock()
    vs.search.return_value = [
        {"id": "a", "score": 0.9, "text": "a", "metadata": {}},
        {"id": "b", "score": 0.1, "text": "b", "metadata": {}},
    ]
    vs.get_by_course_id.return_value = []
    with patch(
        "src.services.retrieval._cached_query_vec", return_value=(0.1, 0.2)
    ):
        out = retrieve(
            "三重积分",
            vs,
            "course-default",
            top_k=5,
            score_threshold=0.25,
            rerank_enabled=False,
        )
    assert len(out) == 1
    assert out[0]["id"] == "a"


def test_retrieve_empty_query():
    vs = MagicMock()
    assert retrieve("   ", vs, "course-default") == []
    vs.search.assert_not_called()


def test_rerank_orders_by_scores():
    hits = [
        {"id": "a", "text": "noise", "score": 0.9},
        {"id": "b", "text": "gold", "score": 0.8},
        {"id": "c", "text": "mid", "score": 0.7},
    ]
    out = rerank(
        "卷积",
        hits,
        top_n=2,
        model_name="dummy",
        score_fn=lambda q, t: [0.0, 5.0, 1.0],
    )
    assert [h["id"] for h in out] == ["b", "c"]


def test_retrieve_rerank_path_uses_wide_pool(monkeypatch):
    clear_query_embed_cache()
    clear_reranker()
    monkeypatch.setattr("src.config.config.retrieval.rerank_enabled", True)
    monkeypatch.setattr("src.config.config.retrieval.rerank_candidates", 4)
    monkeypatch.setattr("src.config.config.retrieval.rerank_top_n", 2)
    monkeypatch.setattr("src.config.config.retrieval.rerank_model", "dummy")

    fused_pool = [
        {"id": "a", "text": "a", "score": 0.99, "metadata": {}},
        {"id": "b", "text": "b", "score": 0.98, "metadata": {}},
        {"id": "c", "text": "c", "score": 0.97, "metadata": {}},
        {"id": "d", "text": "d", "score": 0.96, "metadata": {}},
    ]
    vs = MagicMock()
    vs.search.return_value = fused_pool
    vs.get_by_course_id.return_value = []

    def fake_rerank(query, hits, top_n, *, model_name):
        ordered = [
            {**hits[3], "score": 0.9},
            {**hits[0], "score": 0.8},
            {**hits[1], "score": 0.1},
        ]
        return ordered[:top_n]

    with (
        patch("src.services.retrieval._cached_query_vec", return_value=(0.1, 0.2)),
        patch("src.services.rerank.rerank", side_effect=fake_rerank),
    ):
        out = retrieve(
            "q",
            vs,
            "course-default",
            top_k=2,
            score_threshold=0.5,
            rerank_enabled=True,
        )

    assert [h["id"] for h in out] == ["d", "a"]
    assert vs.search.call_args.kwargs["top_k"] == 4

def test_bm25_cache_refreshes_after_invalidate(vector_store):
    dim = 8
    vector_store.upsert(
        [_chunk("1", DEFAULT_COURSE_ID, "默认课：傅里叶变换", DEFAULT_COURSE_NAME)],
        [[0.1] * dim],
    )
    assert len(_bm25_search("傅里叶", vector_store, DEFAULT_COURSE_ID, 5)) == 1
    vector_store.upsert(
        [_chunk("2", DEFAULT_COURSE_ID, "默认课：卷积定理", DEFAULT_COURSE_NAME)],
        [[0.2] * dim],
    )
    assert _bm25_search("卷积", vector_store, DEFAULT_COURSE_ID, 5) == []
    invalidate_bm25_cache(DEFAULT_COURSE_ID)
    assert len(_bm25_search("卷积", vector_store, DEFAULT_COURSE_ID, 5)) == 1
    invalidate_bm25_cache()
    assert len(_bm25_search("卷积", vector_store, DEFAULT_COURSE_ID, 5)) == 1
