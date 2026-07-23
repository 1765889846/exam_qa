"""集成：入库 + 端到端问答（需 Embedding / LLM；默认跳过）。"""

import tempfile

import pytest

from src.config import config
from src.exceptions import BadRequestException, UnsupportedFormatException
from src.services.ingestion import ingest_file
from src.services.llm import OpenAIClient
from src.services.query import ask as query_ask
from src.services.storage.catalog_store import (
    DEFAULT_COLLEGE_ID,
    DEFAULT_COURSE_ID,
    DEFAULT_COURSE_NAME,
)

_CID = DEFAULT_COURSE_ID


@pytest.mark.integration
class TestIngestAndAsk:
    def test_ingest_markdown(self, sample_md_file, vector_store, doc_store):
        doc_id = ingest_file(
            path=sample_md_file,
            vs=vector_store,
            ds=doc_store,
            course_id=_CID,
        )
        doc = doc_store.get(int(doc_id))
        assert doc["status"] == "done"
        assert doc["chunk_count"] > 0
        assert doc["course_id"] == _CID

    def test_ingest_rejects_empty_and_bad_ext(self, temp_dir, vector_store, doc_store):
        empty = temp_dir / "empty.txt"
        empty.write_text("   \n", encoding="utf-8")
        with pytest.raises(BadRequestException):
            ingest_file(str(empty), vector_store, doc_store, course_id=_CID)

        bad = temp_dir / "x.xyz"
        bad.write_text("x", encoding="utf-8")
        with pytest.raises(UnsupportedFormatException):
            ingest_file(str(bad), vector_store, doc_store, course_id=_CID)

    def test_ask_grounded_and_refusal(self, vector_store, doc_store):
        content = """# 样例

## 卷积定理

时域卷积对应频域相乘：x(t)*h(t) ↔ X(f)·H(f)。
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        ingest_file(
            path,
            vector_store,
            doc_store,
            course_id=_CID,
            course=DEFAULT_COURSE_NAME,
            college_id=DEFAULT_COLLEGE_ID,
        )
        llm = OpenAIClient(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )
        ok = query_ask("什么是卷积定理", "qa", vector_store, llm, _CID)
        assert ok.grounded is True
        assert ok.citations

        refuse = query_ask(
            "What is the capital of France", "qa", vector_store, llm, _CID
        )
        assert refuse.grounded is False
        assert "未找到" in refuse.answer
