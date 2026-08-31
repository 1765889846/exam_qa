"""Agent 节点：retrieve → grade → rewrite / generate → refuse / finish。"""

from __future__ import annotations

import logging

from src.services import generation
from src.services.agent import tools
from src.services.agent.state import AgentState
from src.services.llm import OpenAIClient
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

_REFUSAL = "资料库中未找到相关内容"


def retrieve_node(state: AgentState, vs: ChromaVectorStore) -> dict:
    query = state.get("current_query") or state["question"]
    hits = tools.retrieve_tool(
        query,
        vs,
        state["course_id"],
        int(state["top_k"]),
    )
    attempts = int(state.get("attempts", 0)) + 1
    logger.info(
        "Agent 检索: course=%s attempt=%d query='%s...' hits=%d",
        state.get("course_id"),
        attempts,
        query.strip()[:60],
        len(hits),
    )
    return {
        "chunks": hits,
        "attempts": attempts,
        "queries": [query],
        "steps": [f"retrieve: {query}"],
    }


def grade_node(state: AgentState, llm: OpenAIClient) -> dict:
    chunks = state.get("chunks") or []
    threshold = float(state.get("score_threshold", 0.0))
    attempts = int(state.get("attempts", 0))
    max_steps = int(state.get("max_steps", 1))
    best = max((float(h.get("score", 0.0)) for h in chunks), default=0.0)

    if chunks and best >= threshold:
        decision = "generate"
        note = f"score={best:.3f} ≥ {threshold}"
    elif attempts >= max_steps or not llm.configured:
        decision = "refuse"
        note = "达到最大轮数" if attempts >= max_steps else "LLM 未配置"
    else:
        decision = "rewrite"
        note = f"score={best:.3f} < {threshold}"

    logger.info("Agent 判定: course=%s decision=%s (%s)", state.get("course_id"), decision, note)
    return {"decision": decision, "steps": [f"grade: {note}"]}


def _rewrite_query(query: str, llm: OpenAIClient) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "你是课程资料检索改写助手。把用户问题改写成更适合检索的短查询，"
                "保留原意，输出单个查询句，不要解释、不要标点包裹。"
            ),
        },
        {"role": "user", "content": f"原问题：{query}"},
    ]
    rewritten = (llm.chat(messages, temperature=0.0) or "").strip()
    return rewritten or query


def rewrite_node(state: AgentState, llm: OpenAIClient) -> dict:
    query = state.get("current_query") or state["question"]
    new_query = _rewrite_query(query, llm)
    logger.info("Agent 改写: course=%s '%s...' → '%s...'", state.get("course_id"), query.strip()[:40], new_query.strip()[:40])
    return {
        "current_query": new_query,
        "queries": [new_query],
        "steps": [f"rewrite: {new_query}"],
    }


def generate_node(state: AgentState, llm: OpenAIClient) -> dict:
    chunks = state.get("chunks") or []
    result = generation.generate(
        context=chunks,
        question=state["question"],
        llm=llm,
        mode=state.get("mode", "qa"),
    )
    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "grounded": bool(result["grounded"]),
        "steps": ["generate"],
    }


def refuse_node(state: AgentState) -> dict:
    return {
        "answer": _REFUSAL,
        "citations": [],
        "grounded": False,
        "steps": ["refuse"],
    }


def finish_node(state: AgentState) -> dict:
    return {}
