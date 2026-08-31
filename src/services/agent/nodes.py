"""Agent 节点：retrieve → grade → rewrite / generate → refuse / finish。"""

from __future__ import annotations

import json
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
    kwargs: dict[str, object] = {}
    if state.get("scenario"):
        kwargs["scenario"] = state["scenario"]
    if state.get("as_of"):
        kwargs["as_of"] = state["as_of"]
    hits = tools.retrieve_tool(query, vs, state["course_id"], int(state["top_k"]), **kwargs)
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


_AGENTIC_SYSTEM = """你是受控的课程资料 RAG Agent。
只能依据工具返回的课程资料回答；需要证据时必须先调用工具。
工具只读取当前课程，不能要求系统绕过课程范围。资料不足时不要猜测，直接说明无法确认。
完成取证后输出简洁的最终中文答案，不要输出工具调用 JSON。"""

_TOOL_ARG_KEYS = {
    "search_pdf": {"query", "top_k"},
    "read_page": {"doc_id", "source_file", "page"},
    "extract_table": {"query", "doc_id", "source_file", "page", "top_k"},
    "analyze_chart": {"query", "doc_id", "page", "top_k"},
    "quote_source": {"query", "top_k"},
}


def _parse_tool_args(name: str, raw_args: object, top_k: int) -> dict:
    if name not in _TOOL_ARG_KEYS:
        raise ValueError(f"未知工具: {name}")
    try:
        parsed = json.loads(raw_args or "{}") if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as exc:
        raise ValueError("工具参数不是有效 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("工具参数必须是对象")
    args = {key: value for key, value in parsed.items() if key in _TOOL_ARG_KEYS[name]}
    for key, value in list(args.items()):
        if isinstance(value, str):
            args[key] = value.strip()[:500]
    if "top_k" in args:
        try:
            args["top_k"] = max(1, min(int(args["top_k"]), min(max(top_k, 1), 20)))
        except (TypeError, ValueError) as exc:
            raise ValueError("top_k 必须是整数") from exc
    if "page" in args:
        try:
            args["page"] = max(1, min(int(args["page"]), 10000))
        except (TypeError, ValueError) as exc:
            raise ValueError("page 必须是正整数") from exc
    if name == "read_page" and not (args.get("doc_id") or args.get("source_file")):
        raise ValueError("read_page 必须提供 doc_id 或 source_file")
    if name in {"search_pdf", "quote_source"} and not args.get("query"):
        raise ValueError(f"{name} 必须提供 query")
    return args


def _tool_observation(call: dict, args: dict, result: dict | None, error: str = "") -> dict:
    citations = (result or {}).get("citations") or []
    return {
        "id": str(call.get("id") or ""),
        "name": str(call.get("name") or ""),
        "arguments": args,
        "ok": not error,
        "citation_count": len(citations),
        "error": error,
    }


def _dedupe_citations(citations: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for citation in citations:
        key = (
            citation.get("source_file"), citation.get("page"), citation.get("snippet"),
        )
        if key not in seen:
            seen.add(key)
            result.append(citation)
    return result


def agentic_agent_node(state: AgentState, llm: OpenAIClient) -> dict:
    """请求模型决定下一步；最终答案必须已有工具引用才能通过。"""
    existing_messages = state.get("messages") or []
    is_first_turn = not existing_messages
    messages = existing_messages or [
        {"role": "system", "content": _AGENTIC_SYSTEM},
        {"role": "user", "content": state["question"]},
    ]
    response = llm.chat_with_tools(messages, tools.TOOL_SCHEMAS, temperature=0)
    content = str(response.get("content") or "").strip()
    pending = response.get("tool_calls") or []
    if pending:
        assistant_message = {
            "role": "assistant", "content": content,
            "tool_calls": [
                {
                    "id": str(call.get("id") or ""), "type": "function",
                    "function": {
                        "name": str(call.get("name") or ""),
                        "arguments": str(call.get("arguments") or "{}"),
                    },
                }
                for call in pending
            ],
        }
        return {
            "messages": ([*messages, assistant_message] if is_first_turn else [assistant_message]), "pending_tool_calls": pending,
            "decision": "tools", "steps": [f"agent: {len(pending)} tool call(s)"],
        }
    citations = state.get("citations") or []
    if content and citations:
        return {"answer": content, "grounded": True, "decision": "finish", "steps": ["agent: final answer"]}
    return {"decision": "refuse", "steps": ["agent: no grounded final answer"]}


def agentic_tool_node(state: AgentState, vs: ChromaVectorStore, llm: OpenAIClient) -> dict:
    """仅通过白名单执行工具，并将结果作为 tool message 回填模型上下文。"""
    messages: list[dict] = []
    observations: list[dict] = []
    citations: list[dict] = list(state.get("citations") or [])
    for call in state.get("pending_tool_calls") or []:
        name = str(call.get("name") or "")
        call_id = str(call.get("id") or "")
        try:
            args = _parse_tool_args(name, call.get("arguments"), int(state["top_k"]))
            result = tools.execute_tool(
                name, args, vs=vs, course_id=state["course_id"], llm=llm,
                top_k=int(state["top_k"]), scenario=state.get("scenario"), as_of=state.get("as_of"),
            )
            citations.extend(result.get("citations") or [])
            observations.append(_tool_observation(call, args, result))
            payload = result
        except Exception as exc:
            error = str(exc) or "工具执行失败"
            observations.append(_tool_observation(call, {}, None, error))
            payload = {"error": error}
        messages.append(
            {"role": "tool", "tool_call_id": call_id, "name": name, "content": json.dumps(payload, ensure_ascii=False)[:12000]}
        )
    rounds = int(state.get("tool_rounds", 0)) + 1
    return {
        "messages": messages, "tool_calls": observations,
        "citations": _dedupe_citations(citations), "pending_tool_calls": [],
        "tool_rounds": rounds, "steps": [f"tools: round {rounds}"],
    }
