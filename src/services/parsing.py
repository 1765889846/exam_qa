"""文档解析：PDF / Office / 纯文本 → ParsedDocument。"""

from __future__ import annotations

import logging
import os
import re
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
    page: int | None  # PDF/PPT 1-based；纯文本/docx 为 None
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
    pages = []
    for chunk in raw:
        text = (chunk.get("text") or "").strip()
        if text:
            pages.append(ParsedPage(page=_page_num(chunk.get("metadata") or {}), text=text))
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

    return _pages_from_pymupdf4llm(
        pymupdf4llm.to_markdown(path, **_pymupdf4llm_kwargs(force_ocr=force_ocr))
    )


def _parse_pdf_fitz(path: str) -> ParsedDocument:
    import fitz

    doc = fitz.open(path)
    try:
        pages = [
            ParsedPage(page=i, text=t)
            for i, page in enumerate(doc, 1)
            if (t := page.get_text().strip())
        ]
        return ParsedDocument(pages)
    finally:
        doc.close()


def _parse_pdf(path: str) -> ParsedDocument:
    p = config.parsing
    try:
        doc = _parse_pdf_pymupdf4llm(path)
        if doc and doc.full_text.strip():
            return doc
        if p.pdf_use_ocr and not p.pdf_force_ocr:
            logger.info("PDF 空文本，OCR 重试: %s", Path(path).name)
            doc = _parse_pdf_pymupdf4llm(path, force_ocr=True)
            if doc and doc.full_text.strip():
                return doc
    except Exception as e:
        logger.warning("pymupdf4llm 失败，回退 fitz: %s", e)

    doc = _parse_pdf_fitz(path)
    if doc.full_text.strip():
        return doc

    if p.pdf_use_ocr and not p.pdf_force_ocr:
        try:
            ocr = _parse_pdf_pymupdf4llm(path, force_ocr=True)
            if ocr and ocr.full_text.strip():
                return ocr
        except Exception as e:
            logger.warning("PDF OCR 失败: %s", e)
    return doc


