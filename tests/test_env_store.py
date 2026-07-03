"""env 引导单元测试。"""

import tempfile
from pathlib import Path

from src.services import env_store


def test_ensure_env_file_creates_from_example(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        example = base / ".env.example"
        target = base / ".env"
        example.write_text("PORT=8787\n", encoding="utf-8")
        monkeypatch.setattr(env_store, "ENV_PATH", target)
        monkeypatch.setattr(env_store, "ENV_EXAMPLE_PATH", example)
        monkeypatch.setattr(env_store, "_env_created", False)

        assert env_store.ensure_env_file() is True
        assert target.read_text(encoding="utf-8") == "PORT=8787\n"
        assert env_store.ensure_env_file() is False
