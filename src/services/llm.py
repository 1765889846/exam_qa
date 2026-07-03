"""LLM 对话客户端（OpenAI 兼容 API）。向量化见 services/embedding.py。"""

import logging
from typing import Protocol, runtime_checkable

from src.exceptions import LLMAPIException, LLMTimeoutException

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMClient(Protocol):
    """对话补全抽象接口。"""

    def chat(self, messages: list[dict], **kwargs) -> str:
        ...

    def health_check(self) -> bool:
        ...

    @property
    def configured(self) -> bool:
        ...


class OpenAIClient:
    """OpenAI 兼容对话 API。支持 DeepSeek、Qwen 等。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60,
    ):
        from openai import OpenAI

        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = None
        if api_key:
            from src.services.http_client import create_openai_http_client

            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                http_client=create_openai_http_client(timeout),
            )

    @property
    def configured(self) -> bool:
        return self._client is not None

    def chat(self, messages: list[dict], **kwargs) -> str:
        if self._client is None:
            raise LLMAPIException("AI 服务未配置：请设置 LLM_API_KEY")
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", self._temperature),
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            self._raise_mapped(e)

    def chat_stream(self, messages: list[dict], **kwargs):
        """流式对话，逐块 yield 文本 delta。"""
        if self._client is None:
            raise LLMAPIException("AI 服务未配置：请设置 LLM_API_KEY")
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", self._temperature),
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            self._raise_mapped(e)

    def _raise_mapped(self, exc: Exception) -> None:
        name = type(exc).__name__
        if "Timeout" in name:
            raise LLMTimeoutException(detail=str(exc)) from exc
        if name in ("APIConnectionError", "APIStatusError", "AuthenticationError", "RateLimitError"):
            raise LLMAPIException(detail=str(exc)) from exc
        if isinstance(exc, LLMAPIException):
            raise
        logger.error("LLM 调用失败: %s", exc)
        raise LLMAPIException(detail=str(exc)) from exc

    def health_check(self) -> bool:
        if self._client is None:
            logger.warning("LLM API key 未配置，跳过健康检查")
            return False
        try:
            self._client.models.list()
            logger.info("LLM API 连通性检查通过，模型: %s", self._model)
            return True
        except Exception as e:
            logger.error("LLM API 连接失败: %s", e)
            return False
