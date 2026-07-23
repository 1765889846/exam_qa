"""入库主链：分块、扫描、章节、acquire/fail、跨课拒绝。"""

import pytest

from src.exceptions import BadRequestException
from src.services.ingestion import (
    _acquire_doc_id,
    _fail_ingest,
    _needs_reindex,
    _split_text,
    assign_chapters,
    scan_knowledge_dir,
)
from src.services.storage.catalog_store import DEFAULT_COURSE_ID, DEFAULT_COURSE_NAME

_COURSE = DEFAULT_COURSE_NAME
_CID = DEFAULT_COURSE_ID


def _vec_chunk(doc_id: int, text: str) -> dict:
    return {
        "doc_id": str(doc_id),
        "source_file": "x.md",
        "chunk_index": 0,
        "course": _COURSE,
        "course_id": _CID,
        "college_id": "college-default",
        "text": text,
    }


class TestSplitText:
    def test_short_and_empty(self):
        assert _split_text("短文本", chunk_size=500, chunk_overlap=50) == ["短文本"]
        assert _split_text("") == []
        assert _split_text("   \n\n  ") == []

    def test_split_and_overlap(self):
        text = "信号" * 200 + "\n\n" + "系统" * 200
        chunks = _split_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) >= 2
        assert chunks[0][-20:] in chunks[1]


class TestScanAndChapter:
    def test_needs_reindex_rules(self):
        assert _needs_reindex(None, 100.0) is True
        assert _needs_reindex({"status": "done", "file_mtime": 100.0}, 100.0) is False
        assert _needs_reindex({"status": "done", "file_mtime": 100.0}, 200.0) is True
        assert _needs_reindex({"status": "failed", "file_mtime": 100.0}, 100.0) is True
        assert (
            _needs_reindex({"status": "processing", "file_mtime": None}, 100.0) is False
        )

    def test_scan_force_reindexes_done(
        self, temp_dir, vector_store, doc_store, monkeypatch
    ):
        knowledge = temp_dir / "knowledge"
        knowledge.mkdir()
        monkeypatch.setattr(
            "src.services.ingestion.config.storage.knowledge_dir", str(knowledge)
        )
        md = knowledge / "note.md"
        md.write_text("hello", encoding="utf-8")
        doc_id = doc_store.create(
            "note.md", str(md.resolve()), course=_COURSE, course_id=_CID
        )
        doc_store.update_status(doc_id, "done", chunk_count=1)
        doc_store.update_file_mtime(doc_id, md.stat().st_mtime)

        called: list[str] = []

        def fake_ingest(**kwargs):
            called.append(kwargs["path"])
            return str(doc_id)

        monkeypatch.setattr("src.services.ingestion.ingest_file", fake_ingest)

        scan_knowledge_dir(vector_store, doc_store, force=False)
        assert called == []
        scan_knowledge_dir(vector_store, doc_store, force=True)
        assert len(called) == 1 and called[0].endswith("note.md")

    def test_assign_chapters_header_and_page_fallback(self):
        text = "## 第3章 傅里叶\n\n定义。\n\n## 第4章 卷积\n\n卷积。\n"
        chapters = assign_chapters(text, ["定义。", "卷积。"])
        assert "第3章" in chapters[0] and "第4章" in chapters[1]
        assert assign_chapters("无标题", ["无标题"], pages=[2]) == ["第2页"]


class TestIngestHelpers:
    def test_acquire_reuses_failed(self, doc_store, vector_store, temp_dir):
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

    def test_acquire_reuses_done_clears_vectors(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "done.md"
        path.write_text("x", encoding="utf-8")
        resolved = str(path.resolve())
        doc_id = doc_store.create("done.md", resolved, course=_COURSE, course_id=_CID)
        doc_store.update_status(doc_id, "done", chunk_count=3)
        vector_store.upsert([_vec_chunk(doc_id, "old")], [[0.2] * 8])
        reused = _acquire_doc_id(
            doc_store, vector_store, path, "done.md", _COURSE, _CID
        )
        assert reused == doc_id
        assert vector_store.search([0.2] * 8, top_k=5, course_id=_CID) == []

    def test_fail_ingest_cleans_vectors(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "fail.md"
        path.write_text("content", encoding="utf-8")
        doc_id = doc_store.create(
            "fail.md", str(path.resolve()), course=_COURSE, course_id=_CID
        )
        doc_store.update_status(doc_id, "processing")
        vector_store.upsert([_vec_chunk(doc_id, "content")], [[0.1] * 8])
        _fail_ingest(vector_store, doc_store, doc_id)
        assert doc_store.get(doc_id)["status"] == "failed"
        assert vector_store.search([0.1] * 8, top_k=5, course_id=_CID) == []

    def test_acquire_rejects_cross_course(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "move.md"
        path.write_text("x", encoding="utf-8")
        resolved = str(path.resolve())
        doc_id = doc_store.create("move.md", resolved, course=_COURSE, course_id=_CID)
        doc_store.update_status(doc_id, "done", chunk_count=1)
        with pytest.raises(BadRequestException):
            _acquire_doc_id(
                doc_store,
                vector_store,
                path,
                "move.md",
                "思政原理",
                "course-ideology-2025",
            )
        assert doc_store.get(doc_id)["course_id"] == _CID


class TestDocStoreIsolation:
    def test_list_by_course_id(self, doc_store):
        doc_store.create("a.pdf", "/tmp/a.pdf", course_id=_CID)
        doc_store.create(
            "b.pdf",
            "/tmp/b.pdf",
            course="思政原理",
            course_id="course-ideology-2025",
        )
        docs = doc_store.list(course_id=_CID)
        assert len(docs) == 1
        assert docs[0]["filename"] == "a.pdf"

    def test_create_update_delete(self, doc_store):
        doc_id = doc_store.create(
            "test.md", "/tmp/test.md", course=_COURSE, course_id=_CID
        )
        doc_store.update_status(doc_id, "done", chunk_count=3)
        assert doc_store.get(doc_id)["chunk_count"] == 3
        doc_store.delete(doc_id)
        assert doc_store.get(doc_id) is None


class TestVectorStoreGuard:
    def test_upsert_requires_course_id(self, vector_store):
        with pytest.raises(ValueError, match="course_id"):
            vector_store.upsert(
                [
                    {
                        "doc_id": "1",
                        "source_file": "a.md",
                        "chunk_index": 0,
                        "course": _COURSE,
                        "text": "no course_id",
                    }
                ],
                [[0.1] * 8],
            )

    def test_delete_by_doc_id(self, vector_store):
        vector_store.upsert([_vec_chunk(42, "chunk a")], [[0.1] * 8])
        vector_store.delete_by_doc_id("42")
        assert vector_store.search([0.1] * 8, top_k=5, course_id=_CID) == []
