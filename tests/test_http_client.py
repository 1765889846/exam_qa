"""HTTP 代理工具测试。"""

import os

from src.config import ProxyConfig
from src.services.http_client import apply_proxy_env


def test_apply_proxy_env_sets_variables(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(key, raising=False)
    apply_proxy_env(ProxyConfig(url="http://127.0.0.1:7890", no_proxy="localhost"))
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:7890"
    assert os.environ["NO_PROXY"] == "localhost"


def test_apply_proxy_env_clears_when_empty(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://old:1")
    apply_proxy_env(ProxyConfig(url="", no_proxy="127.0.0.1"))
    assert "HTTP_PROXY" not in os.environ
