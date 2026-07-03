"""HTTP 客户端与代理环境变量。"""

from __future__ import annotations

import os

import httpx

from src.config import ProxyConfig, config

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)


def apply_proxy_env(proxy: ProxyConfig | None = None) -> None:
    """将代理写入进程环境，供 httpx / Hugging Face 等库使用。"""
    p = proxy if proxy is not None else config.proxy
    if p.url:
        for key in _PROXY_ENV_KEYS:
            os.environ[key] = p.url
    else:
        for key in _PROXY_ENV_KEYS:
            os.environ.pop(key, None)
    if p.no_proxy:
        os.environ["NO_PROXY"] = p.no_proxy
        os.environ["no_proxy"] = p.no_proxy


def create_openai_http_client(timeout: float) -> httpx.Client:
    """OpenAI SDK 用 httpx 客户端（显式代理 + trust_env 读 NO_PROXY）。"""
    proxy = config.proxy.url or None
    return httpx.Client(proxy=proxy, timeout=timeout, trust_env=True)
