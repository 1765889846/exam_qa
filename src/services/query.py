"""查询编排：按 mode 路由，串联检索与生成，组装 AnswerData。"""

import logging

from src.config import config
from src.exceptions import BadRequestException, LLMAPIException
from src.models import AnswerData, Citation
from src.services.generation import generate, stream_generate
from src.services.llm import OpenAIClient
from src.services.retrieval import retrieve
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

P0_MODES = frozenset({"qa"})


def ask(
    question: str,
    mode: str,
    vs: ChromaVectorStore,
    llm: OpenAIClient,
    course_id: str,
) -> AnswerData:
    """检索 + 生成；caller 须保证 course_id 有效。"""
    if mode not in P0_MODES:
        raise BadRequestException(f"P0 仅支持 mode=qa，收到 mode={mode}")
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")

    logger.info(
        "查询开始: course_id=%s mode=%s question='%s...'",
        course_id,
        mode,
        question[:60],
    )

    hits = retrieve(
        query=question,
        vs=vs,
        course_id=course_id,
    )

    if not hits:
        logger.info("检索拒答: 无过阈命中 threshold=%.4f", config.retrieval.score_threshold)
        return AnswerData(
            answer="资料库中未找到相关内容",
            citations=[],
            grounded=False,
        )

    if not llm.configured:
        raise LLMAPIException("AI 服务未配置：请设置 LLM_API_KEY")

    result = generate(context=hits, question=question, llm=llm)

    citations = [
        Citation(
            source_file=c["source_file"],
            page=c.get("page"),
            snippet=c["snippet"],
            score=c["score"],
        )
        for c in result["citations"]
    ]

    return AnswerData(
        answer=result["answer"],
        citations=citations,
        grounded=result["grounded"],
    )


def ask_stream(
    question: str,
    mode: str,
    vs: ChromaVectorStore,
    llm: OpenAIClient,
    course_id: str,
):
    """流式问答：yield SSE 事件 dict。"""
    if mode not in P0_MODES:
        raise BadRequestException(f"P0 仅支持 mode=qa，收到 mode={mode}")
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")

    logger.info(
        "流式查询开始: course_id=%s mode=%s question='%s...'",
        course_id,
        mode,
        question[:60],
    )
    yield {"type": "phase", "phase": "retrieving"}

    hits = retrieve(
        query=question,
        vs=vs,
        course_id=course_id,
    )

    if not hits:
        logger.info(
            "检索拒答(流式): 无过阈命中 threshold=%.4f",
            config.retrieval.score_threshold,
        )
        yield {
            "type": "done",
            "data": AnswerData(
                answer="资料库中未找到相关内容",
                citations=[],
                grounded=False,
            ).model_dump(),
        }
        return

    if not llm.configured:
        yield {"type": "error", "message": "AI 服务未配置：请设置 LLM_API_KEY"}
        return

    yield {"type": "phase", "phase": "generating"}
    for event in stream_generate(context=hits, question=question, llm=llm):
        if event["type"] == "delta":
            yield event
            continue
        if event["type"] == "done":
            data = event["data"]
            citations = [
                Citation(
                    source_file=c["source_file"],
                    page=c.get("page"),
                    snippet=c["snippet"],
                    score=c["score"],
                )
                for c in data["citations"]
            ]
            yield {
                "type": "done",
                "data": AnswerData(
                    answer=data["answer"],
                    citations=citations,
                    grounded=data["grounded"],
                ).model_dump(),
            }
