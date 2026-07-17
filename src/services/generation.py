"""生成：拼 prompt、调 LLM、格式化 citations 与 grounded。"""

import logging

from src.config import config
from src.services.llm import OpenAIClient

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """你是一位课程答疑助教。请根据以下参考资料回答问题。

回答规则：
1. 优先使用参考资料中的内容，直接引用其中的定义与公式。
2. 数学公式用 LaTeX：行内用 $...$ 或 \\(...\\)，独立成行用 $$...$$ 或 \\[...\\]；勿把公式拆成裸字母拼写。
3. 资料相关但不完整时，可据已有信息作答，并标明哪些来自资料。
4. 勿在资料之外自行补充知识点或公式；资料确无则写「资料未包含此内容」。
5. 引用用【】标注出处，例如【第4章笔记 · 4.2 节】；每个出处单独一个标签。
6. 表述简洁、准确，便于复习。"""


def _format_context(chunks: list[dict]) -> str:
    """将检索到的 chunk 列表格式化为 LLM 可读的参考文本。"""
    parts = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        src = meta.get("source_file", "未知")
        src_short = src.replace(".md", "").replace(".pdf", "").replace(".txt", "")
        text = c.get("text", "")
        first_line = text.split("\n", 1)[0].strip().lstrip("§ ")
        if len(first_line) > 40:
            first_line = first_line[:37] + "..."
        label = f"【{src_short} · {first_line}】"
        parts.append(f"{label}\n{text}")
    return "\n\n".join(parts)


def _build_citations(chunks: list[dict]) -> list[dict]:
    citations = []
    for c in chunks:
        meta = c.get("metadata", {})
        text = c.get("text", "")
        citations.append({
            "source_file": meta.get("source_file", "未知"),
            "page": meta.get("page"),
            "snippet": text[:200].replace("\n", " "),
            "score": round(c.get("score", 0), 4),
        })
    return citations


def _build_messages(context: list[dict], question: str) -> list[dict]:
    context_text = _format_context(context)
    return [
        {"role": "system", "content": QA_SYSTEM_PROMPT},
        {"role": "user", "content": f"参考资料：\n\n{context_text}\n\n学生问题：{question}"},
    ]


def generate(
    context: list[dict],
    question: str,
    llm: OpenAIClient,
) -> dict:
    if not context:
        return {
            "answer": "资料库中未找到相关内容",
            "citations": [],
            "grounded": False,
        }

    messages = _build_messages(context, question)
    answer = llm.chat(messages, temperature=config.llm.temperature)
    logger.info(
        "LLM 生成完成: question='%s...' answer_len=%d",
        question[:40], len(answer),
    )

    return {
        "answer": answer,
        "citations": _build_citations(context),
        "grounded": True,
    }


def stream_generate(
    context: list[dict],
    question: str,
    llm: OpenAIClient,
):
    """流式生成：yield {"type":"delta","text":str}，最后 yield done 载荷。"""
    messages = _build_messages(context, question)
    parts: list[str] = []
    for delta in llm.chat_stream(messages, temperature=config.llm.temperature):
        parts.append(delta)
        yield {"type": "delta", "text": delta}
    answer = "".join(parts)
    logger.info(
        "LLM 流式生成完成: question='%s...' answer_len=%d",
        question[:40],
        len(answer),
    )
    yield {
        "type": "done",
        "data": {
            "answer": answer,
            "citations": _build_citations(context),
            "grounded": True,
        },
    }
