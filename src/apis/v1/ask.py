"""POST /api/v1/ask — 问答接口（支持 SSE 流式）。"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette import status

from src.dependencies import get_current_user, get_llm_client, get_vector_store
from src.exceptions import AppException
from src.models import AskRequest
from src.services.llm import OpenAIClient
from src.services.query import ask as query_ask
from src.services.query import ask_stream as query_ask_stream
from src.services.storage.vector_store import ChromaVectorStore

router = APIRouter(prefix="/ask", tags=["ask"])


def _sse_encode(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("")
async def ask_question(
    body: AskRequest,
    vs: ChromaVectorStore = Depends(get_vector_store),
    llm: OpenAIClient = Depends(get_llm_client),
    _user=Depends(get_current_user),
):
    """接收问题，调 query 返回答案与引用。stream=true 时返回 SSE。"""
    if body.stream:
        def event_gen():
            try:
                for line in _sse_encode(
                    query_ask_stream(
                        question=body.question,
                        mode=body.mode,
                        vs=vs,
                        llm=llm,
                    )
                ):
                    yield line
            except AppException as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': exc.message}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    result = query_ask(
        question=body.question,
        mode=body.mode,
        vs=vs,
        llm=llm,
    )

    return {
        "code": status.HTTP_200_OK,
        "data": result.model_dump(),
    }
