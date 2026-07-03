# 05 Web UI 规划

> RAG 复习助手 · Web 工作台重构规格（填写模板）  
> **用途**：按 8 个维度定义 Web 工作台重构目标，填完后可作为实施依据。  
> **项目**：`exam-rag`  
> **关联文档**：[01-产品边界](./01-产品边界.md) · [02-模块架构](./02-模块架构.md) · [03-工程规范](./03-工程规范.md) · [04-后续演进规范](./04-后续演进规范.md)  
> **现状快照**（2026-07）：前端为 `web/index.html` 单文件（原生 JS + 内联 CSS）；后端 FastAPI 挂载 `web/`；API 无前缀版本（`/health`、`/documents`、`/ask`）；资料目录已迁至 `data/knowledge/`。  
> **目标栈**：**React 18 + Vite 7**；构建产物输出 `www/`，由 FastAPI 同端口挂载。

**填写说明**：将 `[待填写]` 替换为你的决策；保留 `（可选）` 段落可删；勾选框用 `[x]` / `[ ]`。

---

## 1. 视觉风格（整体设计基调）

### 1.1 品牌定位

| 项 | 填写 |
|---|---|
| 产品气质关键词（3–5 个） | `专注复习、学术克制、开发者工具感` 例：学术克制 / 复习专注 / 可信引用 / 暗色护眼 |
| 参考产品或站点（附链接） | `GitHub Dark、Notion 暗色、Linear` 例：当前 `web/index.html` 的 GitHub 暗色基调 |
| 明确不要的风格 | `花哨 AI 紫渐变、过度玻璃拟态、营销落地页风` |

### 1.2 视觉语言

| 项 | 填写 |
|---|---|
| 主色 / 强调色 | `#58a6ff`（现状链接色）是否保留？拒答/警告用 `#f85149`，成功/有据用 `#3fb950` |
| 明暗模式策略 | `[x]` 保留双主题 `[ ]` 仅暗色（P0） `[ ]` 仅亮色 `[ ]` 跟随系统 |
| 圆角尺度（sm / md / lg） | `6 / 8 / 12px`（对齐现状 `.upload-zone`、`.answer-box`） |
| 阴影与层次 | `轻量边框分层为主，少量 elevation` 当前几乎无阴影 |
| 动效原则 | `CSS transition 为主`；P1 可选 GSAP 微交互；`prefers-reduced-motion` 强制降级 |

### 1.3 页面级差异

| 页面 | 与工作台关系 | 填写 |
|---|---|---|
| `/` 工作台首页 | 默认进入问答 Tab | 双栏：左资料库 + 右问答（延续现状布局） |
| `/documents`（或 Tab） | 资料管理 | 上传区 + 文档列表 + 扫描 `data/knowledge/` |
| `/ask`（或 Tab） | 核心问答 | 输入框 + 回答区 + citations 折叠 + KaTeX 渲染 |
| `/settings`（或 Tab） | 只读配置展示 | 展示 LLM 模型名、chunk 参数、检索阈值（敏感项脱敏） |
| P1-A 选课 | 顶栏课程切换 | `college → course` 级联选择，始终展示当前课程名 |

### 1.4 关键界面截图或草图（可选）

```
[待填写：粘贴链接或附件路径]
- 双栏布局（资料库 + 问答）
- citations 展开态（含 snippet + score）
- grounded: false 拒答态
- P1-A 顶栏选课
```

---

## 2. 技术方案（核心架构选型）

### 2.1 基础栈（勾选确认）

- [x] **采用** React 18 + Vite 7 单入口 SPA（`workbench/` 源码目录）
- [x] **构建输出** `www/`，`base: '/'`（FastAPI 根路径挂载，同端口部署）
- [x] **引入** TypeScript（迁移策略：`渐进` — 新代码 `.tsx`，工具层先 `.ts`）
- [x] **引入** 路由库（`React Router 7`）— 页面：`/` 工作台、`/settings`；Tab 可用 `?tab=` 或路由子路径
- [ ] **引入** 全局状态（`[待填写]` Zustand / Context only）— 候选：当前 `course_id`（P1-A）、主题
- [ ] **引入** 数据请求层（`[待填写]` 保留 `fetch` 封装 / 加 TanStack Query）

