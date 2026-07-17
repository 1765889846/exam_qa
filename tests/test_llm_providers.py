"""LLM 注册表 API（注册 / 切换 / 删除）。"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import llm_providers as registry

client = TestClient(app)


@pytest.fixture()
def provider_store(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "llm_providers.json"
        monkeypatch.setattr(registry, "STORE_PATH", path)
        monkeypatch.setattr(registry, "write_env_updates", lambda updates: None)
        monkeypatch.setattr(registry, "ensure_seeded_from_env", lambda: None)
        yield path


def test_upsert_list_activate_delete(provider_store, monkeypatch):
    r = client.post(
        "/api/v1/llm-providers",
        json={
            "name": "deepseek",
            "format": "openai",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "deepseek"

    r = client.post(
        "/api/v1/llm-providers",
        json={
            "name": "local-ollama",
            "format": "local",
            "model": "qwen2.5",
            "base_url": "http://127.0.0.1:11434/v1",
        },
    )
    assert r.status_code == 200

    listed = client.get("/api/v1/llm-providers").json()["data"]
    names = {p["name"] for p in listed["items"]}
    assert names == {"deepseek", "local-ollama"}

    monkeypatch.setattr(
        registry,
        "set_active",
        lambda name: {
            "items": [
                {
                    "name": "local-ollama",
                    "format": "local",
                    "model": "qwen2.5",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "has_api_key": False,
                    "active": True,
                }
            ],
            "active": "local-ollama",
            "formats": sorted(registry.FORMATS),
        },
    )
    r = client.post("/api/v1/llm-providers/active", json={"name": "local-ollama"})
    assert r.status_code == 200
    assert r.json()["data"]["active"] == "local-ollama"


def test_config_llm_includes_providers(provider_store, monkeypatch):
    monkeypatch.setattr(
        registry,
        "list_public",
        lambda: {
            "items": [
                {
                    "name": "default",
                    "format": "openai",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                    "has_api_key": True,
                    "active": True,
                }
            ],
            "active": "default",
            "formats": ["local", "openai", "openai-compatible"],
        },
    )
    r = client.get("/api/v1/config")
    assert r.status_code == 200
    llm = r.json()["data"]["llm"]
    assert llm["active"] == "default"
    assert llm["providers"][0]["name"] == "default"
