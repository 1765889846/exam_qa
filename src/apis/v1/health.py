"""GET /api/v1/health — 检查存储、Embedding、LLM 可达性。"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette import status

from src.dependencies import get_doc_store, get_embedding_client, get_vector_store
from src.services.embedding import EmbeddingClient
from src.services.storage.doc_store import SQLiteDocStore
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    request: Request,
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    embedding: EmbeddingClient = Depends(get_embedding_client),
):
    """无鉴权健康检查。不做 LLM/Embedding 网络探测，避免阻塞事件循环。"""
    from src.config import config

    chroma_ok = vs.health_check()
    sqlite_ok = ds.health_check()
    embedding_status = embedding.status()
    llm_status = "ok" if config.llm.api_key else "unavailable"
    request.app.state.llm_health = llm_status

    core_ok = chroma_ok and sqlite_ok
    embedding_ok = embedding_status == "ok"
    llm_ok = llm_status == "ok"
    all_ok = core_ok and embedding_ok and llm_ok
    http_status = status.HTTP_200_OK if core_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    overall = "healthy" if all_ok else ("degraded" if core_ok else "unavailable")

    return JSONResponse(
        status_code=http_status,
        content={
            "code": http_status,
            "data": {
                "status": overall,
                "chromadb": "ok" if chroma_ok else "unavailable",
                "sqlite": "ok" if sqlite_ok else "unavailable",
                "embedding": embedding_status,
                "llm": llm_status,
            },
        },
    )
