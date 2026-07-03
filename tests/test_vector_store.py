"""向量存储单元测试。"""

import pytest

from src.services.ingestion import embed_texts


class TestVectorStore:
    def test_empty_search(self, vector_store):
        hits = vector_store.search([0.0] * 384, top_k=5)
        assert hits == []

    def test_health_check(self, vector_store):
        assert vector_store.health_check() is True


@pytest.mark.integration
class TestVectorStoreWithEmbedder:
    def test_upsert_and_search(self, vector_store):
        chunks = [{
            "doc_id": "1",
            "source_file": "test.md",
            "chunk_index": 0,
            "course": "信号与系统",
            "text": "傅里叶变换将时域信号转换到频域",
        }]
        embeddings = embed_texts([chunks[0]["text"]])
        vector_store.upsert(chunks, embeddings)

        query_vec = embed_texts(["傅里叶变换是什么"])[0]
        hits = vector_store.search(query_vec, top_k=1)
        assert len(hits) == 1
        assert hits[0]["score"] > 0.3
        assert "傅里叶" in hits[0]["text"]

    def test_delete_by_doc_id(self, vector_store):
        chunks = [
            {
                "doc_id": "42",
                "source_file": "a.md",
                "chunk_index": 0,
                "course": "信号与系统",
                "text": "chunk a",
            },
            {
                "doc_id": "42",
                "source_file": "a.md",
                "chunk_index": 1,
                "course": "信号与系统",
                "text": "chunk b",
            },
        ]
        embeddings = embed_texts([c["text"] for c in chunks])
        vector_store.upsert(chunks, embeddings)

        vector_store.delete_by_doc_id("42")
        assert vector_store.search(embeddings[0], top_k=5) == []
