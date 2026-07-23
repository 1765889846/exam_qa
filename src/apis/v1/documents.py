"""documents API — 上传 / 列表 / 扫描 / 删除。"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from starlette import status

from src.config import config
from src.dependencies import (
    get_catalog_store,
    get_current_user,
    get_doc_store,
    get_vector_store,
)
from src.exceptions import (
    AppException,
    BadRequestException,
    NotFoundException,
    UnsupportedFormatException,
)
from src.services.ingestion import SUPPORTED_EXTENSIONS, ingest_file, scan_knowledge_dir
from src.services.storage.catalog_store import CatalogStore
from src.services.storage.doc_store import SQLiteDocStore
from src.services.storage.vector_store import ChromaVectorStore

router = APIRouter(prefix="/documents", tags=["documents"])

_CHUNK_SIZE = 1024 * 1024


def _knowledge_dir() -> Path:
    return Path(config.storage.knowledge_dir)


def _write_upload_limited(src: UploadFile, dest: Path, max_bytes: int) -> None:
    total = 0
    with open(dest, "wb") as out:
        while True:
            chunk = src.file.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                limit_mb = max_bytes // (1024 * 1024)
                raise BadRequestException(f"文件超过大小限制（{limit_mb}MB）")
            out.write(chunk)


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    course_id: str = Form(...),
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    course = catalog.require_course(course_id)

    if not file.filename:
        raise BadRequestException("文件名为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatException(
            f"不支持的文件格式: {ext}，仅接受 PDF/TXT/MD/DOC/DOCX/PPTX"
        )

    upload_dir = _knowledge_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{Path(file.filename).stem}_{os.urandom(4).hex()}{ext}"
    save_path = upload_dir / safe_name
    max_bytes = config.max_upload_mb * 1024 * 1024

    _write_upload_limited(file, save_path, max_bytes)

    try:
        doc_id = ingest_file(
            path=str(save_path.resolve()),
            vs=vs,
            ds=ds,
            course_id=course_id,
            course=course["name"],
            college_id=course["college_id"],
            display_name=file.filename,
        )
    except AppException:
        save_path.unlink(missing_ok=True)
        raise

    return {
        "code": status.HTTP_200_OK,
        "data": {
            "doc_id": doc_id,
            "filename": file.filename,
            "status": "done",
            "stored_path": str(save_path),
            "course_id": course_id,
        },
    }


@router.get("")
async def list_documents(
    course_id: str,
    ds: SQLiteDocStore = Depends(get_doc_store),
    vs: ChromaVectorStore = Depends(get_vector_store),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    catalog.require_course(course_id)
    docs = ds.list(course_id=course_id)
    emb = config.embedding
    dim = vs.stored_embedding_dim()
    return {
        "code": status.HTTP_200_OK,
        "data": {
            "items": docs,
            "total": len(docs),
            "embedding": {
                "provider": emb.provider,
                "model": emb.model,
                "dim": int(dim) if dim is not None else None,
            },
        },
    }


@router.post("/scan")
async def scan_data_dir(
    course_id: str = Form(...),
    force: bool = Form(False),
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    course = catalog.require_course(course_id)
    scan_knowledge_dir(
        vs,
        ds,
        course_id=course_id,
        course=course["name"],
        college_id=course["college_id"],
        recover_stale=False,
        force=force,
    )
    return {
        "code": status.HTTP_200_OK,
        "data": {
            "message": "强制重建完成" if force else "扫描完成",
            "course_id": course_id,
            "force": force,
        },
    }


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    course_id: str,
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    catalog.require_course(course_id)
    doc = ds.get(doc_id)
    if doc is None:
        raise NotFoundException(f"文档不存在: {doc_id}")
    if doc.get("course_id") != course_id:
        raise NotFoundException(f"文档不存在: {doc_id}")

    vs.delete_by_doc_id(str(doc_id))

    file_path = Path(doc["file_path"])
    if file_path.is_file():
        file_path.unlink(missing_ok=True)

    ds.delete(doc_id)

    return {
        "code": status.HTTP_200_OK,
        "data": {
            "message": f"文档 {doc['filename']} 已删除",
            "deleted_doc_id": str(doc_id),
        },
    }
