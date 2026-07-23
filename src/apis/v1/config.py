"""GET/PATCH /api/v1/config — 设置页配置读写。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette import status

from src.config import config, reload_config
from src.dependencies import get_current_user, reload_services
from src.exceptions import BadRequestException
from src.models import ConfigUpdateRequest
from src.services.env_store import (
    ENV_PATH,
    MASKED_SECRET,
    PROJECT_ROOT,
    env_file_writable,
    write_env_updates,
)
from src.services.settings_apply import build_settings_effects

router = APIRouter(prefix="/config", tags=["config"])


def _config_path_label() -> str:
    try:
        return str(ENV_PATH.relative_to(PROJECT_ROOT))
    except ValueError:
        return ".env"


def _build_config_data(request: Request) -> dict:
    from src.services import llm_providers as llm_reg

    emb = config.embedding
    llm = config.llm
    providers = llm_reg.list_public()
    return {
        "llm": {
            "active": providers.get("active") or config.llm_provider,
            "providers": providers.get("items") or [],
            "formats": providers.get("formats") or [],
            "model": llm.model,
            "base_url": llm.base_url,
            "timeout": llm.timeout,
            "configured": bool(llm.api_key),
        },
        "embedding": {
            "provider": emb.provider,
            "model": emb.model,
            "base_url": emb.resolve_base_url(llm),
            "timeout": emb.timeout,
            "configured": bool(emb.resolve_api_key(llm)),
            "uses_separate_credentials": bool(emb.api_key or emb.base_url),
        },
        "retrieval": {
            "top_k": config.retrieval.top_k,
            "score_threshold": config.retrieval.score_threshold,
            "rerank_enabled": config.retrieval.rerank_enabled,
            "rerank_model": config.retrieval.rerank_model,
            "rerank_candidates": config.retrieval.rerank_candidates,
            "rerank_top_n": config.retrieval.rerank_top_n,
        },
        "chunk": {
            "chunk_size": config.chunk.chunk_size,
            "chunk_overlap": config.chunk.chunk_overlap,
        },
        "storage": {
            "knowledge_dir": config.storage.knowledge_dir,
        },
        "parsing": {
            "pdf_use_ocr": config.parsing.pdf_use_ocr,
            "pdf_force_ocr": config.parsing.pdf_force_ocr,
            "pdf_ocr_language": config.parsing.pdf_ocr_language,
        },
        "server": {
            "host": config.host,
            "port": config.port,
        },
        "app": {
            "max_upload_mb": config.max_upload_mb,
            "debug": config.debug,
            "log_level": config.log_level,
        },
        "proxy": {
            "url": config.proxy.url,
            "no_proxy": config.proxy.no_proxy,
            "enabled": config.proxy.enabled,
        },
        "meta": {
            "config_path": _config_path_label(),
            "env_writable": env_file_writable(),
        },
        "health": {
            "llm": "ok" if config.llm.api_key else "unavailable",
            "embedding": getattr(request.app.state, "embedding_health", "not_ready"),
        },
    }


def _patch_to_env(body: ConfigUpdateRequest) -> tuple[dict[str, str], list[str]]:
    updates: dict[str, str] = {}
    patched: list[str] = []

    if body.llm is not None:
        patched.append("llm")
        p = body.llm.model_dump(exclude_none=True)
        if "api_key" in p and p["api_key"] != MASKED_SECRET:
            updates["LLM_API_KEY"] = p["api_key"].strip()
        if "base_url" in p:
            updates["LLM_BASE_URL"] = p["base_url"].strip()
        if "model" in p:
            updates["LLM_MODEL"] = p["model"].strip()
        if "timeout" in p:
            updates["LLM_TIMEOUT"] = str(p["timeout"])
        from src.services import llm_providers as llm_reg

        llm_reg.sync_active_fields_from_patch(
            model=p.get("model"),
            base_url=p.get("base_url"),
            api_key=p.get("api_key") if p.get("api_key") != MASKED_SECRET else None,
        )

    if body.embedding is not None:
        patched.append("embedding")
        p = body.embedding.model_dump(exclude_none=True)
        if "provider" in p:
            updates["EMBEDDING_PROVIDER"] = p["provider"]
        if "api_key" in p and p["api_key"] != MASKED_SECRET:
            updates["EMBEDDING_API_KEY"] = p["api_key"].strip()
        if "base_url" in p:
            updates["EMBEDDING_BASE_URL"] = p["base_url"].strip()
        if "model" in p:
            updates["EMBEDDING_MODEL"] = p["model"].strip()
        if "timeout" in p:
            updates["EMBEDDING_TIMEOUT"] = str(p["timeout"])

    if body.retrieval is not None:
        patched.append("retrieval")
        p = body.retrieval.model_dump(exclude_none=True)
        if "top_k" in p:
            updates["RETRIEVAL_TOP_K"] = str(p["top_k"])
        if "score_threshold" in p:
            updates["RETRIEVAL_SCORE_THRESHOLD"] = str(p["score_threshold"])
        if "rerank_enabled" in p:
            updates["RERANK_ENABLED"] = "true" if p["rerank_enabled"] else "false"
        if "rerank_model" in p:
            name = str(p["rerank_model"]).strip()
            if not name:
                raise BadRequestException("rerank_model 不能为空")
            updates["RERANK_MODEL"] = name
        if "rerank_candidates" in p:
            updates["RERANK_CANDIDATES"] = str(p["rerank_candidates"])
        if "rerank_top_n" in p:
            updates["RERANK_TOP_N"] = str(p["rerank_top_n"])

    if body.chunk is not None:
        patched.append("chunk")
        p = body.chunk.model_dump(exclude_none=True)
        size = p.get("chunk_size", config.chunk.chunk_size)
        overlap = p.get("chunk_overlap", config.chunk.chunk_overlap)
        if "chunk_size" in p:
            updates["CHUNK_SIZE"] = str(p["chunk_size"])
            size = p["chunk_size"]
        if "chunk_overlap" in p:
            overlap = p["chunk_overlap"]
            updates["CHUNK_OVERLAP"] = str(p["chunk_overlap"])
        if overlap >= size:
            raise BadRequestException("chunk_overlap 必须小于 chunk_size")

    if body.parsing is not None:
        patched.append("parsing")
        p = body.parsing.model_dump(exclude_none=True)
        if "pdf_use_ocr" in p:
            updates["PDF_USE_OCR"] = "true" if p["pdf_use_ocr"] else "false"
        if "pdf_force_ocr" in p:
            updates["PDF_FORCE_OCR"] = "true" if p["pdf_force_ocr"] else "false"
        if "pdf_ocr_language" in p:
            updates["PDF_OCR_LANGUAGE"] = p["pdf_ocr_language"].strip()

    if body.app is not None:
        patched.append("app")
        p = body.app.model_dump(exclude_none=True)
        if "max_upload_mb" in p:
            updates["MAX_UPLOAD_MB"] = str(p["max_upload_mb"])
        if "log_level" in p:
            updates["LOG_LEVEL"] = str(p["log_level"]).strip().upper()

    if body.server is not None:
        patched.append("server")
        p = body.server.model_dump(exclude_none=True)
        if "host" in p:
            host = p["host"].strip()
            if not host:
                raise BadRequestException("HOST 不能为空")
            updates["HOST"] = host
        if "port" in p:
            updates["PORT"] = str(p["port"])

    if body.proxy is not None:
        patched.append("proxy")
        p = body.proxy.model_dump(exclude_none=True)
        if "url" in p:
            updates["PROXY_URL"] = p["url"].strip()
        if "no_proxy" in p:
            updates["NO_PROXY"] = p["no_proxy"].strip()
        if "enabled" in p:
            updates["PROXY_ENABLED"] = "true" if p["enabled"] else "false"

    return updates, patched


@router.get("")
async def read_config(request: Request, _user=Depends(get_current_user)):
    return {"code": status.HTTP_200_OK, "data": _build_config_data(request)}


@router.patch("")
async def patch_config(
    request: Request,
    body: ConfigUpdateRequest,
    _user=Depends(get_current_user),
):
    sections = [
        name
        for name in ("llm", "embedding", "retrieval", "chunk", "parsing", "app", "server", "proxy")
        if getattr(body, name) is not None
    ]
    if not sections:
        raise BadRequestException("请至少修改一项配置")

    updates, patched = _patch_to_env(body)
    if not updates:
        raise BadRequestException("没有可写入的配置项")

    write_env_updates(updates)
    reload_config()
    reload_services()

    request.app.state.llm_health = "ok" if config.llm.api_key else "unavailable"
    from src.services.embedding import get_embedding_client

    request.app.state.embedding_health = get_embedding_client().status()

    data = _build_config_data(request)
    data["settings_effects"] = build_settings_effects(patched)
    return {"code": status.HTTP_200_OK, "data": data}
