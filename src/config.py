"""全局配置 dataclass。优先级：环境变量 > .env 文件 > 代码默认值。"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.services.env_store import ENV_PATH, ensure_env_file

ensure_env_file()
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


def _env_flag(name: str) -> bool | None:
    """读布尔环境变量；未设置返回 None。"""
    raw = os.getenv(name)
    if raw is None:
        return None
    text = raw.strip().lower()
    if text == "":
        return None
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _proxy_enabled_default() -> bool:
    """PROXY_ENABLED 显式优先；未写时兼容旧行为：有 PROXY_URL 即启用。"""
    flag = _env_flag("PROXY_ENABLED")
    if flag is not None:
        return flag
    return bool(os.getenv("PROXY_URL", "").strip())


@dataclass
class ProxyConfig:
    """出站 HTTP 代理。PROXY_URL 同时用于 HTTP/HTTPS（LLM、Embedding、Hugging Face 下载）。"""

    url: str = field(default_factory=lambda: os.getenv("PROXY_URL", "").strip())
    no_proxy: str = field(
        default_factory=lambda: os.getenv("NO_PROXY", "127.0.0.1,localhost").strip()
    )
    enabled: bool = field(default_factory=_proxy_enabled_default)

    @property
    def active_url(self) -> str:
        return self.url if self.enabled and self.url else ""


@dataclass
class LLMConfig:
    """对话生成模型（OpenAI 兼容 API）。"""

    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "60")))


@dataclass
class EmbeddingConfig:
    """向量化模型。与 LLM 独立配置 api_key / base_url。

    provider:
      - local  → sentence-transformers 本地模型（默认）
      - openai → OpenAI 兼容 Embedding API
    """

    provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local"))
    model: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )
    api_key: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", ""))
    timeout: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_TIMEOUT", "60")))

    def resolve_api_key(self, llm: LLMConfig) -> str:
        """Embedding 专用 key 优先，未设则回退 LLM key。"""
        return self.api_key or llm.api_key

    def resolve_base_url(self, llm: LLMConfig) -> str:
        """Embedding 专用 base_url 优先，未设则回退 LLM base_url。"""
        return self.base_url or llm.base_url or "https://api.openai.com/v1"


@dataclass
class StorageConfig:
    chroma_path: str = field(default_factory=lambda: os.getenv("CHROMA_PATH", "./storage/chroma"))
    sqlite_path: str = field(default_factory=lambda: os.getenv("SQLITE_PATH", "./storage/meta.db"))
    log_path: str = field(default_factory=lambda: os.getenv("LOG_PATH", "./storage/app.log"))
    knowledge_dir: str = field(default_factory=lambda: os.getenv("KNOWLEDGE_DIR", "data/knowledge"))


@dataclass
class ChunkConfig:
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "800")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "50")))


@dataclass
class RetrievalConfig:
    top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "5")))
    score_threshold: float = field(
        default_factory=lambda: float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.25"))
    )
    # P2-A：BGE CrossEncoder 精排；默认关，避免 CI/首启强制下载
    rerank_enabled: bool = field(
        default_factory=lambda: os.getenv("RERANK_ENABLED", "false").lower() == "true"
    )
    rerank_model: str = field(
        default_factory=lambda: os.getenv(
            "RERANK_MODEL", "BAAI/bge-reranker-v2-m3"
        ).strip()
        or "BAAI/bge-reranker-v2-m3"
    )
    rerank_candidates: int = field(
        default_factory=lambda: int(os.getenv("RERANK_CANDIDATES", "20"))
    )
    rerank_top_n: int = field(
        default_factory=lambda: int(os.getenv("RERANK_TOP_N", "0"))
    )  # 0 → 回退 top_k


@dataclass
class ParsingConfig:
    """文档解析：PDF OCR 等。"""

    pdf_use_ocr: bool = field(
        default_factory=lambda: os.getenv("PDF_USE_OCR", "true").lower() == "true"
    )
    pdf_force_ocr: bool = field(
        default_factory=lambda: os.getenv("PDF_FORCE_OCR", "false").lower() == "true"
    )
    pdf_ocr_language: str = field(
        default_factory=lambda: os.getenv("PDF_OCR_LANGUAGE", "eng+chi_sim")
    )


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    # 注册表活跃名，对应 data/llm_providers.json
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "").strip()
    )
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    )
    api_v1_prefix: str = field(default_factory=lambda: os.getenv("API_V1_PREFIX", "/api/v1"))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "50")))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    # ponytail: 8787 避开 Windows Hyper-V 常保留的 8000 等端口
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8787")))

    def validate(self) -> None:
        """启动时校验配置，非法值尽早失败。"""
        provider = self.embedding.provider.strip().lower()
        if provider not in ("local", "openai"):
            raise ValueError(
                f"EMBEDDING_PROVIDER 无效: {self.embedding.provider!r}，可选 local / openai"
            )
        level = self.log_level.strip().upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError(
                f"LOG_LEVEL 无效: {self.log_level!r}，可选 DEBUG / INFO / WARNING / ERROR"
            )
        self.log_level = level
        if self.chunk.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if self.chunk.chunk_overlap >= self.chunk.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        if self.max_upload_mb <= 0:
            raise ValueError("max_upload_mb 必须大于 0")
        if self.retrieval.top_k <= 0:
            raise ValueError("top_k 必须大于 0")
        if not (0 <= self.retrieval.score_threshold <= 1):
            raise ValueError("score_threshold 须在 0～1")
        if self.retrieval.rerank_candidates <= 0:
            raise ValueError("rerank_candidates 必须大于 0")
        if self.retrieval.rerank_top_n < 0:
            raise ValueError("rerank_top_n 不能为负")


config = AppConfig()

from src.services.http_client import apply_proxy_env  # noqa: E402

apply_proxy_env(config.proxy)


def reload_config() -> AppConfig:
    """重新加载 .env 并刷新全局 config（保持 import 引用有效）。"""
    from src.services.env_store import ENV_PATH as env_path
    from src.utils.logging import apply_log_level

    load_dotenv(env_path, override=True)
    fresh = AppConfig()
    fresh.validate()
    for name in config.__dataclass_fields__:
        setattr(config, name, getattr(fresh, name))
    apply_proxy_env(config.proxy)
    apply_log_level(config.log_level)
    return config
