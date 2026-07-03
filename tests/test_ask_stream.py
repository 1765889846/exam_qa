"""流式问答单元测试。"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.dependencies import get_llm_client
from src.main import app

client = TestClient(app)


def _mock_hits():
    return [
        {
            "text": "傅里叶变换定义…",
            "score": 0.8,
            "metadata": {"source_file": "ch1.md", "page": 1},
        }
    ]


class TestAskStreamAPI:
    def test_stream_refusal_emits_done(self):
        with patch("src.services.query.retrieve", return_value=[]):
            with client.stream(
                "POST",
                "/api/v1/ask",
                json={"question": "测试", "mode": "qa", "stream": True},
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                body = "".join(resp.iter_text())
                assert '"type": "done"' in body
                assert "未找到相关内容" in body

    def test_stream_generating_emits_deltas(self):
        def fake_stream(*_args, **_kwargs):
            yield {"type": "delta", "text": "你好"}
            yield {
                "type": "done",
                "data": {
                    "answer": "你好",
                    "citations": [
                        {
                            "source_file": "ch1.md",
                            "page": 1,
                            "snippet": "片段",
                            "score": 0.8,
                        }
                    ],
                    "grounded": True,
                },
            }

        mock_llm = MagicMock()
        mock_llm.configured = True
        app.dependency_overrides[get_llm_client] = lambda: mock_llm

        try:
            with patch("src.services.query.retrieve", return_value=_mock_hits()):
                with patch("src.services.query.stream_generate", side_effect=fake_stream):
                    with client.stream(
                        "POST",
                        "/api/v1/ask",
                        json={"question": "测试", "mode": "qa", "stream": True},
                    ) as resp:
                        assert resp.status_code == 200
                        events = []
                        for line in resp.iter_lines():
                            if line.startswith("data: "):
                                events.append(json.loads(line[6:]))
                        types = [e["type"] for e in events]
                        assert "phase" in types
                        assert "delta" in types
                        assert "done" in types
                        done = next(e for e in events if e["type"] == "done")
                        assert done["data"]["answer"] == "你好"
        finally:
            app.dependency_overrides.pop(get_llm_client, None)

    def test_non_stream_still_json(self):
        with patch("src.services.query.retrieve", return_value=[]):
            r = client.post(
                "/api/v1/ask",
                json={"question": "测试", "mode": "qa", "stream": False},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["code"] == 200
            assert body["data"]["grounded"] is False
