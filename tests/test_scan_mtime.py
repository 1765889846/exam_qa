"""mtime 变更检测与 scan 重索引。"""

import time

from src.services.ingestion import _needs_reindex, ingest_file, scan_knowledge_dir


class TestNeedsReindex:
    def test_new_file(self):
        assert _needs_reindex(None, 100.0) is True

    def test_done_unchanged(self):
        assert _needs_reindex({"status": "done", "file_mtime": 100.0}, 100.0) is False

    def test_done_mtime_changed(self):
        assert _needs_reindex({"status": "done", "file_mtime": 100.0}, 200.0) is True

    def test_done_missing_mtime(self):
        assert _needs_reindex({"status": "done", "file_mtime": None}, 100.0) is True

    def test_failed_retries(self):
        assert _needs_reindex({"status": "failed", "file_mtime": 100.0}, 100.0) is True

    def test_processing_skipped(self):
        assert _needs_reindex({"status": "processing", "file_mtime": None}, 100.0) is False


class TestScanReindex:
    def test_scan_reindexes_on_mtime_change(self, temp_dir, vector_store, doc_store, monkeypatch):
        knowledge = temp_dir / "knowledge"
        knowledge.mkdir()
        monkeypatch.setattr("src.services.ingestion.config.storage.knowledge_dir", str(knowledge))

        md = knowledge / "note.md"
        md.write_text("# v1\n短内容", encoding="utf-8")
        ingest_file(str(md), vector_store, doc_store)
        doc = doc_store.get(1)
        old_mtime = doc["file_mtime"]
        old_chunks = doc["chunk_count"]

        time.sleep(0.05)
        md.write_text("# v2\n" + "更新内容。" * 80, encoding="utf-8")
        scan_knowledge_dir(vector_store, doc_store)

        doc = doc_store.get(1)
        assert doc["status"] == "done"
        assert doc["file_mtime"] > old_mtime
        assert doc["chunk_count"] >= old_chunks
