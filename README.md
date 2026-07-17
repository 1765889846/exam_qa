<div align="center">

<h1>溯知</h1>
<p><code>exam-rag</code></p>
<p><strong>据源而答 · 出处可循</strong></p>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-orange?style=flat-square)](https://www.trychroma.com/)
[![uv](https://img.shields.io/badge/uv-package-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)

上传资料 · 语义检索 · 带引用作答 · 依据不足则拒答

[快速开始](#快速开始) · [架构](#架构) · [配置](#配置) · [API](#api) · [开发](#开发) · [文档](docs/)

</div>

## 这是什么

把讲义、笔记、真题放进本地资料库，用自然语言提问。答案必须能落到具体片段；检索分数不够就拒答，不硬编。

资料留在本机，按 `course_id` 隔离（见 [docs/04](docs/04-后续演进规范.md)）。

## 快速开始

需要 Python ≥ 3.11、[uv](https://docs.astral.sh/uv/)，以及 OpenAI 兼容的对话 API（`LLM_API_KEY`）。扫描版 PDF 可选 [Tesseract](https://github.com/tesseract-ocr/tesseract)（`eng` / `chi_sim`）。

```bash
cp .env.example .env   # 填写 LLM_API_KEY，或启动后在设置页注册模型
uv sync
uv run exam            # → http://127.0.0.1:8787
```

| 地址 | 用途 |
|:-----|:-----|
| [`/sz/`](http://127.0.0.1:8787/sz/) | 对话 |
| [`/sz-docs/`](http://127.0.0.1:8787/sz-docs/) | 资料上传 / 扫描 |
| [`/sz-cfg/`](http://127.0.0.1:8787/sz-cfg/) | 设置（LLM 注册与切换） |
| [`/docs`](http://127.0.0.1:8787/docs) | OpenAPI |
| [`/api/v1/health`](http://127.0.0.1:8787/api/v1/health) | 健康检查 |

前端是手写 HTML/CSS/JS（无构建），挂在 `www/`。启动时会校验配置，并扫描 `data/knowledge/` 里尚未入库的文件（默认课）。

```bash
curl http://127.0.0.1:8787/api/v1/health
uv run pytest -q
```

## 架构

请求从浏览器进 FastAPI，业务在 `services/`，持久化在 Chroma + SQLite。UI 只调 `/api/v1/*`，不写 RAG 逻辑。

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
    RET["retrieval · top_k"]
    GEN["generation"]
    EMB["embedding"]
    LLM["llm · llm_providers"]
  end

  subgraph persist["持久化"]
    CH[("Chroma<br/>向量 · course_id")]
    META[("SQLite<br/>文档元数据 · 学院/课程")]
    FILES[("data/knowledge/<br/>原始文件")]
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

两条主路径：

```mermaid
flowchart LR
  subgraph ingest["入库"]
    A1["上传 / 扫描"] --> A2["parsing"] --> A3["分块"] --> A4["embedding"] --> A5[("Chroma + SQLite")]
  end

  subgraph ask["问答"]
    B1["提问 + course_id"] --> B2["向量检索 top_k"] --> B3{"score ≥ 阈值?"}
    B3 -->|是| B4["LLM + citations"]
    B3 -->|否| B5["拒答 · grounded: false"]
  end
```

最高分低于 `score_threshold` 时返回 `grounded: false`，文案固定为「资料库中未找到相关内容」。

| 模块 | 职责 |
|:-----|:-----|
| `services/ingestion.py` | 解析 → 分块 → 向量化 → 写入 |
| `services/parsing.py` | PDF / DOCX / PPTX / TXT / MD（PDF 可选 OCR） |
| `services/retrieval.py` | 按 `course_id` 向量检索，`top_k` 后阈值过滤 |
| `services/generation.py` | 拼 prompt、调 LLM、组装引用 |
| `services/query.py` | 串联检索与生成，拒答判断 |
| `services/embedding.py` | 本地 sentence-transformers 或 OpenAI 兼容 API |
| `services/llm.py` | OpenAI 兼容对话 API |
| `services/llm_providers.py` | 模型注册表（`data/llm_providers.json`） |
| `services/storage/` | Chroma 向量 · SQLite 文档与目录 |

<details>
<summary><strong>目录结构</strong></summary>

```
exam-rag/
├── data/
│   ├── knowledge/           # 原始资料
│   └── llm_providers.json   # LLM 注册表（运行时）
├── storage/                 # Chroma · meta.db · 日志
├── src/
│   ├── main.py              # FastAPI 入口 · 挂载 www/
│   ├── config.py
│   ├── apis/v1/             # health · config · llm-providers
│   │                        # catalog · documents · ask · embedding
│   └── services/
│       ├── ingestion.py · query.py · retrieval.py · generation.py
│       ├── embedding.py · llm.py · llm_providers.py
│       └── storage/         # vector_store · doc_store · catalog_store
├── www/
│   ├── shared/              # shell · api · conversations · KaTeX
│   ├── sz/                  # 对话
│   ├── sz-docs/             # 资料
│   └── sz-cfg/              # 设置
├── docs/                    # 产品与架构说明 · assets/
└── tests/
```

</details>

<details>
<summary><strong>架构图（SVG）</strong></summary>

可再生：`uv run python scripts/gen_arch_svgs.py`

| 图 | 说明 |
|:---|:-----|
| [分层](docs/assets/architecture-layers.svg) | www → apis → services → storage |
| [浏览器与后端](docs/assets/architecture-agent.svg) | UI 只调 API |
| [流水线](docs/assets/architecture-pipelines.svg) | 入库 / 问答 + 拒答 |

![分层](docs/assets/architecture-layers.svg)

![流水线](docs/assets/architecture-pipelines.svg)

</details>

## 配置

优先级：**环境变量 > `.env` > 代码默认值**。复制 `.env.example` 后按需改；也可在 `/sz-cfg/` 写入。

| 分组 | 关键变量 |
|:-----|:---------|
| LLM | `LLM_PROVIDER`（注册表名）· `LLM_API_KEY` · `LLM_BASE_URL` · `LLM_MODEL` |
| Embedding | `EMBEDDING_PROVIDER`（`local` / `openai`）· `EMBEDDING_MODEL` |
| 存储 | `CHROMA_PATH` · `SQLITE_PATH` · `KNOWLEDGE_DIR` · `MAX_UPLOAD_MB` |
| PDF | `PDF_USE_OCR` · `PDF_FORCE_OCR` · `PDF_OCR_LANGUAGE` |
| 代理 | `PROXY_URL` · `PROXY_ENABLED` · `NO_PROXY` |

在设置页注册多个 LLM（OpenAI 兼容 / 本地 Ollama），再「设为当前」；活跃项会同步回 `.env`。

<details>
<summary><strong>检索与分块</strong>（<code>config.py</code>）</summary>

| 参数 | 默认 | 含义 |
|:-----|:-----|:-----|
| `top_k` | 5 | 每次召回的最相似片段数 |
| `score_threshold` | 0.25 | 低于此分不送 LLM，直接拒答 |
| `chunk_size` | 800 | 分块字符数 |
| `chunk_overlap` | 50 | 相邻块重叠 |

</details>

## API

统一响应：`{ "code": 200, "data": … }` 或 `{ "code": 4xx, "message": "…" }`。

| 方法 | 路径 | 说明 |
|:----:|:-----|:-----|
| `GET` | `/api/v1/health` | 连通性 |
| `GET` / `PATCH` | `/api/v1/config` | 读写配置 |
| `GET` / `POST` | `/api/v1/llm-providers` | 列出 / 注册模型 |
| `POST` | `/api/v1/llm-providers/active` | 切换当前模型 |
| `DELETE` | `/api/v1/llm-providers/{name}` | 删除注册项 |
| `POST` | `/api/v1/embedding/warmup` | 预热本地 Embedding |
| `GET` | `/api/v1/colleges` | 学院列表 |
| `GET` | `/api/v1/courses` | 课程列表（可选 `?college_id=`） |
| `POST` | `/api/v1/documents` | 上传入库（Form 必填 `course_id`） |
| `GET` | `/api/v1/documents` | 资料列表（必填 `?course_id=`） |
| `POST` | `/api/v1/documents/scan` | 扫描 `data/knowledge/`（Form 必填 `course_id`） |
| `DELETE` | `/api/v1/documents/{doc_id}` | 删除（必填 `?course_id=`，须匹配归属） |
| `POST` | `/api/v1/ask` | 问答（JSON 必填 `course_id`） |

检索与资料按 `course_id` 隔离。默认种子课为 `course-default`。同一物理文件不会跨课改归属。

<details>
<summary><strong>问答示例</strong></summary>

```json
POST /api/v1/ask
{
  "question": "卷积定理是什么？",
  "course_id": "course-default",
  "mode": "qa",
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

`stream: true` 时为 SSE：`phase` → `delta` → `done`（拒答则直接 `done`）。

</details>

支持格式：`.pdf` · `.txt` · `.md` · `.doc` · `.docx` · `.pptx`

## 现状与路线

| 阶段 | 状态 |
|:-----|:-----|
| P0 入库 / 问答 / 拒答 / WebUI | 已实现 |
| P1-A 学院·课程目录与隔离 | 已实现 |
| P1-B `mode=concept` · 混合检索 | 未做（见 [docs/01](docs/01-产品边界.md)） |
| P2 章节概览 · Reranker · 离线评估 | 未做 |

## 开发

```bash
uv run exam
DEBUG=true uv run exam
uv run pytest -q
uv run pytest -q -m integration
```

| 约定 | 说明 |
|:-----|:-----|
| `apis/` | 只做 HTTP |
| `services/` | 不 import FastAPI |
| 新依赖 | `uv add <package>` |

WSL：venv 放在 `~/` 下，不要放 `/mnt/` 挂载盘，否则模型加载容易超时。

## 文档

| 文档 | 内容 |
|:-----|:-----|
| [01 产品边界](docs/01-产品边界.md) | 场景与范围 |
| [02 模块架构](docs/02-模块架构.md) | 流水线与数据模型 |
| [03 工程规范](docs/03-工程规范.md) | 工具链与约定 |
| [04 后续演进](docs/04-后续演进规范.md) | 多课程隔离、检索增强、Agent |
| [05 Web UI](docs/05-WebUI规划.md) | 工作台规格 |

<div align="center">

<sub>

**溯知** · exam-rag · 据源而答 · 资料不上云

</sub>

</div>
