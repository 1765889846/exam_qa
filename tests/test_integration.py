"""集成测试：入库 + 检索 + 生成（需 embedding 与 LLM API）。"""

import tempfile

import pytest

from src.config import config
from src.services.ingestion import ingest_file
from src.services.parsing import parse_file
from src.services.retrieval import retrieve
from src.services.query import ask as query_ask
from src.services.llm import OpenAIClient


@pytest.mark.integration
class TestIngestion:
    """入库管道集成测试。"""

    def test_ingest_markdown(self, sample_md_file, vector_store, doc_store):
        """上传 MD 文件完整入库。"""
        doc_id = ingest_file(
            path=sample_md_file,
            vs=vector_store,
            ds=doc_store,
        )
        assert doc_id is not None
        assert int(doc_id) > 0

        doc = doc_store.get(int(doc_id))
        assert doc["status"] == "done"
        assert doc["chunk_count"] > 0

    def test_ingest_txt(self, sample_txt_file, vector_store, doc_store):
        """上传 TXT 文件完整入库。"""
        doc_id = ingest_file(
            path=sample_txt_file,
            vs=vector_store,
            ds=doc_store,
        )
        doc = doc_store.get(int(doc_id))
        assert doc["status"] == "done"
        assert doc["chunk_count"] > 0

    def test_ingest_empty_file_fails(self, temp_dir, vector_store, doc_store):
        """空文件入库应抛出异常。"""
        p = temp_dir / "empty.txt"
        p.write_text("   \n  ", encoding="utf-8")
        from src.exceptions import BadRequestException
        with pytest.raises(BadRequestException):
            ingest_file(path=str(p), vs=vector_store, ds=doc_store)

    def test_ingest_unsupported_format(self, temp_dir, vector_store, doc_store):
        """不支持的文件格式应抛出异常。"""
        p = temp_dir / "test.xyz"
        p.write_text("fake", encoding="utf-8")
        from src.exceptions import UnsupportedFormatException
        with pytest.raises(UnsupportedFormatException):
            ingest_file(path=str(p), vs=vector_store, ds=doc_store)

    def test_parse_markdown(self, sample_md_file):
        """解析 MD 文件。"""
        doc = parse_file(sample_md_file)
        assert "测试文档" in doc.full_text
        assert len(doc.full_text) > 0


@pytest.mark.integration
class TestRetrievalGeneration:
    """检索与生成集成测试。"""

    @pytest.fixture(autouse=True)
    def _setup_data(self, vector_store, doc_store):
        """每个测试前导入一份测试文档。"""
        # 创建测试 MD 文件
        content = """# 信号与系统重点

## 傅里叶变换

傅里叶变换是一种将信号从时域转换到频域的数学工具，在信号处理中有广泛应用。

连续时间傅里叶变换定义：
X(f) = ∫ x(t)e^(-j2πft) dt

其中 x(t) 为时域信号，X(f) 为频域表示。变换将信号分解为不同频率分量。

傅里叶变换基本性质：
- 线性、时移、频移、尺度变换
- 卷积定理：时域卷积 ↔ 频域相乘

## 卷积定理

卷积定理揭示时域与频域运算的对偶关系：
时域卷积对应频域相乘：x(t)*h(t) ↔ X(f)·H(f)
频域卷积对应时域相乘：x(t)·h(t) ↔ X(f)*H(f)

这是系统分析中最常用的定理之一，使频域分析变得简洁高效。

## 采样定理

奈奎斯特采样定理：为避免混叠，采样频率 fs > 2fmax。
fs/2 为奈奎斯特频率，低于此频率采样会产生混叠失真。
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            self._test_file = f.name

        ingest_file(
            path=self._test_file,
            vs=vector_store,
            ds=doc_store,
        )

    def test_retrieve_relevant(self, vector_store):
        """检索相关内容。"""
        results = retrieve(
            query="傅里叶变换的定义",
            vs=vector_store,
            top_k=3,
        )
        assert len(results) > 0
        # 至少有一个结果的文本包含"傅里叶"
        texts = [r.get("text", "") for r in results]
        assert any("傅里叶" in t for t in texts)

    def test_retrieve_irrelevant_threshold(self, vector_store):
        """不相关查询应该得分低。"""
        results = retrieve(
            query="拉普拉斯变换",
            vs=vector_store,
            top_k=5,
        )
        if results:
            # 不相关查询的最高分应低于相关查询
            assert results[0]["score"] < 0.5  # 远低于傅里叶查询

    def test_ask_end_to_end(self, vector_store):
        """端到端问答：检索 + LLM 生成。"""
        llm = OpenAIClient(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )

        result = query_ask(
            question="什么是卷积定理",
            mode="qa",
            vs=vector_store,
            llm=llm,
        )
        assert result.grounded is True
        assert len(result.answer) > 0
        assert len(result.citations) > 0

    def test_ask_refusal(self, vector_store):
        """不相关问题应拒答。"""
        llm = OpenAIClient(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )

        result = query_ask(
            question="What is the capital of France",
            mode="qa",
            vs=vector_store,
            llm=llm,
        )
        assert result.grounded is False
        assert "未找到" in result.answer
        assert len(result.citations) == 0
