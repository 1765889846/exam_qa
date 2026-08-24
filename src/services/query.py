"""查询编排：mode 路由 → 检索 / 章节聚合 → 生成 / 拒答。"""

import logging

from src.config import config
from src.exceptions import BadRequestException, LLMAPIException
from src.models import AnswerData, Citation
from src.services.generation import generate, stream_generate
from src.services.llm import OpenAIClient
from src.services.retrieval import retrieve
from src.services.storage.conversation_store import ConversationStore
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
    conversation_store: ConversationStore | None = None,
    conversation_id: str | None = None,
) -> AnswerData:
    _validate(mode, course_id)
    logger.info("查询: course=%s mode=%s conv=%s q='%s...'", course_id, mode, conversation_id, question[:60])

    history = _get_history(conversation_store, conversation_id)

    hits = _retrieve(question, mode, vs, course_id)
    if not hits:
        logger.info("拒答 threshold=%.4f", config.retrieval.score_threshold)
        _save_turn(conversation_store, conversation_id, course_id, question, _REFUSAL, [], False, mode)
        return AnswerData(answer=_REFUSAL, citations=[], grounded=False)

    if not llm.configured:
        raise LLMAPIException("AI 服务未配置：请设置 LLM_API_KEY")

    result = generate(context=hits, question=question, llm=llm, mode=mode, history=history)
    _save_turn(
        conversation_store, conversation_id, course_id,
        question, result["answer"], result["citations"], result["grounded"], mode,
    )
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
    conversation_store: ConversationStore | None = None,
    conversation_id: str | None = None,
):
    _validate(mode, course_id)
    logger.info("流式查询: course=%s mode=%s conv=%s q='%s...'", course_id, mode, conversation_id, question[:60])
    yield {"type": "phase", "phase": "retrieving"}

    history = _get_history(conversation_store, conversation_id)

    hits = _retrieve(question, mode, vs, course_id)
    if not hits:
        _save_turn(conversation_store, conversation_id, course_id, question, _REFUSAL, [], False, mode)
        yield {
            "type": "done",
            "data": AnswerData(answer=_REFUSAL, citations=[], grounded=False).model_dump(),
        }
        return

    if not llm.configured:
        yield {"type": "error", "message": "AI 服务未配置：请设置 LLM_API_KEY"}
        return

    yield {"type": "phase", "phase": "generating"}
    for event in stream_generate(context=hits, question=question, llm=llm, mode=mode, history=history):
        if event["type"] == "delta":
            yield event
        elif event["type"] == "done":
            data = event["data"]
            _save_turn(
                conversation_store, conversation_id, course_id,
                question, data["answer"], data["citations"], data["grounded"], mode,
            )
            yield {
                "type": "done",
                "data": AnswerData(
                    answer=data["answer"],
                    citations=_citations(data["citations"]),
                    grounded=data["grounded"],
                ).model_dump(),
            }


def _get_history(store: ConversationStore | None, conv_id: str | None) -> list[dict] | None:
    """获取对话历史消息，用于拼入 LLM 上下文。"""
    if not store or not conv_id:
        return None
    return store.get_history(conv_id) or None


def _save_turn(
    store: ConversationStore | None,
    conv_id: str | None,
    course_id: str,
    question: str,
    answer: str,
    citations: list,
    grounded: bool,
    mode: str,
) -> bool:
    """保存一轮问答到对话存储，自动创建不存在的对话。

    失败不阻断回答流程，但会记录 ERROR 日志；返回是否保存成功，便于调用方观测。
    """
    if not store or not conv_id:
        return True
    try:
        first_q = question.strip()
        title = first_q[:40] + ("..." if len(first_q) > 40 else "")
        store.ensure_conversation(conv_id, course_id, title)
        store.append_message(conv_id, "user", question, mode=mode)
        store.append_message(conv_id, "assistant", answer, citations=citations, grounded=grounded, mode=mode)
        return True
    except Exception:
        logger.exception(
            "保存对话消息失败 conv=%s course=%s mode=%s q='%s...'",
            conv_id,
            course_id,
            mode,
            question.strip()[:40],
        )
        return False
