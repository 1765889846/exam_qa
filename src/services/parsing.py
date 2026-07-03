"""文档解析：PDF / Office / 纯文本 → 带页码的结构化文本。

PDF 优先 pymupdf4llm（Markdown + 表格 + 标题层级 + 自动/强制 OCR），失败回退 PyMuPDF。
.doc（旧 Word）优先 LibreOffice 转 docx，再 python-docx 解析。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.config import config
from src.exceptions import BadRequestException, UnsupportedFormatException

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".doc", ".docx", ".pptx"}


@dataclass
class ParsedPage:
    page: int | None  # PDF/PPT 为 1-based 页码，txt/md/docx 为 None
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


def _page_num(meta: dict) -> int | None:
    raw = meta.get("page_number") or meta.get("page")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _pages_from_pymupdf4llm(raw) -> ParsedDocument | None:
    if isinstance(raw, str):
        text = raw.strip()
        return ParsedDocument([ParsedPage(page=None, text=text)]) if text else None

    pages: list[ParsedPage] = []
    for chunk in raw:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        meta = chunk.get("metadata") or {}
        pages.append(ParsedPage(page=_page_num(meta), text=text))
    return ParsedDocument(pages) if pages else None


def _pymupdf4llm_kwargs(*, force_ocr: bool | None = None) -> dict:
    p = config.parsing
    return {
        "page_chunks": True,
        "use_ocr": p.pdf_use_ocr,
        "force_ocr": p.pdf_force_ocr if force_ocr is None else force_ocr,
        "ocr_language": p.pdf_ocr_language,
    }


def _parse_pdf_pymupdf4llm(path: str, *, force_ocr: bool | None = None) -> ParsedDocument | None:
    import pymupdf4llm

    raw = pymupdf4llm.to_markdown(path, **_pymupdf4llm_kwargs(force_ocr=force_ocr))
    return _pages_from_pymupdf4llm(raw)


def _parse_pdf_fitz(path: str) -> ParsedDocument:
    import fitz

    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if text:
            pages.append(ParsedPage(page=i, text=text))
    doc.close()
    return ParsedDocument(pages)


def _parse_pdf(path: str) -> ParsedDocument:
    """PDF：pymupdf4llm 按页 Markdown；无文本层时自动 OCR 重试。"""
    p = config.parsing
    try:
        doc = _parse_pdf_pymupdf4llm(path)
        if doc and doc.full_text.strip():
            return doc

        if p.pdf_use_ocr and not p.pdf_force_ocr:
            logger.info("PDF 文本层为空或不足，启用 OCR 重试: %s", Path(path).name)
            doc = _parse_pdf_pymupdf4llm(path, force_ocr=True)
            if doc and doc.full_text.strip():
                return doc
    except Exception as e:
        logger.warning("pymupdf4llm 解析失败，回退 PyMuPDF 纯文本: %s", e)

    doc = _parse_pdf_fitz(path)
    if doc.full_text.strip():
        return doc

    if p.pdf_use_ocr and not p.pdf_force_ocr:
        logger.info("PyMuPDF 纯文本为空，最后尝试 force_ocr: %s", Path(path).name)
        try:
            doc = _parse_pdf_pymupdf4llm(path, force_ocr=True)
            if doc and doc.full_text.strip():
                return doc
        except Exception as e:
            logger.warning("PDF OCR 重试失败: %s", e)

    return doc


def _parse_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk") as f:
            return f.read()


def _parse_plain(path: str) -> ParsedDocument:
    text = _parse_txt(path).strip()
    return ParsedDocument([ParsedPage(page=None, text=text)] if text else [])


def _parse_docx(path: str) -> ParsedDocument:
    from docx import Document

    doc = Document(path)
    parts: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            parts.append("\n".join(rows))
    text = "\n\n".join(parts)
    return ParsedDocument([ParsedPage(page=None, text=text)] if text else [])


def _find_soffice() -> str | None:
    """查找 LibreOffice soffice，用于 .doc → .docx 转换。"""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        for pattern in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if Path(pattern).is_file():
                return pattern
    return None


def _convert_doc_to_docx(path: str) -> Path | None:
    """LibreOffice headless 将 .doc 转为临时 .docx。"""
    soffice = _find_soffice()
    if not soffice:
        return None

    out_dir = Path(tempfile.mkdtemp(prefix="exam_doc_"))
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out_dir), path],
            check=True,
            capture_output=True,
            timeout=120,
        )
        converted = out_dir / f"{Path(path).stem}.docx"
        if not converted.is_file():
            return None
        dest = Path(tempfile.mktemp(suffix=".docx", prefix="exam_doc_"))
        shutil.copy2(converted, dest)
        return dest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("LibreOffice 转换 .doc 失败: %s", e)
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _parse_doc(path: str) -> ParsedDocument:
    """旧版 .doc：LibreOffice 转 docx 后解析。"""
    docx_tmp = _convert_doc_to_docx(path)
    if docx_tmp:
        try:
            return _parse_docx(str(docx_tmp))
        finally:
            docx_tmp.unlink(missing_ok=True)

    raise BadRequestException(
        "无法解析 .doc 文件。请安装 LibreOffice，或将文件另存为 .docx 后重试。"
    )


def _parse_pptx(path: str) -> ParsedDocument:
    from pptx import Presentation

    prs = Presentation(path)
    pages: list[ParsedPage] = []
    for i, slide in enumerate(prs.slides, 1):
        texts: list[str] = []
        for shape in slide.shapes:
            if not hasattr(shape, "text"):
                continue
            t = shape.text.strip()
            if t:
                texts.append(t)
        if texts:
            pages.append(ParsedPage(page=i, text="\n".join(texts)))
    return ParsedDocument(pages)


_PARSERS = {
    ".pdf": _parse_pdf,
    ".txt": _parse_plain,
    ".md": _parse_plain,
    ".doc": _parse_doc,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
}


def parse_file(path: str) -> ParsedDocument:
    """根据扩展名解析文件，返回带页码的 ParsedDocument。"""
    ext = Path(path).suffix.lower()
    if ext not in _PARSERS:
        raise UnsupportedFormatException(
            f"不支持的文件格式: {ext}，仅接受 PDF/TXT/MD/DOC/DOCX/PPTX"
        )
    if not os.path.exists(path):
        raise BadRequestException(f"文件不存在: {path}")

    try:
        doc = _PARSERS[ext](path)
    except UnsupportedFormatException:
        raise
    except BadRequestException:
        raise
    except Exception as e:
        logger.error("文件解析失败 (%s): %s", path, e)
        raise BadRequestException(f"文件解析失败: {e}") from e

    if not doc.full_text.strip():
        raise BadRequestException("文件内容为空，无法入库")

    logger.info(
        "文件解析完成: %s, %d 页/段, 文本长度 %d 字符",
        Path(path).name,
        len(doc.pages),
        len(doc.full_text),
    )
    return doc
