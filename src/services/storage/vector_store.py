"""ChromaDB 向量存储。检索按 course_id 过滤（docs/04 4.2）。"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings

from src.exceptions import AppException, ServiceUnavailableException

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """向量存取：upsert、search、delete_by_doc_id。"""

    def __init__(self, persist_path: str, collection_name: str = "exam_rag"):
        self._persist_path = str(persist_path)
        self._collection_name = collection_name
        Path(self._persist_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self._persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def stored_embedding_dim(self) -> int | None:
        """已有向量维度；空集合或无法读取时返回 None。"""
        if self._collection.count() == 0:
            return None
        peek = self._collection.peek(limit=1)
        embeddings = peek.get("embeddings")
        if embeddings is None:
            # 部分 Chroma 版本 peek 默认不含向量，再显式取一次
            try:
                got = self._collection.get(
                    ids=peek["ids"][:1], include=["embeddings"]
                )
                embeddings = got.get("embeddings")
            except Exception:
                return None
        if embeddings is None or len(embeddings) == 0:
            return None
        first = embeddings[0]
        if first is None:
            return None
        return int(len(first))

    def recreate_collection(self) -> None:
        name = self._collection_name
        try:
            self._client.delete_collection(name)
        except Exception as e:
            logger.warning("删除旧集合失败（可忽略）: %s", e)
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def ensure_embedding_dim(self, dim: int) -> bool:
        """维度可知且冲突时重建集合。空集合的维度锁由 upsert 重试处理。"""
        if dim <= 0:
            raise ValueError("embedding 维度必须为正")
        current = self.stored_embedding_dim()
        if current is None or current == dim:
            return False
        logger.warning(
            "Embedding 维度变更 %d → %d，重建空向量集合（旧向量已失效）",
            current,
            dim,
        )
        self.recreate_collection()
        return True

    def upsert(self, chunk_dicts: list[dict], embeddings: list[list[float]]) -> bool:
        """写入向量。返回是否因维度变更重建过集合。"""
        if not chunk_dicts:
            return False
        if len(chunk_dicts) != len(embeddings):
            raise ValueError("chunk_dicts 与 embeddings 长度不一致")

        dim = len(embeddings[0])
        if any(len(v) != dim for v in embeddings):
            raise ValueError("同一批 embeddings 维度不一致")
        wiped = self.ensure_embedding_dim(dim)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for chunk in chunk_dicts:
            doc_id = str(chunk["doc_id"])
            idx = int(chunk["chunk_index"])
            course_id = str(chunk.get("course_id") or "")
            if not course_id:
                raise ValueError("chunk 缺少 course_id，禁止写入")
            ids.append(f"{doc_id}_{idx}")
            documents.append(chunk["text"])
            metadatas.append({
                "doc_id": doc_id,
                "source_file": chunk.get("source_file", ""),
                "chunk_index": idx,
                "course": chunk.get("course", ""),
                "course_id": course_id,
                "college_id": chunk.get("college_id", ""),
                "page": chunk.get("page") if chunk.get("page") is not None else -1,
            })

        def _do_upsert() -> None:
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        try:
            _do_upsert()
        except Exception as e:
            if "dimension" not in str(e).lower():
                raise
            # Chroma 空集合仍可能锁旧维度
            logger.warning("upsert 维度冲突，强制重建集合后重试: %s", e)
            self.recreate_collection()
            wiped = True
            try:
                _do_upsert()
            except Exception as e2:
                raise AppException(
                    f"向量维度不匹配: {e2}。已尝试重建集合仍失败，请重启服务后再试。",
                    status_code=409,
                ) from e2
        return wiped

    def search(
        self,
        query_vec: list[float],
        top_k: int = 5,
        *,
        course_id: str | None = None,
    ) -> list[dict]:
        if not course_id:
            raise ValueError("search 必须提供 course_id，禁止全库检索")
        if top_k <= 0 or self._collection.count() == 0:
            return []

        try:
            results = self._collection.query(
                query_embeddings=[query_vec],
                n_results=min(top_k, self._collection.count()),
                where={"course_id": course_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                raise AppException(
                    f"检索向量维度与资料库不一致: {e}。"
                    "请统一 Embedding 模型后重新扫描入库。",
                    status_code=409,
                ) from e
            logger.error("向量检索失败: %s", e)
            raise ServiceUnavailableException(
                "向量检索服务不可用", detail=str(e)
            ) from e

        hits: list[dict] = []
        if not results["ids"] or not results["ids"][0]:
            return hits

        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] or {}
            distance = results["distances"][0][i]
            score = max(0.0, 1.0 - distance)
            page = meta.get("page")
            if page == -1:
                page = None
            hits.append({
                "id": chunk_id,
                "text": results["documents"][0][i],
                "score": score,
                "metadata": {
                    "doc_id": meta.get("doc_id", ""),
                    "source_file": meta.get("source_file", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "course": meta.get("course", ""),
                    "course_id": meta.get("course_id", ""),
                    "college_id": meta.get("college_id", ""),
                    "page": page,
                },
            })

        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

    def rebind_course_id(
        self,
        from_course_id: str,
        to_course_id: str,
        *,
        course: str | None = None,
        college_id: str | None = None,
    ) -> int:
        """把旧 course_id 的 chunk metadata 改到新课（升级迁移用）。"""
        if not from_course_id or not to_course_id:
            raise ValueError("from/to course_id 不能为空")
        if from_course_id == to_course_id:
            return 0
        try:
            results = self._collection.get(
                where={"course_id": from_course_id},
                include=["metadatas"],
            )
        except Exception as e:
            logger.error("读取待迁移向量失败: %s", e)
            raise ServiceUnavailableException(
                "向量迁移失败", detail=str(e)
            ) from e

        ids = results.get("ids") or []
        if not ids:
            return 0
        metadatas = results.get("metadatas") or []
        new_metas: list[dict] = []
        for meta in metadatas:
            m = dict(meta or {})
            m["course_id"] = to_course_id
            if course is not None:
                m["course"] = course
            if college_id is not None:
                m["college_id"] = college_id
            new_metas.append(m)
        try:
            self._collection.update(ids=ids, metadatas=new_metas)
        except Exception as e:
            logger.error("写入迁移向量失败: %s", e)
            raise ServiceUnavailableException(
                "向量迁移失败", detail=str(e)
            ) from e
        return len(ids)

    def delete_by_doc_id(self, doc_id: str) -> None:
        try:
            self._collection.delete(where={"doc_id": doc_id})
            logger.info("已删除 doc_id=%s 的向量", doc_id)
        except Exception as e:
            logger.error("按 metadata 删除向量失败 doc_id=%s: %s", doc_id, e)
            raise ServiceUnavailableException("向量删除失败", detail=str(e)) from e

    def health_check(self) -> bool:
        try:
            self._collection.count()
            return True
        except Exception as e:
            logger.error("ChromaDB 健康检查失败: %s", e)
            return False

    def close(self) -> None:
        # ponytail: Chroma 无显式 close；释放引用以便 Windows 测试 teardown 解锁文件
        self._collection = None
        self._client = None