**与 03-工程规范 的差异说明**：规范文档写 Next.js，本工作台明确改为 **Vite 7 静态构建**，理由：单页工作台无需 SSR；与 FastAPI 同端口挂载更简单；构建链更轻。

### 2.2 与后端集成约定

| 项 | 填写 |
|---|---|
| API 基址 | 同端口：`/api/v1`（**目标**）；现状无前缀 `/health` 等，重构时后端一并迁移 |
| 鉴权方式 | MVP 无鉴权（`get_current_user()` 返回 None）；不实现登录页 |
| 响应格式 | 统一 `{code, data}` / `{code, message}`，见 [03-工程规范](./03-工程规范.md) §3.5 |
| 健康检查 | `GET /api/v1/health` → 顶栏状态点（healthy / degraded） |
| 资料 API | `POST/GET/DELETE /api/v1/documents`、`POST /api/v1/documents/scan` |
| 问答 API | `POST /api/v1/ask`，body `{question, mode}`；P1-A 增 `course_id` |
| 配置 API（可选） | `GET /api/v1/config` — 返回非敏感配置供设置页展示 |
| 类型来源 | `手写 types`（P0）；后续可从 `/docs` OpenAPI 生成 |
| KaTeX | 保留 `public/katex/` 或 npm 引入，回答区渲染 LaTeX |

### 2.3 构建与发布

| 项 | 填写 |
|---|---|
| 包管理器 | pnpm（项目根 `package.json` + `pnpm-workspace.yaml`） |
| 源码目录 | `workbench/`（Vite 项目根） |
| 开发命令 | `pnpm dev` → Vite 代理 `/api` 到 `http://127.0.0.1:8000` |
| 生产构建 | `pnpm build` → `www/`；`uv run exam` 挂载 `www/` |
| 旧 `web/` 处理 | 迁移完成后删除或保留为 `web-legacy/` 参考 |
| CI 检查项 | `lint` / `typecheck` / `build` |

**目标启动流程**（对齐 [03-工程规范](./03-工程规范.md) §3.10）：

```bash
pnpm install
pnpm build          # workbench → www/
uv run exam         # FastAPI 挂载 www/，默认 :8000
```

### 2.4 非目标（明确不做）

```
- 不引入 Next.js / SSR
- 不做用户注册登录（见 01 §1.3）
- 不做 Agent/MCP
- 前端不写 RAG 逻辑，仅调 API
- 不拆独立前端仓库
```

---

## 3. UI 组件库（标准化组件选型）

### 3.1 组件库决策

| 方案 | 选择 | 说明 |
|---|---|---|
| 引入完整组件库 | `[Ant Design 5]` | 推荐 **Ant Design 5**（表单/上传/表格成熟）或 **shadcn/ui**（） |

**最终选择**：`[Ant Design 5]`  
**约束**：只选一套；业务 Panel 不得混用两套 UI 库。

### 3.2 组件分层定义

| 层级 | 职责 | 命名前缀（建议） | 示例 |
|---|---|---|---|
| Primitives | 按钮、输入、标签、开关 | `Ui` | Button、Input、Tag |
| Patterns | 上传区、空状态、加载、Toast | `Pattern` | UploadZone、CitationList |
| Features | 业务面板 | 按 feature 目录 | `AskPanel`、`DocumentsPanel` |
| Shell | 顶栏、侧栏、布局 | `Shell` | `AppLayout`、`HealthBadge` |

### 3.3 必要组件清单（勾选需要的）

