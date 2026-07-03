"""ChromaDB 向量存储。"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings

from src.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """向量存取：upsert、search、delete_by_doc_id。"""

    def __init__(self, persist_path: str, collection_name: str = "exam_rag"):
        self._persist_path = str(persist_path)
        Path(self._persist_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self._persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunk_dicts: list[dict], embeddings: list[list[float]]) -> None:
        if not chunk_dicts:
            return
        if len(chunk_dicts) != len(embeddings):
            raise ValueError("chunk_dicts 与 embeddings 长度不一致")

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for chunk in chunk_dicts:
            doc_id = str(chunk["doc_id"])
            idx = int(chunk["chunk_index"])
            ids.append(f"{doc_id}_{idx}")
            documents.append(chunk["text"])
            metadatas.append({
                "doc_id": doc_id,
                "source_file": chunk.get("source_file", ""),
                "chunk_index": idx,
                "course": chunk.get("course", ""),
                "page": chunk.get("page") if chunk.get("page") is not None else -1,
            })

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query_vec: list[float], top_k: int = 20) -> list[dict]:
        if top_k <= 0 or self._collection.count() == 0:
            return []

        try:
            results = self._collection.query(
                query_embeddings=[query_vec],
                n_results=min(top_k, self._collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("向量检索失败: %s", e)
            raise ServiceUnavailableException("向量检索服务不可用", detail=str(e)) from e

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
                    "page": page,
                },
            })

        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

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
