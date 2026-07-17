"""向量存储单元测试。"""

import pytest

from src.services.ingestion import embed_texts
from src.services.storage.catalog_store import (
    DEFAULT_COLLEGE_ID,
    DEFAULT_COURSE_ID,
    DEFAULT_COURSE_NAME,
)


def _meta_chunk(doc_id: str, text: str, chunk_index: int = 0) -> dict:
    return {
        "doc_id": doc_id,
        "source_file": "test.md",
        "chunk_index": chunk_index,
        "course": DEFAULT_COURSE_NAME,
        "course_id": DEFAULT_COURSE_ID,
        "college_id": DEFAULT_COLLEGE_ID,
        "text": text,
    }


class TestVectorStore:
    def test_empty_search(self, vector_store):
        hits = vector_store.search(
            [0.0] * 384, top_k=5, course_id=DEFAULT_COURSE_ID
        )
        assert hits == []

    def test_health_check(self, vector_store):
        assert vector_store.health_check() is True

    def test_upsert_requires_course_id(self, vector_store):
        with pytest.raises(ValueError, match="course_id"):
            vector_store.upsert(
                [{
                    "doc_id": "1",
                    "source_file": "a.md",
                    "chunk_index": 0,
                    "course": DEFAULT_COURSE_NAME,
                    "text": "no course_id",
                }],
                [[0.1] * 384],
            )

    def test_ensure_embedding_dim_recreates_on_mismatch(self, vector_store):
        chunks = [_meta_chunk("1", "old dim")]
        vector_store.upsert(chunks, [[0.1] * 384])
        assert vector_store.stored_embedding_dim() == 384
        assert vector_store.ensure_embedding_dim(3072) is True
        assert vector_store.stored_embedding_dim() is None
        assert vector_store._collection.count() == 0
        # same dim on empty: no wipe via peek (may still be locked — upsert path retries)
        assert vector_store.ensure_embedding_dim(3072) is False
        vector_store.upsert([_meta_chunk("2", "new dim")], [[0.2] * 3072])
        assert vector_store.stored_embedding_dim() == 3072
        assert vector_store.ensure_embedding_dim(3072) is False

    def test_upsert_retries_when_empty_collection_locks_old_dim(self, vector_store):
        """Chroma keeps dim lock after all vectors deleted."""
        vector_store.upsert([_meta_chunk("1", "a")], [[0.1] * 64])
        vector_store.delete_by_doc_id("1")
        assert vector_store._collection.count() == 0
        wiped = vector_store.upsert([_meta_chunk("2", "b")], [[0.2] * 128])
        assert wiped is True
        assert vector_store.stored_embedding_dim() == 128


@pytest.mark.integration
class TestVectorStoreWithEmbedder:
    def test_upsert_and_search(self, vector_store):
        chunks = [_meta_chunk("1", "傅里叶变换将时域信号转换到频域")]
        embeddings = embed_texts([chunks[0]["text"]])
        vector_store.upsert(chunks, embeddings)

        query_vec = embed_texts(["傅里叶变换是什么"])[0]
        hits = vector_store.search(
            query_vec, top_k=1, course_id=DEFAULT_COURSE_ID
        )
        assert len(hits) == 1
        assert hits[0]["score"] > 0.3
        assert "傅里叶" in hits[0]["text"]

    def test_delete_by_doc_id(self, vector_store):
        chunks = [
            _meta_chunk("42", "chunk a", 0),
            _meta_chunk("42", "chunk b", 1),
        ]
        embeddings = embed_texts([c["text"] for c in chunks])
        vector_store.upsert(chunks, embeddings)

        vector_store.delete_by_doc_id("42")
        assert (
            vector_store.search(
                embeddings[0], top_k=5, course_id=DEFAULT_COURSE_ID
            )
            == []
        )
