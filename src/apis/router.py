"""聚合 v1 路由，main.py 只 include 一次。"""

from fastapi import APIRouter

from src.apis.v1 import ask, config, documents, embedding, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(config.router)
api_router.include_router(embedding.router)
api_router.include_router(documents.router)
api_router.include_router(ask.router)
