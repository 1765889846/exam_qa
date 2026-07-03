"""配置 PATCH API 测试。"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@pytest.fixture
def env_backup(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        env_file = base / ".env"
        example = base / ".env.example"
        example.write_text(
            "LLM_API_KEY=\nLLM_MODEL=gpt-4o-mini\nRETRIEVAL_TOP_K=20\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("src.services.env_store.ENV_PATH", env_file)
        monkeypatch.setattr("src.services.env_store.ENV_EXAMPLE_PATH", example)
        monkeypatch.setattr("src.services.env_store.PROJECT_ROOT", base)
        from src.config import reload_config
        from src.dependencies import reload_services

        reload_config()
        reload_services()
        yield env_file
        reload_config()
        reload_services()


def test_config_get_includes_meta():
    r = client.get("/api/v1/config")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "meta" in data
    assert "env_writable" in data["meta"]


def test_config_patch_updates_llm(env_backup):
    r = client.patch(
        "/api/v1/config",
        json={"llm": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["llm"]["model"] == "deepseek-chat"
    assert "settings_effects" in data
    assert env_backup.read_text(encoding="utf-8").count("LLM_MODEL=deepseek-chat") == 1


def test_config_patch_rejects_empty_body():
    r = client.patch("/api/v1/config", json={})
    assert r.status_code == 400
