"""POST /api/v1/documents — 上传资料并入库。"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from starlette import status

from src.config import config
from src.dependencies import get_current_user, get_doc_store, get_vector_store
from src.exceptions import AppException, BadRequestException, NotFoundException, UnsupportedFormatException
from src.services.ingestion import SUPPORTED_EXTENSIONS, ingest_file, scan_knowledge_dir
from src.services.storage.doc_store import SQLiteDocStore
from src.services.storage.vector_store import ChromaVectorStore

router = APIRouter(prefix="/documents", tags=["documents"])

_CHUNK_SIZE = 1024 * 1024


def _knowledge_dir() -> Path:
    return Path(config.storage.knowledge_dir)


def _write_upload_limited(src: UploadFile, dest: Path, max_bytes: int) -> None:
    """流式写入并限制大小。"""
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
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    _user=Depends(get_current_user),
):
    """接收上传文件，保存到 data/knowledge/ 后调用入库管道。"""
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
        },
    }


@router.get("")
async def list_documents(
    ds: SQLiteDocStore = Depends(get_doc_store),
    _user=Depends(get_current_user),
):
    """列出全部文档及入库状态。"""
    docs = ds.list()
    return {
        "code": status.HTTP_200_OK,
        "data": {
            "items": docs,
            "total": len(docs),
        },
    }


@router.post("/scan")
async def scan_data_dir(
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    _user=Depends(get_current_user),
):
    """扫描 data/knowledge/ 目录，导入未入库或已变更的 PDF/TXT/MD/DOC/DOCX/PPTX 文件。"""
    scan_knowledge_dir(vs, ds, recover_stale=False)
    return {
        "code": status.HTTP_200_OK,
        "data": {"message": "扫描完成"},
    }


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    vs: ChromaVectorStore = Depends(get_vector_store),
    ds: SQLiteDocStore = Depends(get_doc_store),
    _user=Depends(get_current_user),
):
    """删除文档及其全部向量数据。"""
    doc = ds.get(doc_id)
    if doc is None:
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
