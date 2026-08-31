"""POST /agent/run — LangGraph Agent 循环（P2-B）。"""

from fastapi import APIRouter, Depends
from starlette import status

from src.dependencies import (
    get_catalog_store,
    get_current_user,
    get_llm_client,
    get_vector_store,
)
from src.models import AgentRunData, AgentRunRequest
from src.services.agent import run_agent
from src.services.llm import OpenAIClient
from src.services.storage.catalog_store import CatalogStore
from src.services.storage.vector_store import ChromaVectorStore

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run")
async def agent_run(
    body: AgentRunRequest,
    vs: ChromaVectorStore = Depends(get_vector_store),
    llm: OpenAIClient = Depends(get_llm_client),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    catalog.require_course(body.course_id)
    result = run_agent(
        question=body.question,
        course_id=body.course_id,
        vs=vs,
        llm=llm,
        mode=body.mode,
        max_steps=body.max_steps,
        top_k=body.top_k,
        score_threshold=body.score_threshold,
    )
    return {
        "code": status.HTTP_200_OK,
        "data": AgentRunData(
            answer=result["answer"],
            citations=result["citations"],
            grounded=result["grounded"],
            steps=result["steps"],
            agent_used=result["agent_used"],
        ).model_dump(),
    }
