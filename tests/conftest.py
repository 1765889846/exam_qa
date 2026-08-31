"""pytest fixtures：隔离存储 + 样例文件。"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 单元测试不触发 MinerU 子进程（避免 CLI 挂起/慢），PDF 走 pymupdf 快速链路
os.environ.setdefault("PDF_PARSER", "pymupdf")
os.environ.setdefault("MINERU_TIMEOUT", "10")


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def doc_store(temp_dir):
    from src.services.storage.doc_store import SQLiteDocStore

    store = SQLiteDocStore(str(temp_dir / "test_meta.db"))
    yield store
    store.close()


@pytest.fixture
def vector_store(temp_dir):
    from src.services.storage.vector_store import ChromaVectorStore

    store = ChromaVectorStore(
        str(temp_dir / "test_chroma"), collection_name="test_exam_rag"
    )
    yield store
    store.close()


@pytest.fixture
def sample_md_file(temp_dir):
    content = """# 测试文档

## 第一节

这是测试内容。用于验证入库管道的分块功能。

## 第二节

傅里叶变换是信号与系统中的核心概念。
"""
    path = temp_dir / "test_sample.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_txt_file(temp_dir):
    path = temp_dir / "test_sample.txt"
    path.write_text(
        "这是纯文本测试文件。\n用于验证 TXT 格式解析。\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture(autouse=True)
def _clear_retrieval_caches():
    """每个用例执行前清空检索缓存（BM25 语料、查询向量），保证用例隔离。"""
    from src.services.retrieval import clear_query_embed_cache, invalidate_bm25_cache

    clear_query_embed_cache()
    invalidate_bm25_cache()
    yield


# ── 测试结束后自动清理测试残留 ──────────────────────────────────

_SAMPLE_FILES = (
    "laplace-transform.txt",
    "eigenvalues.docx",
    "bayes-theorem.pptx",
    "ode-first-order.pdf",
    "determinants.doc",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _cleanup_test_artifacts() -> None:
    """删除测试产生的残留：样本文件、占位笔记、pytest 临时目录。

    只清理已知的测试产物，不触碰用户真实资料。
    """
    root = _project_root()

    knowledge = root / "data" / "knowledge"
    if knowledge.is_dir():
        for name in _SAMPLE_FILES:
            (knowledge / name).unlink(missing_ok=True)
        for note in knowledge.glob("note_*.md"):
            try:
                if note.read_text(encoding="utf-8").strip() == "# hello":
                    note.unlink(missing_ok=True)
            except (OSError, UnicodeDecodeError):
                continue

    shutil.rmtree(root / ".pytest-tmp", ignore_errors=True)


def pytest_sessionfinish(session, exitstatus):
    """pytest 会话结束时自动清理测试残留（不影响真实资料）。"""
    _cleanup_test_artifacts()
