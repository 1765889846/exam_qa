"""Agent 循环：多步检索、改写上限、拒答、接口装配。"""

from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from src.dependencies import get_catalog_store, get_llm_client, get_vector_store
from src.main import app
from src.services.agent import run_agent

client = TestClient(app)


def _fake_llm(configured: bool = True, chat_return: str = "改写后的查询"):
    llm = MagicMock()
    llm.configured = configured
    llm.chat.return_value = chat_return
    return llm


def _hit(score: float) -> dict:
    return {
        "text": "片段内容",
        "score": score,
        "metadata": {"source_file": "a.md", "page": 1},
    }


class TestAgentLoop:
    def test_generate_when_sufficient(self):
        vs = MagicMock()
        llm = _fake_llm(configured=True)
        with patch("src.services.agent.tools.retrieve_tool", return_value=[_hit(0.8)]) as ret:
            with patch(
                "src.services.generation.generate",
                return_value={"answer": "答案", "citations": [], "grounded": True},
            ) as gen:
                result = run_agent(
                    "问题", "course-default", vs, llm,
                    max_steps=3, top_k=5, score_threshold=0.25,
                )
        assert result["grounded"] is True
        assert result["answer"] == "答案"
        assert result["agent_used"] is True
        assert any(s.startswith("retrieve:") for s in result["steps"])
        assert any(s.startswith("grade:") for s in result["steps"])
        assert "generate" in result["steps"]
        assert ret.call_count == 1
        gen.assert_called_once()

    def test_rewrite_then_generate(self):
        vs = MagicMock()
        llm = _fake_llm(configured=True, chat_return="改写查询")
        with patch(
            "src.services.agent.tools.retrieve_tool",
            side_effect=[[_hit(0.1)], [_hit(0.8)]],
        ) as ret:
            with patch(
                "src.services.generation.generate",
                return_value={"answer": "答案", "citations": [], "grounded": True},
            ):
                result = run_agent(
                    "问题", "course-default", vs, llm,
                    max_steps=3, top_k=5, score_threshold=0.25,
                )
        assert result["grounded"] is True
        assert ret.call_count == 2
        assert any(s.startswith("rewrite:") for s in result["steps"])
        llm.chat.assert_called()

    def test_refuse_after_max_steps(self):
        vs = MagicMock()
        llm = _fake_llm(configured=True, chat_return="改写查询")
        with patch(
            "src.services.agent.tools.retrieve_tool",
            return_value=[_hit(0.1)],
        ) as ret:
            result = run_agent(
                "问题", "course-default", vs, llm,
                max_steps=2, top_k=5, score_threshold=0.25,
            )
        assert result["grounded"] is False
        assert result["answer"] == "资料库中未找到相关内容"
        assert ret.call_count == 2
        assert "refuse" in result["steps"]

    def test_refuse_when_llm_unconfigured(self):
        vs = MagicMock()
        llm = _fake_llm(configured=False)
        with patch(
            "src.services.agent.tools.retrieve_tool",
            return_value=[_hit(0.1)],
        ) as ret:
            result = run_agent(
                "问题", "course-default", vs, llm,
                max_steps=3, top_k=5, score_threshold=0.25,
            )
        assert result["grounded"] is False
        assert ret.call_count == 1
        assert "refuse" in result["steps"]


class TestAgentApi:
    def test_missing_course_id_422(self):
        r = client.post("/api/v1/agent/run", json={"question": "问题"})
        assert r.status_code == 422

    def test_endpoint_ok(self):
        vs = MagicMock()
        llm = _fake_llm(configured=True)
        catalog = MagicMock()
        app.dependency_overrides[get_vector_store] = lambda: vs
        app.dependency_overrides[get_llm_client] = lambda: llm
        app.dependency_overrides[get_catalog_store] = lambda: catalog
        try:
            with patch("src.services.agent.tools.retrieve_tool", return_value=[_hit(0.8)]):
                with patch(
                    "src.services.generation.generate",
                    return_value={
                        "answer": "答案",
                        "citations": [
                            {"source_file": "a.md", "page": 1, "snippet": "片段", "score": 0.8}
                        ],
                        "grounded": True,
                    },
                ):
                    r = client.post(
                        "/api/v1/agent/run",
                        json={"question": "问题", "course_id": "course-default"},
                    )
        finally:
            app.dependency_overrides.pop(get_vector_store, None)
            app.dependency_overrides.pop(get_llm_client, None)
            app.dependency_overrides.pop(get_catalog_store, None)

        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 200
        assert body["data"]["agent_used"] is True
        assert body["data"]["grounded"] is True
        assert body["data"]["answer"] == "答案"
        catalog.require_course.assert_called_once_with("course-default")
