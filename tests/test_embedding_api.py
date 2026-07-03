"""Embedding 延迟加载 API 测试。"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.dependencies import get_embedding_client
from src.main import app

client = TestClient(app)


@pytest.fixture
def mock_embedding():
    mock_emb = MagicMock()
    app.dependency_overrides[get_embedding_client] = lambda: mock_emb
    yield mock_emb
    app.dependency_overrides.clear()


class TestEmbeddingWarmupAPI:
    def test_warmup_when_already_ready(self, mock_embedding):
        mock_embedding.status.return_value = "ok"
        mock_embedding.provider = "local"
        mock_embedding.model = "all-MiniLM-L6-v2"

        r = client.post("/api/v1/embedding/warmup")

        assert r.status_code == 200
        body = r.json()
        assert body["data"]["status"] == "ok"
        mock_embedding.warmup.assert_not_called()

    def test_warmup_unavailable_returns_400(self, mock_embedding):
        mock_embedding.status.return_value = "unavailable"

        r = client.post("/api/v1/embedding/warmup")

        assert r.status_code == 400

    def test_health_reports_not_ready_without_load(self, mock_embedding):
        mock_embedding.status.return_value = "not_ready"

        r = client.get("/api/v1/health")

        assert r.status_code == 200
        assert r.json()["data"]["embedding"] == "not_ready"
        assert r.json()["data"]["status"] == "degraded"
