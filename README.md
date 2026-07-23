<div align="center">

# 溯知

### exam-rag · 据源而答 · 出处可循

把讲义、笔记、真题放进本机资料库，用自然语言提问。  
答案必须落到具体片段；检索不够就拒答，不硬编。

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-orange?style=flat-square)](https://www.trychroma.com/)
[![uv](https://img.shields.io/badge/uv-package-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)

</div>

## 它做什么

本地跑起来的课程资料问答：入库 → 按课隔离检索 → 带引用作答。前端在 `www/`（手写 HTML/CSS/JS，无构建），后端是 FastAPI + Chroma + SQLite。

| 能力 | 说明 |
|:-----|:-----|
| 自由问答 | `mode=qa`，混合检索（向量 + BM25 → RRF；可选 BGE 精排） |
| 知识点 | `mode=concept`，更大 top_k，按「定义 → 公式 → 例题」聚合 |
| 章节概览 | `mode=chapter`，按 `chapter` 元数据聚合（不走语义检索） |
| 拒答 | 最高分低于阈值 → `grounded: false`，固定文案，禁止无引用硬编 |
| 多课隔离 | 一切检索 / 上传 / 删除都带 `course_id` |
| 资料格式 | PDF · TXT · MD · DOC · DOCX · PPTX（扫描 PDF 可选 OCR） |

## Quick Start

需要 Python ≥ 3.11、[uv](https://docs.astral.sh/uv/)，以及 OpenAI 兼容的对话 API（`LLM_API_KEY`）。扫描版 PDF 可选 [Tesseract](https://github.com/tesseract-ocr/tesseract)（`eng` / `chi_sim`）。旧版 `.doc` 需 [LibreOffice](https://www.libreoffice.org/) 或本机 Microsoft Word。

```bash
cp .env.example .env   # 填写 LLM_API_KEY，或启动后在设置页注册模型
uv sync
uv run exam            # → http://127.0.0.1:8787
```

| 地址 | 用途 |
|:-----|:-----|
| [`/sz/`](http://127.0.0.1:8787/sz/) | 对话（自由问答 / 知识点 / 章节概览） |
| [`/sz-docs/`](http://127.0.0.1:8787/sz-docs/) | 资料上传 / 扫描（可选强制重建） |
| [`/sz-cfg/`](http://127.0.0.1:8787/sz-cfg/) | 设置（LLM、检索与 BGE 精排、OCR…） |
| [`/docs`](http://127.0.0.1:8787/docs) | OpenAPI |
| [`/api/v1/health`](http://127.0.0.1:8787/api/v1/health) | 健康检查 |

启动时会校验配置；资料入库请在资料页手动上传或扫描（启动不再自动扫库）。

## Commands

| 命令 | 说明 |
|:-----|:-----|
| `uv sync` | 安装依赖 |
| `uv run exam` | 启动服务（默认 `8787`） |
| `DEBUG=true uv run exam` | 调试模式 |
| `uv run pytest -q` | 单元测试 |
| `uv run pytest -q -m integration` | 集成测试（需 Embedding 与 LLM） |
| `uv run python -m tests.eval.run_retrieval_eval --chroma ./storage/chroma` | 离线 Recall@K / MRR |
| `uv add <package>` | 添加依赖 |

```bash
curl http://127.0.0.1:8787/api/v1/health
```

## Architecture

浏览器只调 `/api/v1/*`；RAG 在 `services/`，不进 UI。

```mermaid
flowchart TB
  subgraph browser["浏览器 · www/"]
    SZ["sz/ 对话"]
    DOCS["sz-docs/ 资料"]
    CFG["sz-cfg/ 设置"]
  end

  subgraph http["apis/v1/"]
    EP["ask · documents · catalog<br/>config · llm-providers · health · embedding"]
  end

  subgraph svc["services/"]
    direction TB
    ING["ingestion<br/>解析 → 分块 → 向量化"]
    Q["query<br/>检索 → 阈值 → 生成 / 拒答"]
    RET["retrieval · BM25+RRF"]
    GEN["generation"]
    EMB["embedding"]
    LLM["llm · llm_providers"]
  end

  subgraph persist["持久化"]
    CH[("Chroma · course_id")]
    META[("SQLite · 文档 / 目录")]
    FILES[("data/knowledge/")]
    REG[("data/llm_providers.json")]
  end

  browser -->|HTTP| http --> svc
  ING --> EMB
  ING --> CH
  ING --> META
  ING --> FILES
  Q --> RET --> CH
  Q --> GEN --> LLM
  LLM --> REG
  RET -.->|按 course_id 过滤| CH
```

```mermaid
flowchart LR
  subgraph ingest["入库"]
    A1["上传 / 扫描 / 强制重建"] --> A2["parsing"] --> A3["分块 + chapter"] --> A4["embedding"] --> A5[("Chroma + SQLite")]
  end

  subgraph ask["问答"]
    B1["提问 + course_id + mode"] --> B2{"mode?"}
    B2 -->|qa / concept| B3["向量 + BM25 → RRF"]
    B3 --> B4["可选 BGE 精排"]
    B4 --> B5{"score ≥ 阈值?"}
    B2 -->|chapter| B6["按 chapter 元数据聚合"]
    B5 -->|是| B7["LLM + citations"]
    B5 -->|否| B8["拒答 · grounded: false"]
    B6 --> B7
  end
```

| 模块 | 职责 |
|:-----|:-----|
| `ingestion` / `parsing` | 解析分块入库；写入 `chapter`；PDF 可 OCR |
| `retrieval` / `rerank` | 向量 + BM25 → RRF；可选 BGE CrossEncoder 精排 |
| `query` / `generation` | `qa` / `concept` / `chapter` 编排与 prompt |
| `eval_metrics` | 离线 Recall@K / MRR |
| `embedding` / `llm` | 本地或 OpenAI 兼容 API |
| `storage/` | Chroma 向量 · SQLite 元数据与目录 |

细节见 [docs/02-模块架构.md](docs/02-模块架构.md)。

<details>
<summary>目录结构</summary>

```
exam-rag/
├── data/                    # 运行时（gitignore）：knowledge、llm_providers.json
├── storage/                 # 运行时（gitignore）：Chroma · meta.db · 日志
├── src/
│   ├── main.py              # FastAPI · 挂载 www/
│   ├── apis/v1/
│   └── services/
├── www/                     # 前端源码（入库）
│   ├── shared/
│   ├── sz/
│   ├── sz-docs/
│   └── sz-cfg/
├── docs/
└── tests/
```

</details>

## Configuration

优先级：**环境变量 > `.env` > 代码默认值**。复制 `.env.example`，或在 `/sz-cfg/` 改。

| 分组 | 关键变量 |
|:-----|:---------|
| LLM | `LLM_PROVIDER` · `LLM_API_KEY` · `LLM_BASE_URL` · `LLM_MODEL` |
| Embedding | `EMBEDDING_PROVIDER`（`local` / `openai`）· `EMBEDDING_MODEL` |
| 存储 | `CHROMA_PATH` · `SQLITE_PATH` · `KNOWLEDGE_DIR` · `MAX_UPLOAD_MB` |
| PDF | `PDF_USE_OCR` · `PDF_FORCE_OCR` · `PDF_OCR_LANGUAGE` |
| 代理 | `PROXY_URL` · `PROXY_ENABLED` · `NO_PROXY` |

可注册多个 LLM（OpenAI 兼容 / Ollama），「设为当前」后会写回 `.env`。

<details>
<summary>检索与分块</summary>

| 参数 | 默认 | 含义 |
|:-----|:-----|:-----|
| `top_k` | 5 | RRF 融合后保留条数；`concept` 默认更大 |
| `score_threshold` | 0.25 | 低于此分拒答；精排开启时作用于 sigmoid(logit) |
| `RERANK_ENABLED` | false | 是否启用 BGE CrossEncoder 精排 |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 精排模型（sentence-transformers） |
| `RERANK_CANDIDATES` | 20 | 精排前候选池大小 |
| `RERANK_TOP_N` | 0（=top_k） | 精排后保留条数 |
| `chunk_size` | 800 | 分块字符数 |
| `chunk_overlap` | 50 | 相邻块重叠 |

</details>

## API

统一：`{ "code": 200, "data": … }` 或 `{ "code": 4xx, "message": "…" }`。完整契约见 [`/docs`](http://127.0.0.1:8787/docs)。

| 方法 | 路径 | 说明 |
|:----:|:-----|:-----|
| `GET` | `/api/v1/health` | 连通性 |
| `GET` / `PATCH` | `/api/v1/config` | 配置 |
| `GET` / `POST` | `/api/v1/llm-providers` | 列出 / 注册模型 |
| `POST` | `/api/v1/llm-providers/active` | 切换当前模型 |
| `DELETE` | `/api/v1/llm-providers/{name}` | 删除注册项 |
| `POST` | `/api/v1/embedding/warmup` | 后台拉取/加载本地模型或探测远程 API |
| `GET` | `/api/v1/embedding/status` | Embedding 就绪状态与拉取进度（`warmup.percent`） |
| `GET` | `/api/v1/colleges` | 学院 |
| `GET` | `/api/v1/courses` | 课程（可选 `?college_id=`） |
| `POST` | `/api/v1/documents` | 上传（Form 必填 `course_id`） |
| `GET` | `/api/v1/documents` | 列表（`?course_id=`） |
| `POST` | `/api/v1/documents/scan` | 扫描 knowledge（Form：`course_id`；可选 `force=true` 强制重建） |
| `DELETE` | `/api/v1/documents/{doc_id}` | 删除（`?course_id=`） |
| `POST` | `/api/v1/ask` | 问答（`course_id`；`mode=qa\|concept\|chapter`） |

默认课：`course-default`。同一物理文件不会跨课改归属。

**章节概览（`mode=chapter`）**：依赖入库时写入的 `chapter` 元数据。旧库请到资料页勾选「强制重建」再扫描，或重新上传；普通扫描仅在文件 mtime 变更时重入库。

**BGE 精排**：设置页打开「启用 BGE 精排」后，对混合召回结果做 CrossEncoder 重排；默认关闭（避免首启强制下载模型）。

<details>
<summary>问答示例</summary>

```json
POST /api/v1/ask
{
  "question": "卷积定理是什么？",
  "course_id": "course-default",
  "mode": "qa",
  "stream": false
}
```

知识点（定义 → 公式 → 例题）：

```json
POST /api/v1/ask
{
  "question": "卷积定理",
  "course_id": "course-default",
  "mode": "concept",
  "stream": true
}
```

章节概览（知识清单 → 重点 → 推荐自测；不走语义检索）：

```json
POST /api/v1/ask
{
  "question": "第3章 傅里叶变换",
  "course_id": "course-default",
  "mode": "chapter",
  "stream": false
}
```

```json
{
  "code": 200,
  "data": {
    "answer": "...",
    "grounded": true,
    "citations": [
      { "source_file": "chapter3.pdf", "page": 42, "snippet": "...", "score": 0.68 }
    ]
  }
}
```

`stream: true` → SSE：`phase` → `delta` → `done`（拒答则直接 `done`）。

</details>

## Status

| 阶段 | 状态 |
|:-----|:-----|
| P0 入库 / 问答 / 拒答 / WebUI | 已实现 |
| P1-A 学院·课程隔离 | 已实现 |
| P1-B `mode=concept` · 混合检索 · PPT | 已实现 |
| P2-A 离线评估 · BGE 精排 · `mode=chapter` | 已实现（精排默认关） |
| P2-B Agent / P3 平台化 | 未做 |

## Development

| 约定 | 说明 |
|:-----|:-----|
| `apis/` | 只做 HTTP |
| `services/` | 不 import FastAPI |
| `www/` | 前端源码，随仓库提交 |
| 新依赖 | `uv add <package>` |

WSL：venv 放 `~/`，别放 `/mnt/`，否则模型加载容易超时。

## Documentation

| 文档 | 内容 |
|:-----|:-----|
| [01 产品边界](docs/01-产品边界.md) | 场景与范围 |
| [02 模块架构](docs/02-模块架构.md) | 流水线与数据模型 |
| [03 工程规范](docs/03-工程规范.md) | 工具链与约定 |
| [04 后续演进](docs/04-后续演进规范.md) | 多课程、检索增强、Agent |
| [05 Web UI](docs/05-WebUI规划.md) | 工作台规格 |