**表单与反馈**
- [x] Button（primary / ghost / danger）
- [x] Input / Textarea
- [ ] Select（P1-A 选课）
- [ ] Switch / Checkbox（settings 页）
- [x] Upload（拖拽 + 点击，PDF/TXT/MD）
- [x] Toast / InlineAlert
- [x] Spinner / Skeleton（问答 loading）

**数据展示**
- [x] DocumentList（文件名、chunk_count、status、删除）
- [x] AnswerCard（answer + grounded 标签）
- [x] CitationList（source_file、score、snippet 折叠）
- [ ] CodeBlock（debug 模式，可选）

**导航**
- [x] 顶栏 HealthBadge + 课程名（P1-A）
- [ ] Tabs 或侧栏（ask / documents / settings）
- [ ] Breadcrumb（`[待填写]` 是否需要）

**问答专用**
- [x] AskComposer（输入 + 提交 + Enter 快捷键）
- [x] AnswerView（KaTeX `renderMathInElement` 封装为 hook）
- [x] GroundedBadge（✅ 有据可查 / ⚠️ 无引用依据）
- [ ] ModeSelector（qa / concept / chapter，P1 起）

### 3.4 装饰性组件去留

| 现状 | 去留 | 理由 |
|---|---|---|
| 内联 CSS（`web/index.html`） | 迁移后删除 | 拆到 `styles/` + 组件库 |
| KaTeX 静态资源 | 保留 | 公式渲染刚需 |
| 粒子/营销动画 | 不做 | 与复习工具气质不符 |

---

## 4. 目录结构（工程目录规范）

### 4.1 目标仓库布局（exam-rag 根目录）

```
exam-rag/
├── data/                          # gitignore；留给后续应用级配置
│   └── knowledge/                 # ★ 入库原始资料（PDF/TXT/MD）
├── storage/                       # Chroma + SQLite（或 ~/.exam-rag/）
├── workbench/                     # ★ Vite 7 + React 18 源码
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   ├── public/
│   │   └── katex/                 # 从 web/katex 迁入
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── WorkbenchPage.tsx  # 主工作台（双栏）
│       │   └── SettingsPage.tsx
│       ├── features/
│       │   ├── ask/               # 问答
│       │   ├── documents/         # 资料库
│       │   ├── health/            # 健康状态
│       │   └── catalog/           # P1-A：学院/课程选择
│       ├── components/
│       │   ├── ui/
│       │   └── shell/
│       ├── lib/
│       │   ├── api/               # apiClient、类型
│       │   └── katex/             # useKatexRender
│       └── styles/
│           ├── tokens.css
│           └── global.css
├── www/                           # pnpm build 输出，FastAPI 挂载
├── web/                           # 现状单页（迁移后废弃）
├── src/                           # FastAPI 后端（见 02-模块架构）
│   ├── main.py
│   ├── config.py                  # knowledge_dir 等
│   ├── apis/v1/                   # 目标：版本化路由
│   └── services/
├── tests/
├── pyproject.toml
└── package.json                   # workspace 根
```

### 4.2 文件迁移对照表（必填）

| 现有文件 | 目标路径 | 备注 |
|---|---|---|
| `web/index.html`（整体 UI） | 拆为 `workbench/src/features/*` | 逻辑按 feature 切分 |
| `web/index.html`（样式） | `workbench/src/styles/global.css` + tokens | 去掉内联 `<style>` |
| `web/index.html`（`checkHealth`） | `features/health/useHealth.ts` | |
| `web/index.html`（`loadDocs/upload/delete/scan`） | `features/documents/*` | |
| `web/index.html`（`askQuestion`） | `features/ask/AskPanel.tsx` | 含 KaTeX |
| `web/katex/*` | `workbench/public/katex/` | 静态资源 |
| `src/main.py` 挂载 `web/` | 改挂载 `www/` | 配合 `src/web_static.py`（可选） |

### 4.3 命名与导入规范

