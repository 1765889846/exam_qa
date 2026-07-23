"""pytest fixtures：隔离存储 + 样例文件。"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


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
