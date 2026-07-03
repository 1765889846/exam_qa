"""入库逻辑单元测试（不涉及 embedding）。"""

from src.services.ingestion import _acquire_doc_id, _fail_ingest


class TestIngestHelpers:
    def test_acquire_reuses_failed_record(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "retry.md"
        path.write_text("# t\nbody", encoding="utf-8")
        resolved = str(path.resolve())

        doc_id = doc_store.create("retry.md", resolved)
        doc_store.update_status(doc_id, "failed")

        reused = _acquire_doc_id(doc_store, vector_store, path, "retry.md", "信号与系统")
        assert reused == doc_id
        assert doc_store.get(doc_id)["status"] == "processing"
        assert len(doc_store.list()) == 1

    def test_acquire_reuses_done_record(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "done.md"
        path.write_text("x", encoding="utf-8")
        resolved = str(path.resolve())

        doc_id = doc_store.create("done.md", resolved)
        doc_store.update_status(doc_id, "done", chunk_count=3)
        vector_store.upsert(
            [{
                "doc_id": str(doc_id),
                "source_file": "done.md",
                "chunk_index": 0,
                "course": "信号与系统",
                "text": "old chunk",
            }],
            [[0.2] * 384],
        )

        reused = _acquire_doc_id(doc_store, vector_store, path, "done.md", "信号与系统")
        assert reused == doc_id
        assert len(doc_store.list()) == 1
        assert vector_store.search([0.2] * 384, top_k=5) == []

    def test_fail_ingest_cleans_vectors(self, doc_store, vector_store, temp_dir):
        path = temp_dir / "fail.md"
        path.write_text("content", encoding="utf-8")
        doc_id = doc_store.create("fail.md", str(path.resolve()))
        doc_store.update_status(doc_id, "processing")

        vector_store.upsert(
            [{
                "doc_id": str(doc_id),
                "source_file": "fail.md",
                "chunk_index": 0,
                "course": "信号与系统",
                "text": "content",
            }],
            [[0.1] * 384],
        )

        _fail_ingest(vector_store, doc_store, doc_id)
        assert doc_store.get(doc_id)["status"] == "failed"
        assert vector_store.search([0.1] * 384, top_k=5) == []
