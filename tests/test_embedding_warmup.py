"""Embedding warmup / status API。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.dependencies import get_embedding_client
from src.main import app
from src.services import embedding as emb_mod

client = TestClient(app)


def test_get_warmup_progress_defaults():
    p = emb_mod.get_warmup_progress()
    assert "phase" in p
    assert "percent" in p


def test_start_warmup_background_already_ok():
    fake = MagicMock()
    fake.provider = "local"
    fake.model = "all-MiniLM-L6-v2"
    fake.status.return_value = "ok"
    emb_mod._warmup_thread = None
    out = emb_mod.start_warmup_background(fake)
    assert out["phase"] == "ok"
    assert out["percent"] == 100


def test_build_status_heals_when_model_ready():
    fake = MagicMock()
    fake.provider = "local"
    fake.model = "m"
    fake.status.return_value = "ok"
    emb_mod._set_progress(
        phase="running",
        percent=None,
        message="装载到内存…",
        error=None,
        provider="local",
        model="m",
    )
    data = emb_mod.build_embedding_status(fake)
    assert data["status"] == "ok"
    assert data["warmup"]["phase"] == "ok"
    assert data["warmup"]["percent"] == 100


def test_build_status_drops_stale_ok_after_reset():
    fake = MagicMock()
    fake.provider = "local"
    fake.model = "m"
    fake.status.return_value = "not_ready"
    emb_mod._set_progress(
        phase="ok",
        percent=100,
        message="向量化已就绪",
        error=None,
        provider="local",
        model="old",
    )
    data = emb_mod.build_embedding_status(fake)
    assert data["status"] == "not_ready"
    assert data["warmup"]["phase"] == "idle"


def test_embedding_status_and_warmup_api():
    fake = MagicMock()
    fake.provider = "local"
    fake.model = "all-MiniLM-L6-v2"
    fake.status.return_value = "not_ready"

    started = {}

    def fake_start(c):
        started["ok"] = True
        emb_mod._set_progress(
            phase="running",
            percent=12,
            message="downloading",
            error=None,
            provider="local",
            model="all-MiniLM-L6-v2",
        )
        return emb_mod.get_warmup_progress()

    app.dependency_overrides[get_embedding_client] = lambda: fake
    try:
        with patch(
            "src.apis.v1.embedding.start_warmup_background", side_effect=fake_start
        ):
            r = client.post("/api/v1/embedding/warmup")
            assert r.status_code == 200
            assert r.json()["data"]["warmup"]["phase"] == "running"
            assert started.get("ok")

            r2 = client.get("/api/v1/embedding/status")
            assert r2.status_code == 200
            assert r2.json()["data"]["warmup"]["percent"] == 12
            assert r2.json()["data"]["status"] == "loading"
    finally:
        app.dependency_overrides.pop(get_embedding_client, None)


def test_clear_warmup_progress_bumps_generation():
    g0 = emb_mod._warmup_gen
    emb_mod.clear_warmup_progress()
    assert emb_mod._warmup_gen == g0 + 1
    assert emb_mod.get_warmup_progress()["phase"] == "idle"


def test_patch_hub_tqdm_targets_module_not_class():
    """回归：import huggingface_hub.utils.tqdm 会拿到类，不能 .tqdm 取值。"""
    import huggingface_hub.utils as hub_utils

    class FakeBar:
        def __init__(self, *a, **k):
            self.total = 10
            self.n = 0
            self.desc = "x"

        def update(self, n=1):
            self.n += n

    Progress = emb_mod._make_progress_tqdm(emb_mod._warmup_gen, base=FakeBar)
    mod, utils, old_mod, old_utils = emb_mod._patch_hub_tqdm(Progress)
    try:
        assert utils.tqdm is Progress
        assert mod.tqdm is Progress
        bar = hub_utils.tqdm(total=10)
        bar.update(5)
        assert bar.n == 5
    finally:
        mod.tqdm = old_mod
        utils.tqdm = old_utils
