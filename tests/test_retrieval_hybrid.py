"""BM25 + RRF 混合检索：无 Embedding / LLM。"""

from src.services.retrieval import rrf_fuse, tokenize, _BM25
from src.services.storage.catalog_store import (
    DEFAULT_COLLEGE_ID,
    DEFAULT_COURSE_ID,
    DEFAULT_COURSE_NAME,
)


def test_tokenize_chinese_and_english():
    toks = tokenize("卷积定理 Convolution")
    assert "卷" in toks
    assert "积" in toks
    assert "卷积" in toks
    assert "convolution" in toks


def test_bm25_ranks_keyword_hit_higher():
    docs = [
        ["傅里叶", "变换", "定义"],
        ["卷积", "定理", "频域", "相乘"],
        ["采样", "奈奎斯特"],
    ]
    bm25 = _BM25(docs)
    scores = bm25.scores(["卷积", "定理"])
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_rrf_fuse_prefers_multi_list_agreement():
    a = [
        {"id": "x", "score": 0.9, "text": "x"},
        {"id": "y", "score": 0.8, "text": "y"},
    ]
    b = [
        {"id": "y", "score": 0.7, "text": "y"},
        {"id": "z", "score": 0.6, "text": "z"},
    ]
    fused = rrf_fuse(a, b, top_k=3)
    assert fused[0]["id"] == "y"
    assert {h["id"] for h in fused} == {"x", "y", "z"}


def test_bm25_isolated_by_course_id(vector_store):
    """BM25 语料只含本课 chunk，跨课关键词不得召回。"""
    from src.services.retrieval import _bm25_search

    chunks_a = [{
        "doc_id": "1",
        "source_file": "a.md",
        "chunk_index": 0,
        "course": DEFAULT_COURSE_NAME,
        "course_id": DEFAULT_COURSE_ID,
        "college_id": DEFAULT_COLLEGE_ID,
        "text": "默认课专有词：紫薇星傅里叶变换时移",
    }]
    chunks_b = [{
        "doc_id": "2",
        "source_file": "b.md",
        "chunk_index": 0,
        "course": "思政原理",
        "course_id": "course-ideology-2025",
        "college_id": "college-marx",
        "text": "思政课专有词：考试题型论述题",
    }]
    dim = 8
    emb = [[0.1] * dim]
    vector_store.upsert(chunks_a, emb)
    vector_store.upsert(chunks_b, [[0.2] * dim])

    hits_a = _bm25_search("紫薇星", vector_store, DEFAULT_COURSE_ID, top_k=5)
    assert len(hits_a) == 1
    assert "紫薇星" in hits_a[0]["text"]

    hits_cross = _bm25_search(
        "紫薇星", vector_store, "course-ideology-2025", top_k=5
    )
    assert hits_cross == []

    hits_b = _bm25_search(
        "论述题", vector_store, "course-ideology-2025", top_k=5
    )
    assert len(hits_b) == 1
    assert "论述题" in hits_b[0]["text"]
