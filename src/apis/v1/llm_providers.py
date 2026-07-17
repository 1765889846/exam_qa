"""GET/POST/DELETE /api/v1/llm-providers — 注册与切换对话模型。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette import status

from src.dependencies import get_current_user
from src.services import llm_providers as registry

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


class ProviderUpsert(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    format: str = Field(default="openai")
    model: str = Field(..., min_length=1)
    base_url: str = ""
    api_key: str = ""


class SetActiveRequest(BaseModel):
    name: str = Field(..., min_length=1)


@router.get("")
async def list_providers(_user=Depends(get_current_user)):
    return {"code": status.HTTP_200_OK, "data": registry.list_public()}


@router.post("")
async def upsert_provider(body: ProviderUpsert, _user=Depends(get_current_user)):
    item = registry.upsert_provider(body.model_dump())
    return {"code": status.HTTP_200_OK, "data": item}


@router.post("/active")
async def set_active(body: SetActiveRequest, _user=Depends(get_current_user)):
    data = registry.set_active(body.name)
    return {"code": status.HTTP_200_OK, "data": data}


@router.delete("/{name}")
async def delete_provider(name: str, _user=Depends(get_current_user)):
    registry.remove_provider(name)
    return {"code": status.HTTP_200_OK, "data": registry.list_public()}
