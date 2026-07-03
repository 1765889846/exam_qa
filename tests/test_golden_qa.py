"""冒烟回归测试：golden_qa.jsonl。

验证核心问答链路不退化。先入库测试数据，再逐条验证 golden QA。
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.config import config
from src.services.ingestion import ingest_file
from src.services.query import ask as query_ask
from src.services.llm import OpenAIClient

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_qa.jsonl"


def _load_golden_cases():
    """加载 golden_qa.jsonl 并返回 case 列表。"""
    cases = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


@pytest.mark.integration
class TestGoldenQA:
    """Golden QA 冒烟回归。"""

    @pytest.fixture(autouse=True)
    def _setup_data(self, vector_store, doc_store):
        """入库 golden 测试数据。"""
        content = """# 信号与系统复习资料

## 傅里叶变换

傅里叶变换是一种将信号从时域转换到频域的数学工具，在信号处理、通信系统和图像处理中有广泛应用。

连续时间傅里叶变换的定义为：
X(f) = ∫ x(t)e^(-j2πft) dt

其中 x(t) 为时域信号，X(f) 为频域表示。该变换将信号分解为不同频率的正弦波分量。

傅里叶变换的主要性质包括：
- 线性性质：a·x1(t) + b·x2(t) ↔ a·X1(f) + b·X2(f)
- 时移性质：x(t - t0) ↔ X(f)·e^(-j2πft0)
- 频移性质：x(t)·e^(j2πf0t) ↔ X(f - f0)
- 卷积定理：时域卷积对应频域相乘
- 尺度变换：x(at) ↔ (1/|a|)·X(f/a)

## 卷积定理

卷积定理是信号与系统课程中最重要的定理之一。它揭示了时域运算与频域运算之间的对偶关系：

时域卷积对应频域相乘：
x(t) * h(t) ↔ X(f) · H(f)

频域卷积对应时域相乘：
x(t) · h(t) ↔ X(f) * H(f)

卷积定理极大地简化了系统分析——在频域中，线性时不变系统的输出等于输入频谱与系统频率响应的乘积。

## 采样定理

奈奎斯特采样定理（Nyquist Sampling Theorem）是数字信号处理的基石。

定理内容：为了避免频谱混叠，采样频率 fs 必须大于信号最高频率 fmax 的两倍：
fs > 2fmax

其中 fs/2 称为奈奎斯特频率（Nyquist frequency）。如果采样频率低于 2fmax，高频分量会被折叠到低频区域，产生混叠失真。

实际应用中，通常取 fs ≥ 2.5fmax 以保证足够的裕量。例如，音频 CD 采用 44.1kHz 采样率，覆盖人耳可听的 20kHz 范围。
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

    @pytest.mark.parametrize("case", _load_golden_cases())
    def test_golden_qa(self, case, vector_store):
        """逐条验证 golden QA。"""
        llm = OpenAIClient(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )

        result = query_ask(
            question=case["question"],
            mode=case.get("mode", "qa"),
            vs=vector_store,
            llm=llm,
        )

        if case.get("expect_refusal"):
            assert result.grounded is False, (
                f"期望拒答但 grounded=True: {case['question']}"
            )
        else:
            assert result.grounded is True, (
                f"期望有答案但 grounded=False: {case['question']}"
            )
            for keyword in case.get("expected_contains", []):
                assert keyword in result.answer, (
                    f"回答中缺少关键词 '{keyword}': {result.answer[:100]}"
                )
