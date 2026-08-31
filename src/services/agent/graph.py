"""LangGraph Agent 图：retrieve → grade → rewrite/generate → finish。"""

from __future__ import annotations

import logging
from functools import partial
from datetime import date

from src.config import config
from src.exceptions import BadRequestException, LLMAPIException, ServiceUnavailableException
from src.services.agent import nodes
from src.services.agent.state import AgentState
from src.services.evidence_metadata import normalize_scope
from src.services.llm import OpenAIClient
from src.services.storage.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

_DEFAULT_MAX_STEPS = 3
_SUPPORTED_MODES = frozenset({"qa", "concept"})


def _import_langgraph():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise ServiceUnavailableException(
            "缺少 langgraph 依赖，请运行 `uv add langgraph` 后重启服务",
            detail=str(exc),
        ) from exc
    return END, StateGraph


def build_agent_graph(vs: ChromaVectorStore, llm: OpenAIClient):
    END, StateGraph = _import_langgraph()
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", partial(nodes.retrieve_node, vs=vs))
    graph.add_node("grade", partial(nodes.grade_node, llm=llm))
    graph.add_node("rewrite", partial(nodes.rewrite_node, llm=llm))
    graph.add_node("generate", partial(nodes.generate_node, llm=llm))
    graph.add_node("refuse", nodes.refuse_node)
    graph.add_node("finish", nodes.finish_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        lambda state: state.get("decision") or "refuse",
        {
            "generate": "generate",
            "rewrite": "rewrite",
            "refuse": "refuse",
        },
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "finish")
    graph.add_edge("refuse", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


def build_agentic_graph(vs: ChromaVectorStore, llm: OpenAIClient):
    """P2-C：模型决定工具调用，图只负责受控路由与循环上限。"""
    END, StateGraph = _import_langgraph()
    graph = StateGraph(AgentState)
    graph.add_node("agent", partial(nodes.agentic_agent_node, llm=llm))
    graph.add_node("tool", partial(nodes.agentic_tool_node, vs=vs, llm=llm))
    graph.add_node("refuse", nodes.refuse_node)
    graph.add_node("finish", nodes.finish_node)
    graph.set_entry_point("agent")

    def route(state: AgentState) -> str:
        decision = state.get("decision") or "refuse"
        if decision == "tools":
            return "tool" if int(state.get("tool_rounds", 0)) < int(state["max_steps"]) else "refuse"
        return "finish" if decision == "finish" else "refuse"

    graph.add_conditional_edges("agent", route, {"tool": "tool", "finish": "finish", "refuse": "refuse"})
    graph.add_edge("tool", "agent")
    graph.add_edge("refuse", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


def run_agent(
    question: str,
    course_id: str,
    vs: ChromaVectorStore,
    llm: OpenAIClient,
    *,
    mode: str = "qa",
    max_steps: int = _DEFAULT_MAX_STEPS,
    top_k: int | None = None,
    score_threshold: float | None = None,
    scenario: str | None = None,
    as_of: str | None = None,
    agentic: bool = False,
) -> dict:
    """执行 Agent 循环，返回 answer / citations / grounded / steps / queries。"""
    if mode not in _SUPPORTED_MODES:
        raise BadRequestException(f"仅支持 mode=qa|concept，收到 mode={mode}")
    if max_steps <= 0:
        raise BadRequestException("max_steps 必须大于 0")

    question = (question or "").strip()
    if not question:
        raise BadRequestException("问题内容不能为空")
    if not course_id or not course_id.strip():
        raise BadRequestException("course_id 不能为空")
    if as_of:
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise BadRequestException("as_of 必须是有效日期，格式 YYYY-MM-DD") from exc
    scenario = normalize_scope(scenario) if scenario else None

    if top_k is None:
        top_k = config.retrieval.top_k
    if score_threshold is None:
        score_threshold = config.retrieval.score_threshold

    initial: AgentState = {
        "question": question,
        "course_id": course_id,
        "mode": mode,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "max_steps": max_steps,
        "attempts": 0,
        "current_query": question,
        "queries": [],
        "steps": [],
        "chunks": [],
        "citations": [],
        "answer": "",
        "grounded": False,
        "decision": "",
        "scenario": scenario,
        "as_of": as_of,
        "messages": [],
        "pending_tool_calls": [],
        "tool_calls": [],
        "tool_rounds": 0,
    }
    used_agentic = bool(agentic and llm.configured)
    if used_agentic:
        try:
            final = build_agentic_graph(vs, llm).invoke(initial)
        except LLMAPIException as exc:
            logger.warning("Agentic tool calling 不可用，降级 P2-B: %s", exc)
            used_agentic = False
            final = build_agent_graph(vs, llm).invoke(initial)
    else:
        final = build_agent_graph(vs, llm).invoke(initial)

    logger.info(
        "Agent 完成: course=%s agentic=%s steps=%d grounded=%s",
        course_id,
        used_agentic,
        len(final.get("steps") or []),
        bool(final.get("grounded")),
    )
    return {
        "answer": final.get("answer", ""),
        "citations": final.get("citations") or [],
        "grounded": bool(final.get("grounded", False)),
        "steps": final.get("steps") or [],
        "queries": final.get("queries") or [],
        "tool_calls": final.get("tool_calls") or [],
        "agentic": used_agentic,
        "agent_used": True,
    }
