"""http_client：代理环境与 HF 错误提示。"""

from __future__ import annotations

import os

from src.config import ProxyConfig
from src.services import http_client as hc


def test_is_proxy_or_conn_error():
    assert hc.is_proxy_or_conn_error(OSError(10061, "积极拒绝"))
    assert hc.is_proxy_or_conn_error(RuntimeError("Cannot send a request, as the client has been closed."))
    assert not hc.is_proxy_or_conn_error(ValueError("bad model"))


def test_format_hf_download_error_mentions_proxy(monkeypatch):
    monkeypatch.setattr(
        hc.config,
        "proxy",
        ProxyConfig(url="http://127.0.0.1:7890", enabled=True),
    )
    msg = hc.format_hf_download_error(OSError("[WinError 10061] 由于目标计算机积极拒绝，无法连接。"))
    assert "7890" in msg
    assert "代理" in msg


def test_without_process_proxy_restores(monkeypatch):
    monkeypatch.setattr(
        hc.config,
        "proxy",
        ProxyConfig(url="http://127.0.0.1:7890", enabled=True),
    )
    hc.apply_proxy_env()
    assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:7890"
    with hc.without_process_proxy():
        assert "HTTP_PROXY" not in os.environ
    assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:7890"