| 规则 | 填写 |
|---|---|
| 组件文件 | `PascalCase.tsx` |
| hooks | `useXxx.ts` |
| API 模块 | `lib/api/client.ts`、`lib/api/types.ts` |
| 路径别名 | `@/` → `src/`（vite.config `resolve.alias`） |
| barrel export | `[ ]` 每个 feature 用 index.ts `[x]` 禁止 barrel（减少循环依赖） |

---

## 5. 模块边界（功能解耦定义）

### 5.1 垂直切片（Feature 边界）

每个 feature 对外只暴露 **入口 Panel/Hook**；禁止 feature 间直接 import 内部子组件。

| Feature ID | 入口组件 | 独占状态/API | 可依赖的共享模块 |
|---|---|---|---|
| `health` | `HealthBadge` | `GET /api/v1/health` | `lib/api` |
| `documents` | `DocumentsPanel` | 上传、列表、删除、扫描 | `lib/api`, `components/ui` |
| `ask` | `AskPanel` | 问答请求、回答展示 | `lib/api`, `lib/katex` |
| `settings` | `SettingsPanel` | `GET /api/v1/config`（待实现） | `lib/api` |
| `catalog`（P1-A） | `CoursePicker` | `GET /colleges`、`GET /courses` | `lib/api`、全局 context |

### 5.2 壳（App Shell）职责边界

**壳负责：**
- [x] 顶栏：产品名 + HealthBadge +（P1-A）当前课程
- [x] 主布局：左资料 / 右问答（或 Tab 切换）
- [x] 全局 Toast
- [ ] 路由：`/`、`/settings`

**壳不负责：**
```
- 不内联 fetch 业务逻辑（下沉到 features）
- 不直接操作 DOM 渲染 KaTeX（用 hook）
- 不做 RAG 检索/生成
```

### 5.3 跨模块共享数据

| 数据 | 来源 | 共享方式 | 填写 |
|---|---|---|---|
| 健康状态 | `/api/v1/health` | Shell 轮询或 React Query | `[待填写]` |
| 文档列表 | `/api/v1/documents` | documents feature 自有 state；删除后 ask 无需刷新 | |
| `course_id`（P1-A） | 用户选择 | Context / Zustand | `[待填写]` |
| API 基址 | 环境变量 `VITE_API_BASE` | `import.meta.env` | 默认 `/api/v1` |

### 5.4 与后端的契约文档

| Feature | 端点 | 阶段 |
|---|---|---|
| health | `GET /api/v1/health` | P0 |
| documents | `POST/GET /api/v1/documents` | P0 |
| documents | `DELETE /api/v1/documents/{id}` | P0 |
| documents | `POST /api/v1/documents/scan` | P0 |
| ask | `POST /api/v1/ask` | P0 |
| catalog | `GET /api/v1/colleges`、`GET /api/v1/courses` | P1-A |
| config | `GET /api/v1/config` | P0 可选 |

完整响应格式见 [02-模块架构](./02-模块架构.md) §2.7、[03-工程规范](./03-工程规范.md) §3.5。

---

## 6. 复用规则（组件公用逻辑）

### 6.1 API 客户端统一模式

| 抽象项 | 是否提取 | 命名建议 |
|---|---|---|
| `apiClient.get/post/delete` | 是 | `lib/api/client.ts` |
| 统一解析 `{code, data}` | 是 | `unwrapResponse()` |
| 错误 Toast | 是 | `lib/api/errors.ts` |

### 6.2 列表类复用

```
DocumentList 与 P1-A 课程列表可共用 List + Empty 模式组件
```

### 6.3 问答模块复用

| 模块 | 复用范围 | 填写 |
|---|---|---|
| `useAsk` | ask feature | 封装 loading/error/result |
| `useKatex` | 任何展示 LLM 输出的区域 | 封装 `renderMathInElement` |
| `CitationItem` | ask + 未来 concept 模式 | |

### 6.4 Hooks 提取规则

