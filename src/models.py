"""Pydantic 请求/响应模型。"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_file: str
    page: Optional[int] = None
    snippet: str
    score: float
    source_version: str = ""
    effective_from: str = "0001-01-01"
    effective_to: str = "9999-12-31"
    authority_level: int = 30
    authority_label: str = "教学材料"
    applicability_scope: str = "all"
    selection_reason: str = ""


class IntentData(BaseModel):
    task: str = "qa"
    mode: Literal["qa", "concept", "chapter"] = "qa"
    scenario: str | None = None
    as_of: str | None = None
    confidence: float = 0.0
    layer: Literal["rule", "context", "llm_fallback", "default"] = "default"
    rationale: str = ""


class AnswerData(BaseModel):
    answer: str
    citations: list[Citation] = []
    grounded: bool = True
    intent: IntentData | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="问题内容不能为空")
    course_id: str = Field(..., min_length=1, description="课程 ID，检索隔离必填")
    mode: Literal["auto", "qa", "concept", "chapter"] = "auto"
    conversation_id: str | None = Field(default=None, description="conversation ID for multi-turn context")
    scenario: str | None = Field(default=None, max_length=80, description="固定适用场景键；未传则不过滤")
    as_of: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="证据生效日 YYYY-MM-DD")
    stream: bool = False


class AgentRunRequest(BaseModel):
    question: str = Field(..., min_length=1, description="问题内容不能为空")
    course_id: str = Field(..., min_length=1, description="课程 ID，检索隔离必填")
    mode: Literal["qa", "concept"] = "qa"
    max_steps: int = Field(default=3, ge=1, le=10, description="最大检索/改写轮数")
    top_k: int | None = Field(default=None, ge=1, description="单轮检索候选数，缺省用全局配置")
    score_threshold: float | None = Field(default=None, ge=0, le=1, description="判定检索足够的阈值，缺省用全局配置")


class AgentRunData(BaseModel):
    answer: str
    citations: list[Citation] = []
    grounded: bool = True
    steps: list[str] = []
    agent_used: bool = True


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
    rerank_enabled: bool | None = None
    rerank_model: str | None = None
    rerank_candidates: int | None = Field(default=None, ge=1)
    rerank_top_n: int | None = Field(default=None, ge=0)


class ChunkPatch(BaseModel):
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)


class ParsingPatch(BaseModel):
    pdf_use_ocr: bool | None = None
    pdf_force_ocr: bool | None = None
    pdf_ocr_language: str | None = None
    pdf_parser: Literal["auto", "pymupdf", "mineru"] | None = None
    mineru_cmd: str | None = None
    mineru_timeout: int | None = Field(default=None, ge=0)
    visual_model: str | None = None
    visual_base_url: str | None = None
    visual_api_key: str | None = None
    visual_timeout: int | None = Field(default=None, ge=0)


class EvidenceMetadataPatch(BaseModel):
    source_version: str | None = Field(default=None, max_length=80)
    effective_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    effective_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    authority_level: int | None = Field(default=None, ge=0, le=100)
    authority_label: str | None = Field(default=None, max_length=80)
    applicability_scope: str | None = Field(default=None, max_length=80)


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
