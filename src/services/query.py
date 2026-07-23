"""查询编排：mode 路由 → 检索 / 章节聚合 → 生成 / 拒答。"""

import logging

from src.config import config
from src.exceptions import BadRequestException, LLMAPIException
from src.models import AnswerData, Citation
from src.services.generation import generate, stream_generate
from src.services.llm import OpenAIClient
from src.services.retrieval import retrieve
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

SUPPORTED_MODES = frozenset({"qa", "concept", "chapter"})
CONCEPT_TOP_K = 12
CHAPTER_MAX_CHUNKS = 24
_REFUSAL = "资料库中未找到相关内容"


def _validate(mode: str, course_id: str) -> None:
    if mode not in SUPPORTED_MODES:
        raise BadRequestException(f"仅支持 mode=qa|concept|chapter，收到 mode={mode}")
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")


def _citations(raw: list[dict]) -> list[Citation]:
    return [
        Citation(
            source_file=c["source_file"],
            page=c.get("page"),
            snippet=c["snippet"],
            score=c["score"],
        )
        for c in raw
    ]


def _retrieve(question: str, mode: str, vs: ChromaVectorStore, course_id: str) -> list[dict]:
    if mode == "chapter":
        hits = vs.get_by_chapter(course_id, question.strip())
        capped: list[dict] = []
        for h in hits[:CHAPTER_MAX_CHUNKS]:
            item = dict(h)
            meta = dict(h.get("metadata") or {})
            item["metadata"] = meta
            item["score"] = 1.0
            capped.append(item)
        return capped
    return retrieve(
        query=question,
        vs=vs,
        course_id=course_id,
        top_k=CONCEPT_TOP_K if mode == "concept" else None,
    )


def ask(
    question: str,
    mode: str,
    vs: ChromaVectorStore,
    llm: OpenAIClient,
    course_id: str,
) -> AnswerData:
    _validate(mode, course_id)
    logger.info("查询: course=%s mode=%s q='%s...'", course_id, mode, question[:60])

    hits = _retrieve(question, mode, vs, course_id)
    if not hits:
        logger.info("拒答 threshold=%.4f", config.retrieval.score_threshold)
        return AnswerData(answer=_REFUSAL, citations=[], grounded=False)

    if not llm.configured:
        raise LLMAPIException("AI 服务未配置：请设置 LLM_API_KEY")

    result = generate(context=hits, question=question, llm=llm, mode=mode)
    return AnswerData(
        answer=result["answer"],
        citations=_citations(result["citations"]),
        grounded=result["grounded"],
    )


def ask_stream(
    question: str,
    mode: str,
    vs: ChromaVectorStore,
    llm: OpenAIClient,
    course_id: str,
):
    _validate(mode, course_id)
    logger.info("流式查询: course=%s mode=%s q='%s...'", course_id, mode, question[:60])
    yield {"type": "phase", "phase": "retrieving"}

    hits = _retrieve(question, mode, vs, course_id)
    if not hits:
        yield {
            "type": "done",
            "data": AnswerData(answer=_REFUSAL, citations=[], grounded=False).model_dump(),
        }
        return

    if not llm.configured:
        yield {"type": "error", "message": "AI 服务未配置：请设置 LLM_API_KEY"}
        return

    yield {"type": "phase", "phase": "generating"}
    for event in stream_generate(context=hits, question=question, llm=llm, mode=mode):
        if event["type"] == "delta":
            yield event
        elif event["type"] == "done":
            data = event["data"]
            yield {
                "type": "done",
                "data": AnswerData(
                    answer=data["answer"],
                    citations=_citations(data["citations"]),
                    grounded=data["grounded"],
                ).model_dump(),
            }
