"""单元测试：SQLiteDocStore CRUD 操作。"""


class TestDocStore:
    """文档元数据 CRUD 测试，使用隔离的 SQLite 实例。"""

    def test_create_and_get(self, doc_store):
        """创建文档记录后可以读取。"""
        doc_id = doc_store.create(
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            course="信号与系统",
        )
        assert doc_id > 0

        doc = doc_store.get(doc_id)
        assert doc is not None
        assert doc["filename"] == "test.pdf"
        assert doc["status"] == "pending"
        assert doc["chunk_count"] == 0
        assert doc["course"] == "信号与系统"

    def test_update_status(self, doc_store):
        """更新文档状态。"""
        doc_id = doc_store.create("test.md", "/tmp/test.md")
        doc_store.update_status(doc_id, "processing")
        assert doc_store.get(doc_id)["status"] == "processing"

        doc_store.update_status(doc_id, "done", chunk_count=15)
        doc = doc_store.get(doc_id)
        assert doc["status"] == "done"
        assert doc["chunk_count"] == 15

    def test_list_documents(self, doc_store):
        """列出全部文档。"""
        doc_store.create("a.pdf", "/tmp/a.pdf")
        doc_store.create("b.pdf", "/tmp/b.pdf")
        docs = doc_store.list()
        assert len(docs) == 2
        filenames = {d["filename"] for d in docs}
        assert filenames == {"a.pdf", "b.pdf"}

    def test_delete(self, doc_store):
        """删除文档后查询返回 None。"""
        doc_id = doc_store.create("test.txt", "/tmp/test.txt")
        doc_store.delete(doc_id)
        assert doc_store.get(doc_id) is None

    def test_get_nonexistent(self, doc_store):
        """查询不存在的文档返回 None。"""
        assert doc_store.get(99999) is None

    def test_health_check(self, doc_store):
        """健康检查通过。"""
        assert doc_store.health_check() is True

    def test_find_by_path(self, doc_store):
        doc_id = doc_store.create("a.md", "/tmp/a.md")
        found = doc_store.find_by_path("/tmp/a.md")
        assert found is not None
        assert found["id"] == doc_id

    def test_recover_stale_processing(self, doc_store):
        doc_id = doc_store.create("b.md", "/tmp/b.md")
        doc_store.update_status(doc_id, "processing")
        n = doc_store.recover_stale_processing()
        assert n == 1
        assert doc_store.get(doc_id)["status"] == "failed"
