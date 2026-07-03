"""pytest fixtures：提供隔离的存储实例和测试数据。"""

import os
import tempfile
import shutil
from pathlib import Path

import pytest

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


@pytest.fixture
def temp_dir():
    """临时目录，测试结束后尽力清理（Windows 上 Chroma 可能短暂锁文件）。"""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def doc_store(temp_dir):
    """隔离的 SQLiteDocStore 实例。"""
    from src.services.storage.doc_store import SQLiteDocStore
    db_path = temp_dir / "test_meta.db"
    store = SQLiteDocStore(str(db_path))
    yield store
    store.close()


@pytest.fixture
def vector_store(temp_dir):
    """隔离的 ChromaVectorStore 实例。"""
    from src.services.storage.vector_store import ChromaVectorStore
    chroma_path = temp_dir / "test_chroma"
    store = ChromaVectorStore(str(chroma_path), collection_name="test_exam_rag")
    yield store
    store.close()


@pytest.fixture
def sample_md_file(temp_dir):
    """创建一个测试用的 Markdown 文件。"""
    content = """# 测试文档

## 第一节

这是测试内容。用于验证入库管道的分块功能。

分块大小默认 500 字符，重叠 50 字符。

## 第二节

傅里叶变换是信号与系统中的核心概念。它将时域信号转换到频域。

连续时间傅里叶变换的定义为积分形式。

## 第三节

卷积定理是傅里叶变换最重要的性质之一。时域卷积对应频域乘积。
"""
    path = temp_dir / "test_sample.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_txt_file(temp_dir):
    """创建一个测试用的 TXT 文件。"""
    content = "这是纯文本测试文件。\n用于验证 TXT 格式解析。\n内容比较简单。"
    path = temp_dir / "test_sample.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def short_text():
    """短文本，不需要分块。"""
    return "信号与系统是电子信息类专业的重要基础课程。"


@pytest.fixture
def long_text():
    """长文本，需要被分块。"""
    return "傅里叶变换是一种数学工具。" * 100