def _parse_txt(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    # ponytail: 怪编码替换非法字节，不阻断
    return data.decode("utf-8", errors="replace")


def _parse_plain(path: str) -> ParsedDocument:
    text = _parse_txt(path).strip()
    return ParsedDocument([ParsedPage(page=None, text=text)] if text else [])


def _table_to_text(table) -> str:
    rows: list[str] = []
    for row in table.rows:
        seen: set[int] = set()
        cells: list[str] = []
        for cell in row.cells:
            key = id(cell._tc)
            if key in seen:
                continue
            seen.add(key)
            if t := cell.text.strip():
                cells.append(t)
            for nested in cell.tables:
                if nt := _table_to_text(nested):
                    cells.append(nt)
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _iter_block_items(parent):
    from docx.document import Document as DocxDocument
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = parent.element.body if isinstance(parent, DocxDocument) else parent._element
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _story_parts(container) -> list[str]:
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    parts: list[str] = []
    for block in _iter_block_items(container):
        if isinstance(block, Paragraph):
            if t := (block.text or "").strip():
                parts.append(t)
        elif isinstance(block, Table):
            if t := _table_to_text(block):
                parts.append(t)
    return parts


def _header_footer_parts(doc) -> list[str]:
    # 单节异常跳过，避免整份 docx 失败
    seen: set[str] = set()
    out: list[str] = []
    for section in doc.sections:
        for part in (section.header, section.footer):
            try:
                block = "\n".join(_story_parts(part)).strip()
            except Exception:
                continue
            if block and block not in seen:
                seen.add(block)
                out.append(block)
    return out


def _textbox_parts(doc) -> list[str]:
    from docx.oxml.ns import qn

    parts: list[str] = []
    for txbx in doc.element.body.iter(qn("w:txbxContent")):
        texts = [(n.text or "").strip() for n in txbx.iter(qn("w:t")) if (n.text or "").strip()]
        if texts:
            parts.append("\n".join(texts))
    return parts


def _parse_docx(path: str) -> ParsedDocument:
    from docx import Document

    doc = Document(path)
    parts = _header_footer_parts(doc) + _story_parts(doc) + _textbox_parts(doc)
    text = "\n\n".join(parts)
    return ParsedDocument([ParsedPage(page=None, text=text)] if text else [])


def _find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        if found := shutil.which(name):
            return found
    if os.name == "nt":
        for exe in ("soffice.com", "soffice.exe"):
            for pattern in (
                rf"C:\Program Files\LibreOffice\program\{exe}",
                rf"C:\Program Files (x86)\LibreOffice\program\{exe}",
            ):
                if Path(pattern).is_file():
                    return pattern
    return None


def _convert_doc_to_docx_soffice(path: str) -> Path | None:
    soffice = _find_soffice()
    if not soffice:
        return None

    out_dir = Path(tempfile.mkdtemp(prefix="exam_doc_"))
    dest: Path | None = None
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
        fd, dest_name = tempfile.mkstemp(suffix=".docx", prefix="exam_doc_")
        os.close(fd)
        dest = Path(dest_name)
        shutil.copy2(converted, dest)
        return dest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("LibreOffice 转换失败: %s", e)
        if dest is not None:
            dest.unlink(missing_ok=True)
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _convert_doc_to_docx_word(path: str) -> Path | None:
    """Windows：无 LibreOffice 时用本机 Word COM 另存为 .docx。"""
    if os.name != "nt":
        return None
    src = str(Path(path).resolve())
    fd, dest_name = tempfile.mkstemp(suffix=".docx", prefix="exam_doc_")
    os.close(fd)
    dest = Path(dest_name)
    dest.unlink(missing_ok=True)
    src_ps = src.replace("'", "''")
    dest_ps = str(dest.resolve()).replace("'", "''")
    ps = (
        "$ErrorActionPreference='Stop'; "
        "$word=New-Object -ComObject Word.Application; "
        "$word.Visible=$false; "
        f"$doc=$word.Documents.Open('{src_ps}'); "
        f"$doc.SaveAs([ref]'{dest_ps}',[ref]16); "
        "$doc.Close(); $word.Quit(); "
        "[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        dest.unlink(missing_ok=True)
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("Word COM 转换失败: %s", e)
        dest.unlink(missing_ok=True)
        return None


def _convert_doc_to_docx(path: str) -> Path | None:
    return _convert_doc_to_docx_soffice(path) or _convert_doc_to_docx_word(path)


def _parse_doc(path: str) -> ParsedDocument:
    docx_tmp = _convert_doc_to_docx(path)
    if docx_tmp:
        try:
            return _parse_docx(str(docx_tmp))
        finally:
            docx_tmp.unlink(missing_ok=True)
    raise BadRequestException(
        "无法解析 .doc 文件。请安装 LibreOffice 或 Microsoft Word，或将文件另存为 .docx 后重试。"
    )


def _shape_texts(shape) -> list[str]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
        return [t for child in shape.shapes for t in _shape_texts(child)]

    texts: list[str] = []
    if getattr(shape, "has_table", False):
        rows = []
        for row in shape.table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            texts.append("\n".join(rows))
    if getattr(shape, "has_text_frame", False):
        if t := shape.text_frame.text.strip():
            texts.append(t)
    elif hasattr(shape, "text") and (t := (shape.text or "").strip()):
        texts.append(t)
    return texts


def _convert_pptx_to_pdf_soffice(path: str) -> Path | None:
    """LibreOffice headless 将 PPTX 转为 PDF，可覆盖 SmartArt/图表/母版文本。"""
    soffice = _find_soffice()
    if not soffice:
        return None

    out_dir = Path(tempfile.mkdtemp(prefix="exam_pptx_"))
    profile_dir = Path(tempfile.mkdtemp(prefix="exam_lo_profile_"))
    dest: Path | None = None
    try:
        user_install = "file:///" + str(profile_dir).replace("\\", "/")
        subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                f"-env:UserInstallation={user_install}",
                path,
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        converted = out_dir / f"{Path(path).stem}.pdf"
        if not converted.is_file():
            return None
        fd, dest_name = tempfile.mkstemp(suffix=".pdf", prefix="exam_pptx_")
        os.close(fd)
        dest = Path(dest_name)
        shutil.copy2(converted, dest)
        return dest
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("LibreOffice PPTX 转 PDF 失败: %s", e)
        if dest is not None:
            dest.unlink(missing_ok=True)
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)


def _convert_pptx_to_pdf_powerpoint(path: str) -> Path | None:
    """Windows：无 LibreOffice 时用本机 PowerPoint COM 导出 PDF（ppSaveAsPDF=32）。"""
    if os.name != "nt":
        return None
    src = str(Path(path).resolve())
    fd, dest_name = tempfile.mkstemp(suffix=".pdf", prefix="exam_pptx_")
    os.close(fd)
    dest = Path(dest_name)
    dest.unlink(missing_ok=True)
    src_ps = src.replace("'", "''")
    dest_ps = str(dest.resolve()).replace("'", "''")
    ps = (
        "$ErrorActionPreference='Stop'; "
        "$pp=New-Object -ComObject PowerPoint.Application; "
        "try { "
        f"$pres=$pp.Presentations.Open('{src_ps}',-1,0,0); "
        f"$pres.SaveAs([ref]'{dest_ps}',[ref]32); "
        "$pres.Close(); "
        "} finally { "
        "$pp.Quit(); "
        "[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp)|Out-Null "
        "}"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        dest.unlink(missing_ok=True)
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("PowerPoint COM 导出 PDF 失败: %s", e)
        dest.unlink(missing_ok=True)
        return None


def _convert_pptx_to_pdf(path: str) -> Path | None:
    return _convert_pptx_to_pdf_soffice(path) or _convert_pptx_to_pdf_powerpoint(path)


def _parse_pptx_direct(path: str) -> ParsedDocument:
    from pptx import Presentation

    pages: list[ParsedPage] = []
    for i, slide in enumerate(Presentation(path).slides, 1):
        texts = [t for shape in slide.shapes for t in _shape_texts(shape)]
        if slide.has_notes_slide:
            if notes := slide.notes_slide.notes_text_frame.text.strip():
                texts.append(f"[备注]\n{notes}")
        if texts:
            pages.append(ParsedPage(page=i, text="\n".join(texts)))
    return ParsedDocument(pages)


def _tesseract_available() -> bool:
    if shutil.which("tesseract"):
        return True
    if os.name == "nt" and Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").is_file():
        return True
    return False


def _clean_pdf_markdown(text: str) -> str:
    """清理 pymupdf4llm 输出的 markdown 杂质（图片占位符、标题标记等）。"""
    text = re.sub(r"\*\*==>.*?<==\*\*", "", text, flags=re.S)
    text = re.sub(r"^\s*#+\s*$", "", text, flags=re.M)
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*\|?[\s:|-]+\|?\s*$", "", text, flags=re.M)
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines).strip()


def _merge_pages_by_length(a: list[ParsedPage], b: list[ParsedPage]) -> ParsedDocument:
    """同一 PPT 的两种提取结果按页择优合并（PDF 页号与 PPT 页号一致）。"""
    pages: list[ParsedPage] = []
    for i in range(max(len(a), len(b))):
        pa = a[i] if i < len(a) else None
        pb = b[i] if i < len(b) else None
        if pa and pb:
            pages.append(pa if len(pa.text) >= len(pb.text) else pb)
        else:
            pages.append(pa or pb)
    return ParsedDocument([p for p in pages if p.text and p.text.strip()])


def _parse_pptx(path: str) -> ParsedDocument:
    """优先转 PDF 走 pymupdf4llm 管线，清理杂质后与 python-pptx 按页择优合并；
    图片型 PPT 自动尝试 OCR（需系统安装 Tesseract）。"""
    direct = _parse_pptx_direct(path)
    pdf_tmp = _convert_pptx_to_pdf(path)
    if not pdf_tmp:
        return direct
    try:
        doc = _parse_pdf(str(pdf_tmp))
        pdf_pages = [
            ParsedPage(page=p.page, text=_clean_pdf_markdown(p.text))
            for p in doc.pages
            if _clean_pdf_markdown(p.text).strip()
        ]
        direct_chars = sum(len(p.text) for p in direct.pages)
        pdf_chars = sum(len(p.text) for p in pdf_pages)
        if pdf_chars < max(direct_chars, 1) * 0.5 and _tesseract_available():
            try:
                ocr_doc = _parse_pdf_pymupdf4llm(str(pdf_tmp), force_ocr=True)
                ocr_pages = [
                    ParsedPage(page=p.page, text=_clean_pdf_markdown(p.text))
                    for p in ocr_doc.pages
                    if _clean_pdf_markdown(p.text).strip()
                ]
                ocr_chars = sum(len(p.text) for p in ocr_pages)
                if ocr_chars > pdf_chars:
                    logger.info("PPTX 图片 OCR 生效: %s -> %d 字", Path(path).name, ocr_chars)
                    pdf_pages = ocr_pages
            except Exception as e:
                logger.warning("PPTX 图片 OCR 失败: %s", e)
        return _merge_pages_by_length(direct.pages, pdf_pages)
    except Exception as e:
        logger.warning("PPTX 转 PDF 解析失败，回退 python-pptx: %s", e)
        return direct
    finally:
        pdf_tmp.unlink(missing_ok=True)


_PARSERS = {
    ".pdf": _parse_pdf,
    ".txt": _parse_plain,
    ".md": _parse_plain,
    ".doc": _parse_doc,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
}


def parse_file(path: str) -> ParsedDocument:
    ext = Path(path).suffix.lower()
    if ext not in _PARSERS:
        raise UnsupportedFormatException(
            f"不支持的文件格式: {ext}，仅接受 PDF/TXT/MD/DOC/DOCX/PPTX"
        )
    if not os.path.exists(path):
        raise BadRequestException(f"文件不存在: {path}")

    try:
        doc = _PARSERS[ext](path)
    except (UnsupportedFormatException, BadRequestException):
        raise
    except Exception as e:
        logger.error("文件解析失败 (%s): %s", path, e)
        raise BadRequestException(f"文件解析失败: {e}") from e

    if not doc.full_text.strip():
        raise BadRequestException("文件内容为空，无法入库")

    logger.info(
        "解析完成: %s pages=%d chars=%d",
        Path(path).name,
        len(doc.pages),
        len(doc.full_text),
    )
    return doc
