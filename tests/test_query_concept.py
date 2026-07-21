"""mode=concept：更大 top_k + 聚合 prompt；不依赖真实 LLM。"""

from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import BadRequestException
from src.services import generation
from src.services.query import CONCEPT_TOP_K, ask, ask_stream


def test_concept_prompt_structure():
    msgs = generation._build_messages(
        [{"text": "卷积定理：时域卷积对应频域相乘", "metadata": {"source_file": "a.md"}}],
        "卷积定理",
        mode="concept",
    )
    assert "定义" in msgs[0]["content"]
    assert "公式" in msgs[0]["content"]
    assert "例题" in msgs[0]["content"]
    assert "卷积定理" in msgs[1]["content"]


def test_ask_rejects_unknown_mode():
    with pytest.raises(BadRequestException):
        ask("q", mode="chapter", vs=MagicMock(), llm=MagicMock(), course_id="c")


def test_ask_concept_uses_larger_top_k_and_mode():
    hits = [{"text": "定义…", "score": 0.9, "metadata": {"source_file": "a.md"}}]
    llm = MagicMock()
    llm.configured = True
    with patch("src.services.query.retrieve", return_value=hits) as mock_ret:
        with patch(
            "src.services.query.generate",
            return_value={
                "answer": "定义…\n公式…\n例题…",
                "citations": [
                    {"source_file": "a.md", "page": None, "snippet": "定义", "score": 0.9}
                ],
                "grounded": True,
            },
        ) as mock_gen:
            out = ask(
                "卷积定理",
                mode="concept",
                vs=MagicMock(),
                llm=llm,
                course_id="course-default",
            )
    mock_ret.assert_called_once()
    assert mock_ret.call_args.kwargs["top_k"] == CONCEPT_TOP_K
    assert mock_gen.call_args.kwargs["mode"] == "concept"
    assert out.grounded is True


def test_ask_stream_concept_passes_mode():
    hits = [{"text": "x", "score": 0.9, "metadata": {"source_file": "a.md"}}]
    llm = MagicMock()
    llm.configured = True

    def _fake_stream(**kwargs):
        assert kwargs["mode"] == "concept"
        yield {"type": "delta", "text": "定"}
        yield {
            "type": "done",
            "data": {
                "answer": "定义",
                "citations": [
                    {"source_file": "a.md", "page": None, "snippet": "x", "score": 0.9}
                ],
                "grounded": True,
            },
        }

    with patch("src.services.query.retrieve", return_value=hits) as mock_ret:
        with patch("src.services.query.stream_generate", side_effect=_fake_stream):
            events = list(
                ask_stream(
                    "卷积",
                    mode="concept",
                    vs=MagicMock(),
                    llm=llm,
                    course_id="course-default",
                )
            )
    assert mock_ret.call_args.kwargs["top_k"] == CONCEPT_TOP_K
    assert events[0]["type"] == "phase"
    assert events[-1]["type"] == "done"
