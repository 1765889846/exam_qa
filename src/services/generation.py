"""生成：拼 prompt、调 LLM、组装 citations。"""

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

CONCEPT_SYSTEM_PROMPT = """你是一位课程答疑助教。学生在检索某个知识点，请根据参考资料做结构化聚合。

回答结构（按此顺序，缺则写「资料未包含」）：
1. **定义**：该知识点的核心定义与含义。
2. **公式**：相关公式（LaTeX：$...$ / $$...$$），并简要说明符号。
3. **例题**：资料中的例题或典型应用；若无例题，写明并给一句基于资料的应用提示（勿编造题目）。

其他规则：
- 只依据参考资料，勿补充资料外知识点。
- 引用用【】标注出处；每个出处单独一个标签。
- 表述简洁，便于复习。"""


def _format_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        meta = c.get("metadata", {})
        src = meta.get("source_file", "未知")
        src_short = src.replace(".md", "").replace(".pdf", "").replace(".txt", "")
        text = c.get("text", "")
        first_line = text.split("\n", 1)[0].strip().lstrip("§ ")
        if len(first_line) > 40:
            first_line = first_line[:37] + "..."
        parts.append(f"【{src_short} · {first_line}】\n{text}")
    return "\n\n".join(parts)


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "source_file": c.get("metadata", {}).get("source_file", "未知"),
            "page": c.get("metadata", {}).get("page"),
            "snippet": c.get("text", "")[:200].replace("\n", " "),
            "score": round(c.get("score", 0), 4),
        }
        for c in chunks
    ]


def _build_messages(context: list[dict], question: str, mode: str = "qa") -> list[dict]:
    ctx = _format_context(context)
    if mode == "concept":
        system, user = CONCEPT_SYSTEM_PROMPT, f"参考资料：\n\n{ctx}\n\n请聚合知识点「{question}」（定义→公式→例题）。"
    else:
        system, user = QA_SYSTEM_PROMPT, f"参考资料：\n\n{ctx}\n\n学生问题：{question}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate(context: list[dict], question: str, llm: OpenAIClient, mode: str = "qa") -> dict:
    if not context:
        return {"answer": "资料库中未找到相关内容", "citations": [], "grounded": False}
    answer = llm.chat(_build_messages(context, question, mode=mode), temperature=config.llm.temperature)
    logger.info("LLM 生成完成: mode=%s len=%d", mode, len(answer))
    return {"answer": answer, "citations": _build_citations(context), "grounded": True}


def stream_generate(context: list[dict], question: str, llm: OpenAIClient, mode: str = "qa"):
    parts: list[str] = []
    for delta in llm.chat_stream(
        _build_messages(context, question, mode=mode), temperature=config.llm.temperature
    ):
        parts.append(delta)
        yield {"type": "delta", "text": delta}
    yield {
        "type": "done",
        "data": {
            "answer": "".join(parts),
            "citations": _build_citations(context),
            "grounded": True,
        },
    }