**何时提取 hook：**
```
- 同一逻辑在 2+ 组件出现
- 涉及副作用（轮询 health、提交问答）
```

**禁止：**
```
- feature 专属 hook 不要放到 global hooks 除非 2+ feature 使用
```

### 6.5 文案与 i18n

| 项 | 填写 |
|---|---|
| 文案 | P0 继续组件内中文硬编码 |
| 拒答文案 | 与后端 `grounded: false` 固定语一致 |
| 产品名 | 「RAG 复习助手」；课程名 P0 写死「信号与系统」，P1-A 动态 |

---

## 7. 样式系统（全局视觉规范）

### 7.1 Design Tokens（CSS 变量）

> 从现状 `web/index.html` 内联样式抽离到 `workbench/src/styles/tokens.css`。

| Token 组 | 变量示例 | 现状值 | 是否调整 |
|---|---|---|---|
| 颜色-背景 | `--bg-primary` | `#0d1117` | 保留 |
| 颜色-表面 | `--bg-surface` | `#161b22` | 保留 |
| 颜色-边框 | `--border-default` | `#30363d` | 保留 |
| 颜色-强调 | `--accent` | `#58a6ff` | 保留 |
| 颜色-成功 | `--success` | `#3fb950` | 保留 |
| 颜色-危险 | `--danger` | `#f85149` | 保留 |
| 颜色-次要文字 | `--text-muted` | `#8b949e` | 保留 |
| 圆角 | `--radius-sm/md/lg` | `6/8/12px` | 保留 |
| 布局 | `--panel-left-width` | `360px` | 可调 |

### 7.2 主题实现

| 项 | 填写 |
|---|---|
| P0 策略 | 仅暗色，不实现切换 |
| 组件库主题 | 覆盖 Ant Design / shadcn token 映射到 `--accent` 等 |
| 硬编码色 | 禁止新增 hex，仅允许 `var(--*)` |

### 7.3 CSS 组织策略

- [ ] **方案 A**：Tailwind CSS
- [x] **方案 B**：纯 CSS + CSS 变量 + BEM `exam-*`（推荐，与现状接近）
- [ ] **方案 C**：CSS Modules per component

**选择**：方案 B（可按 feature 拆 `styles/features/ask.css` 等）

### 7.4 响应式与无障碍

| 断点 | 行为 | 填写 |
|---|---|---|
| `≤768px` | 双栏改上下堆叠 | `[待填写]` |
| reduced-motion | 关闭动画 | `prefers-reduced-motion: reduce` |
| 焦点环 | 输入框 `:focus` 边框高亮 | 已有，保留 |
| 键盘 | Enter 提交问题 | 已有，保留 |

---

## 8. 实施计划（开发迭代排期）

### 8.1 里程碑

| 阶段 | 目标 | 产出 | 预估 | 完成标准 |
|---|---|---|---|---|
| **P0-0 路径** | 资料目录迁至 `data/knowledge/` | config + 后端扫描/上传 | 已完成 | 启动自动入库 knowledge 下文件 |
| **P0-1 脚手架** | Vite 7 + React 18 初始化 | `workbench/`、代理、别名 | `[待填写]` | `pnpm build` 输出 `www/` |
| **P0-2 后端对齐** | API 加 `/api/v1` 前缀 | `apis/router.py` 聚合 | `[待填写]` | 前端 `VITE_API_BASE=/api/v1` 联调通 |
| **P0-3 壳 + health** | 布局 + 顶栏状态 | `AppLayout`、`HealthBadge` | `[待填写]` | 健康检查展示正常 |
| **P0-4 documents** | 资料库 feature | 上传/列表/删除/扫描 | `[待填写]` | 与现状 `web/index.html` 功能对等 |
| **P0-5 ask** | 问答 feature | AskPanel + KaTeX + citations | `[待填写]` | 问答 + 拒答 + 公式渲染 |
| **P0-6 切换挂载** | FastAPI 挂 `www/` | 删/归档 `web/` | `[待填写]` | `uv run exam` 打开新 UI |
| **P1-A** | 选课 UI | `CoursePicker` + `course_id` | 见 04 §4.2 | 跨课不串答 |

