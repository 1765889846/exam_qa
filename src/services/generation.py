"""生成：拼 prompt、调 LLM、格式化 citations 与 grounded。"""

import logging

from src.config import config
from src.services.llm import OpenAIClient

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """你是一位信号与系统课程的辅导助教。请根据以下参考资料回答学生的问题。

回答规则：
1. 优先使用参考资料中的内容回答，直接引用资料中的定义和公式（包括 $$...$$ 格式的 LaTeX 公式）。
2. 如果资料包含相关内容但不够完整，请根据已有信息尽力回答，标注哪些来自资料。
3. 不要在资料之外自行补充知识点或公式——如果资料真的没有，就说"资料未包含此内容"。
4. 引用时直接使用【】标签注明出处，例如【第4章_信道与信道容量_复习 · 4.2 信道容量】。每个出处用单独标签，不要合并。
5. 保持回答简洁、准确，适合课程学习。"""


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
