"""GET/POST/DELETE /api/v1/conversations —— 多轮对话管理。"""

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.dependencies import get_conversation_store, get_current_user
from src.services.storage.conversation_store import ConversationStore

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("")
async def create_conversation(
    course_id: str = Query(..., description="课程 ID"),
    title: str = Query("新对话", description="对话标题"),
    store: ConversationStore = Depends(get_conversation_store),
    _user=Depends(get_current_user),
):
    conv = store.create_conversation(course_id, title)
    return {"code": status.HTTP_200_OK, "data": conv}


@router.get("")
async def list_conversations(
    course_id: str = Query(..., description="课程 ID"),
    store: ConversationStore = Depends(get_conversation_store),
    _user=Depends(get_current_user),
):
    convs = store.list_conversations(course_id)
    return {"code": status.HTTP_200_OK, "data": convs}


@router.delete("/{conv_id}")
async def delete_conversation(
    conv_id: str,
    course_id: str = Query(..., description="课程 ID（校验归属）"),
    store: ConversationStore = Depends(get_conversation_store),
    _user=Depends(get_current_user),
):
    conv = store.get_conversation(conv_id)
    if not conv:
        return {"code": 404, "message": "对话不存在"}
    if conv.get("course_id") != course_id:
        return {"code": 403, "message": "无权操作该对话"}
    store.delete_conversation(conv_id)
    return {"code": status.HTTP_200_OK, "data": None}