### 8.2 迁移策略

- [x] **绞杀者**：`workbench/` 并行开发，完成后切换 `www/` 挂载，废弃 `web/index.html`
- [ ] **大爆炸**：一次性替换（不推荐）

### 8.3 每阶段验证清单

```bash
# 前端构建
cd workbench && pnpm build

# 后端
uv run pytest -q                    # 单元测试
uv run pytest -m integration -q     # 集成（需 API Key）

# 联调
uv run exam
# 浏览器：/ → 健康绿点 → 上传 MD → 提问 → 查看 citations
# 确认 data/knowledge/ 下文件可被 scan 入库
```

**人工回归重点：**
```
- [ ] GET /api/v1/health 状态展示
- [ ] 上传 PDF/TXT/MD 到 data/knowledge/ 并入库
- [ ] POST /api/v1/ask 流式/非流式回答 + grounded 标签
- [ ] citations 展开 + KaTeX 公式
- [ ] 删除文档后向量同步清除
- [ ] 检索低分拒答（grounded: false）
```

### 8.4 风险与回滚

| 风险 | 缓解 | 填写 |
|---|---|---|
| API 前缀迁移破坏旧前端 | 后端短期双挂载或保留旧路由别名 | `[待填写]` |
| KaTeX 在 React 中重复渲染 | `useEffect` + 容器 ref，依赖 answer 文本 | |
| `data/knowledge/` 与旧 `data/` 路径不一致 | 已集中 `config.storage.knowledge_dir` | 已完成 |
| 构建产物 404 | 确认 `www/index.html` + FastAPI `html=True` | |

**回滚策略**：保留 `web/index.html` 直至 P0-6 验收通过；`www/` 可 git tag 上一版。

### 8.5 分工（可选）

| 负责人 | 范围 |
|---|---|
| `[待填写]` | 视觉 + tokens |
| `[待填写]` | workbench 脚手架 + Shell |
| `[待填写]` | ask + documents feature |
| `[待填写]` | 后端 `/api/v1` 迁移 |

---

## 附录 A：现状 API 与目标对照

| 现状路径 | 目标路径 | 说明 |
|---|---|---|
| `GET /health` | `GET /api/v1/health` | 待后端迁移 |
| `GET /documents` | `GET /api/v1/documents` | |
| `POST /documents` | `POST /api/v1/documents` | 文件存 `data/knowledge/` |
| `POST /documents/scan` | `POST /api/v1/documents/scan` | 扫描 knowledge 目录 |
| `DELETE /documents/{id}` | `DELETE /api/v1/documents/{id}` | |
| `POST /ask` | `POST /api/v1/ask` | body: `{question, mode}` |

## 附录 B：资料目录约定

```
data/                    # 应用数据根（gitignore）
├── knowledge/           # ★ 入库资料（PDF/TXT/MD），扫描与上传均指向此处
│   └── *.md / *.pdf …
└── (预留)               # 后续应用配置、缓存等，避免与 knowledge 混放
```

环境变量：`KNOWLEDGE_DIR=data/knowledge`（见 `src/config.py` `StorageConfig.knowledge_dir`）。

## 附录 C：填写优先级建议

1. **先填 §1 视觉 + §7 样式** — 确定暗色 token 与组件库  
2. **再填 §4 目录 + §5 模块边界** — 确定 workbench 怎么拆  
3. **然后 §3 组件库 + §6 复用规则** — 确定抽象深度  
4. **最后 §2 技术方案 + §8 排期** — 锁定 Vite 构建与 API 迁移顺序  

---

*文档版本：1.0 · exam-rag 专版 · 2026-07*
