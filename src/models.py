"""Pydantic 请求/响应模型。"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_file: str
    page: Optional[int] = None
    snippet: str
    score: float


class AnswerData(BaseModel):
    answer: str
    citations: list[Citation] = []
    grounded: bool = True


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="问题内容不能为空")
    course_id: str = Field(..., min_length=1, description="课程 ID，检索隔离必填")
    mode: Literal["qa", "concept"] = "qa"
    stream: bool = False


class LLMPatch(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: int | None = Field(default=None, ge=1)


class EmbeddingPatch(BaseModel):
    provider: Literal["local", "openai"] | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: int | None = Field(default=None, ge=1)


class RetrievalPatch(BaseModel):
    top_k: int | None = Field(default=None, ge=1)
    score_threshold: float | None = Field(default=None, ge=0, le=1)


class ChunkPatch(BaseModel):
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)


class ParsingPatch(BaseModel):
    pdf_use_ocr: bool | None = None
    pdf_force_ocr: bool | None = None
    pdf_ocr_language: str | None = None


class AppPatch(BaseModel):
    max_upload_mb: int | None = Field(default=None, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None


class ServerPatch(BaseModel):
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class ProxyPatch(BaseModel):
    url: str | None = None
    no_proxy: str | None = None
    enabled: bool | None = None


class ConfigUpdateRequest(BaseModel):
    llm: LLMPatch | None = None
    embedding: EmbeddingPatch | None = None
    retrieval: RetrievalPatch | None = None
    chunk: ChunkPatch | None = None
    parsing: ParsingPatch | None = None
    app: AppPatch | None = None
    server: ServerPatch | None = None
    proxy: ProxyPatch | None = None
