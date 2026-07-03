"""POST /api/v1/embedding/warmup — 手动加载本地模型或探测远程 API。"""

import logging

from fastapi import APIRouter, Depends
from starlette import status

from src.config import config
from src.dependencies import get_embedding_client
from src.exceptions import AppException
from src.services.embedding import EmbeddingClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["embedding"])


@router.post("/embedding/warmup")
async def warmup_embedding(embedding: EmbeddingClient = Depends(get_embedding_client)):
    """加载本地 Embedding 模型，或探测远程 API 连通性。"""
    if embedding.status() == "ok":
        return {
            "code": status.HTTP_200_OK,
            "data": {
                "status": "ok",
                "provider": embedding.provider,
                "model": embedding.model,
                "message": "向量化已就绪",
            },
        }

    if embedding.status() == "unavailable":
        raise AppException(
            "Embedding 未配置：请设置 EMBEDDING_API_KEY 或切换为本地模型",
            status_code=400,
        )

    try:
        embedding.warmup()
    except Exception as e:
        logger.exception("Embedding 加载失败")
        raise AppException(f"Embedding 加载失败: {e}", status_code=500) from e

    if embedding.status() != "ok":
        raise AppException("Embedding 加载后仍未就绪", status_code=500)

    logger.info(
        "Embedding 手动加载完成: provider=%s model=%s",
        config.embedding.provider,
        config.embedding.model,
    )
    return {
        "code": status.HTTP_200_OK,
        "data": {
            "status": "ok",
            "provider": embedding.provider,
            "model": embedding.model,
            "message": "向量化已就绪",
        },
    }
