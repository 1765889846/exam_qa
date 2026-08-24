# AGENTS.md

> 溯知（exam-rag）· 据源而答的课程资料问答（FastAPI + Chroma + SQLite 本地 RAG）。
> 完整约束见 `docs/01-产品边界.md`、`docs/03-工程规范.md`、`docs/04-后续演进规范.md`；本文是 Codex 在本仓库工作时的强制约定。

## 项目概览

- 两条独立流水线：**入库**（上传 → 解析 → 分块 → 向量化 → 写入）与**查询**（检索 → 阈值 → 生成/拒答）。
- 前端在 `www/`（手写 HTML/CSS/JS，无构建），只调 `/api/v1/*`；RAG 逻辑全部在 `src/services/`，不进 UI。
- 多课隔离：一切检索/上传/删除都带 `course_id`。

## 技术栈（不可随意更换）

- Python ≥ 3.11、FastAPI ≥ 0.115、uvicorn ≥ 0.30、ChromaDB ≥ 0.5、SQLite（标准库）、OpenAI 兼容 LLM API。
- 依赖锁在 `uv.lock`；**只用 `uv add <package>`** 添加依赖，不手写 `pyproject.toml`、不手动改 `uv.lock`、不走 `pip install`。

## 运行与验证

```bash
uv sync
uv run exam          # 启动服务（端口读 .env 的 PORT，默认 8787）
uv run pytest -q     # 单元测试（默认跳过 integration）
uv run pytest -q -m integration   # 集成测试（需 Embedding + LLM）
```

- 修改 `www/` 静态文件后刷新即可，无构建步骤。
- 环境要求：扫描版 PDF 的 OCR 可选 Tesseract；旧版 `.doc` 转换需 LibreOffice 或本机 Word。

## 工程规范

- **配置**：优先级 环境变量 > `.env` > 代码默认值；敏感参数走环境变量，不硬编码；应用参数集中在 `src/config.py` 的 dataclass；`.env` 不入 git，改模板用 `.env.example`。
- **日志**：标准库 `logging`，模块级 `logging.getLogger(__name__)`；禁止 `print()`；级别 DEBUG/INFO/WARNING/ERROR。
- **异常**：业务异常继承 `src/exceptions.py` 的 `AppException`；外部库异常在调用处转为业务异常；禁止 `except Exception: pass`；`services` 层不捕获异常（除非转业务异常），`apis` 层不写 try/except。
- **存储**：业务代码不得直接 `chromadb.PersistentClient` 或裸 `sqlite3.connect`，必须走 `src/services/storage/` 抽象（`VectorStore` / `DocStore`）。
- **接口**：成功 `{"code": 200, "data": ...}`；失败 `{"code": HTTP, "message": ..., "detail": ...}`；用 HTTP 状态码，不自定义业务错误码；`detail` 仅 DEBUG 模式返回。
- **依赖注入**：复用组件经 `src/dependencies.py` 的 `@lru_cache()` 工厂注入，保持单例。

## 产品边界（不做的事）

- 必须实现**拒答**：检索最高分低于阈值时返回 `grounded: false`，固定文案「资料库中未找到相关内容」，禁止无引用硬编。
- 不做：用户管理/登录、多人协作、资料版本管理、在线编辑器、Agent/MCP/Skills 框架、跨会话长期记忆。
- P0 的 `services/` 主链路（ingestion → retrieval → generation）不被 Agent 或多学科重写，只做扩展。

## 测试约定

- pytest 覆盖核心链路：对话（`test_ask`）、入库（`test_ingest`）、检索隔离（`test_retrieval`）、解析（`test_parsing`）、API（`test_api`）。
- 覆盖核心链路，不镜像每个工具函数；离线 Recall@K / MRR 用 `tests/eval/run_retrieval_eval.py`，不进默认 pytest。
- 集成测试标 `@integration`。