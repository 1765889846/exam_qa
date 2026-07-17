"""入库逻辑单元测试（不涉及 embedding）。"""

import pytest

from src.services.ingestion import _acquire_doc_id, _fail_ingest
from src.services.storage.catalog_store import DEFAULT_COURSE_ID, DEFAULT_COURSE_NAME

_COURSE = DEFAULT_COURSE_NAME
_CID = DEFAULT_COURSE_ID


def _chunk(doc_id: int, text: str) -> dict:
    return {
        "doc_id": str(doc_id),
        "source_file": "x.md",
        "chunk_index": 0,
        "course": _COURSE,
        "course_id": _CID,
        "college_id": "college-default",
        "text": text,
    }


class TestIngestHelpers:
    def test_acquire_reuses_failed_record(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "retry.md"
        path.write_text("# t\nbody", encoding="utf-8")
        resolved = str(path.resolve())

        doc_id = doc_store.create("retry.md", resolved, course=_COURSE, course_id=_CID)
        doc_store.update_status(doc_id, "failed")

        reused = _acquire_doc_id(
            doc_store, vector_store, path, "retry.md", _COURSE, _CID
        )
        assert reused == doc_id
        assert doc_store.get(doc_id)["status"] == "processing"
        assert len(doc_store.list()) == 1

    def test_acquire_reuses_done_record(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "done.md"
        path.write_text("x", encoding="utf-8")
        resolved = str(path.resolve())

        doc_id = doc_store.create("done.md", resolved, course=_COURSE, course_id=_CID)
        doc_store.update_status(doc_id, "done", chunk_count=3)
        vector_store.upsert([_chunk(doc_id, "old chunk")], [[0.2] * 384])

        reused = _acquire_doc_id(
            doc_store, vector_store, path, "done.md", _COURSE, _CID
        )
        assert reused == doc_id
        assert len(doc_store.list()) == 1
        assert vector_store.search([0.2] * 384, top_k=5, course_id=_CID) == []

    def test_fail_ingest_cleans_vectors(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "fail.md"
        path.write_text("content", encoding="utf-8")
        doc_id = doc_store.create(
            "fail.md", str(path.resolve()), course=_COURSE, course_id=_CID
        )
        doc_store.update_status(doc_id, "processing")

        vector_store.upsert([_chunk(doc_id, "content")], [[0.1] * 384])

        _fail_ingest(vector_store, doc_store, doc_id)
        assert doc_store.get(doc_id)["status"] == "failed"
        assert vector_store.search([0.1] * 384, top_k=5, course_id=_CID) == []

    def test_acquire_rejects_cross_course(self, doc_store, vector_store, temp_dir):
        from src.exceptions import BadRequestException

        path = temp_dir / "move.md"
        path.write_text("x", encoding="utf-8")
        resolved = str(path.resolve())
        doc_id = doc_store.create(
            "move.md", resolved, course=_COURSE, course_id=_CID
        )
        doc_store.update_status(doc_id, "done", chunk_count=1)

        with pytest.raises(BadRequestException):
            _acquire_doc_id(
                doc_store, vector_store, path, "move.md", "思政原理", "course-ideology-2025"
            )
        row = doc_store.get(doc_id)
        assert row["course_id"] == _CID
        assert row["status"] == "done"

    def test_rebind_course_id(self, vector_store):
        vector_store.upsert(
            [{
                "doc_id": "9",
                "source_file": "a.md",
                "chunk_index": 0,
                "course": "旧课",
                "course_id": "course-signals-2025",
                "college_id": "college-telecom",
                "text": "legacy",
            }],
            [[0.3] * 384],
        )
        n = vector_store.rebind_course_id(
            "course-signals-2025",
            _CID,
            course=_COURSE,
            college_id="college-default",
        )
        assert n == 1
        hits = vector_store.search([0.3] * 384, top_k=5, course_id=_CID)
        assert len(hits) == 1
        assert hits[0]["metadata"]["course_id"] == _CID
        assert (
            vector_store.search(
                [0.3] * 384, top_k=5, course_id="course-signals-2025"
            )
            == []
        )

    def test_search_requires_course_id(self, vector_store):
        with pytest.raises(ValueError, match="course_id"):
            vector_store.search([0.0] * 384, top_k=5)
