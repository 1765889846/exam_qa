"""检索隔离与目录种子：不依赖 LLM。"""

from src.services.storage.catalog_store import (
    DEFAULT_COLLEGE_ID,
    DEFAULT_COURSE_ID,
    DEFAULT_COURSE_NAME,
    CatalogStore,
)


class TestCourseFilter:
    def test_search_filters_by_course_id(self, vector_store):
        dim = 8
        chunks_a = [{
            "doc_id": "1",
            "source_file": "a.md",
            "chunk_index": 0,
            "course": DEFAULT_COURSE_NAME,
            "course_id": DEFAULT_COURSE_ID,
            "college_id": DEFAULT_COLLEGE_ID,
            "text": "默认课：傅里叶变换",
        }]
        chunks_b = [{
            "doc_id": "2",
            "source_file": "b.md",
            "chunk_index": 0,
            "course": "思政原理",
            "course_id": "course-ideology-2025",
            "college_id": "college-marx",
            "text": "思政课：考试题型",
        }]
        emb_a = [[1.0] + [0.0] * (dim - 1)]
        emb_b = [[0.0, 1.0] + [0.0] * (dim - 2)]
        vector_store.upsert(chunks_a, emb_a)
        vector_store.upsert(chunks_b, emb_b)

        hits_a = vector_store.search(emb_a[0], top_k=5, course_id=DEFAULT_COURSE_ID)
        assert len(hits_a) == 1
        assert hits_a[0]["metadata"]["course_id"] == DEFAULT_COURSE_ID
        assert "傅里叶" in hits_a[0]["text"]

        hits_b = vector_store.search(
            emb_a[0], top_k=5, course_id="course-ideology-2025"
        )
        assert len(hits_b) == 1
        assert hits_b[0]["metadata"]["course_id"] == "course-ideology-2025"
        assert "思政" in hits_b[0]["text"]

        assert (
            vector_store.search(emb_a[0], top_k=5, course_id="course-nonexistent")
            == []
        )


class TestCatalogStore:
    def test_seed_defaults(self, temp_dir):
        store = CatalogStore(str(temp_dir / "catalog.db"))
        try:
            colleges = store.list_colleges()
            assert any(c["id"] == DEFAULT_COLLEGE_ID for c in colleges)
            course = store.require_course(DEFAULT_COURSE_ID)
            assert course["name"] == DEFAULT_COURSE_NAME
        finally:
            store.close()
