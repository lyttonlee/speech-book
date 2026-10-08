# CLAUDE.md

本项目面向 AI 编码代理（Claude Code / WorkBuddy 等）的指引文件。改动代码前请先阅读本文件与 `docs/` 下对应文档。

## 项目简介

**有声书智能制作平台（AI Audiobook Studio）**：上传小说文本 → AI 解析（旁白/对话/心理描写分离、说话人识别、情绪分析、角色画像）→ 音色匹配 → 多角色 TTS 合成 → 导出音频 + 字幕。
首期（MVP）聚焦**音频闭环 + 情绪分析 + 自研声音克隆（合规前置）**。

## 技术栈

- **前端**：Vue 3（`<script setup>` + TypeScript）+ Vite + Element Plus + Pinia + Vue Router + 原生 `EventSource`（SSE）。包管理：**pnpm**。
- **后端**：Python 3.11+ / **FastAPI**（async，Pydantic v2）。包管理：**uv**。全栈 Python（API 服务与异步 Worker 同语言），不引入 Go/Java。
- **存储**：PostgreSQL + pgvector（向量）/ S3 兼容对象存储（默认 `versity/versitygw`，可换 MinIO）/ Redis（缓存 + Redis Stream 任务队列 + 进度）。
- **引擎适配层（Python + GPU）**：LLM 解析适配器；本地 TTS（IndexTTS / Qwen3-TTS，统一 `TTSEngine` 抽象）；自研声音克隆；内容安全审核。
- **音频处理**：ffmpeg / pydub。

## 仓库结构

```text
speech-book/
├── backend/                 # FastAPI 应用（uv 管理）
│   └── app/
│       ├── main.py          # 入口：挂载路由/SSE/静态、CORS、异常、生命周期
│       ├── core/            # config / security(JWT) / db / redis_bus / errors / sse / storage
│       ├── models/          # SQLAlchemy ORM（对应 docs/设计文档.md §6 DDL）
│       ├── schemas/         # Pydantic 请求/响应（按模块）
│       ├── routers/         # 路由层（薄：参数校验 + 调 service）
│       ├── services/        # 业务逻辑（不含 HTTP，可单测）
│       ├── workers/         # 独立进程：消费 Redis Stream（parse/synth/clone）
│       ├── engines/         # 引擎适配层（llm/tts/clone/moderation）
│       ├── tasks/           # 任务派发 + 状态机 + 进度
│       └── migrations/      # Alembic
│   ├── pyproject.toml       # uv 管理
│   └── uv.lock
├── docker-compose.yml       # 完整栈：db(pgvector) + redis + minio + backend(8000) + web(nginx:80)
├── docker-compose.poc.yml   # POC 覆盖层：中间件 scale:0，退回 SQLite/本地文件/内存进度
├── .env.example             # 部署配置模板（复制成 .env 后改口令与端口）
├── web/                     # Vue3 SPA（pnpm 管理）
│   ├── Dockerfile           # node:22-alpine 编译 → nginx:alpine 运行
│   ├── nginx.conf           # 静态 + 反代 /api、/files 到 backend
│   └── src/
│       ├── router/ stores/ api/ composables/ types/
│       ├── components/      # AppLayout / workspace/ / studio/ / voice/
│       ├── views/           # Dashboard Login Settings Studio WorkSpace VoiceLibrary
│       ├── styles/          # design.css（设计系统）/ main.css
│       └── utils/           # status.ts（状态派生）/ format.ts（时间·大小·时长）
│   ├── package.json
│   └── pnpm-lock.yaml
└── docs/                    # 需求文档 / 设计文档 / 架构设计 / 接口文档 /
                             # 功能落地对照 / 启动与部署
design/                      # 静态设计稿（HTML 原型，非运行时代码）
├── index.html               # 应用框架（侧栏 + 顶栏）
├── dashboard.html           # 工作台：多作品列表
├── workspace.html           # 单书工作空间（v0.3 核心页，前端实现的蓝本）
├── voice-library.html       # 音色库
├── settings.html / login.html / studio.html
├── assets/                  # design.css / app.js
└── DESIGN_SPEC.md           # 设计说明：IA、组件约定、人工调整留痕视觉规范
```

## 常用命令

**后端（uv）**
- 安装/同步依赖：`uv sync`
- 启动 API：`uv run uvicorn app.main:app --reload`
- 跑 Worker：`uv run python -m app.workers.parse_worker`（合成/克隆同理）
- 迁移：`uv run alembic upgrade head`
- 测试：`uv run pytest`

**前端（pnpm）**
- 安装依赖：`pnpm install`
- 开发：`pnpm dev`（Vite dev server，代理 `/api`、`/files` 到后端 8000）
- 构建：`pnpm build`（产出 `dist/`）
- 校验：`pnpm typecheck`（vue-tsc）

**Docker（完整栈，详见 docs/启动与部署.md）**
- 预拉基础镜像：应用 `python:3.11-slim` / `node:22-alpine` / `nginx:alpine`，
  基础设施 `pgvector/pgvector:pg16` / `redis:7-alpine` / `minio/minio:latest`
- 配置：`cp .env.example .env`
- 构建：`docker compose build`（在项目根目录执行）
- 启动：`docker compose up -d --build`（入口 `http://localhost`，MinIO 控制台 `:9001`）
- 轻量 POC 形态：`docker compose -f docker-compose.yml -f docker-compose.poc.yml up -d`
- 日志 / 停止：`docker compose logs -f backend` / `docker compose down`（-v 连数据卷一起删）
- 本机直跑（改代码热更新更快）：后端 `uv run uvicorn app.main:app --reload`，前端 `pnpm dev`

## API 约定（详见 docs/接口文档.md）

- 路径前缀 `/api/v1`；鉴权 `Authorization: Bearer <JWT>`；SSE 走 `?token=<JWT>`。
- 成功信封 `{ "code": "OK", "data": ..., "request_id": "..." }`；错误 `{ "code", "message", "request_id" }`。
- 列表 `?page&page_size=`，`data` 含 `items/total/page/page_size`。
- 长任务返回 `task_id`（HTTP 202），进度经 `GET /tasks/{id}/stream`（SSE）推送；提交可带 `Idempotency-Key`。
- 错误码：400 INVALID_PARAM / 401 UNAUTHORIZED / 403 FORBIDDEN / 404 *_NOT_FOUND / 409 CONFLICT / 422 CLONE_COMPLIANCE_FAILED·BANNED_PERSON·SENSITIVE_CONTENT / 429 RATE_LIMITED / 503 ENGINE_UNAVAILABLE。

## 关键领域规则

- **作品状态机**：草稿 → 文本已上传 → 解析中 → 待校对 → 校对完成 → 合成中 → 合成完成 → 导出中 → 已完成；可归档/回收站；解析中/合成中不可重复提交（409）。
- **解析**：角色词典复用，禁止每块独立新建角色；龙套（`level=extra`）走默认旁白/群杂，不强制绑音色。
- **克隆**：仅用户上传自有样本自助，**无运营审核**；前置 实名 + 授权书 + 声纹核验（本人）+ 禁公众人物关键词库 + 隐式水印。
- **合成**：情绪→参数走**引擎无关中间表示（EmotionIR）+ 能力探测降级**；样章先行 `scope=sample` 复用全本片段。
- **首期不做**：计费、版权承诺/侵权投诉、视频生成、关系图谱（M2）、团队协作（M4）、PDF 解析。

## 编码代理指引

- 路由保持"薄"：参数绑定 + 鉴权 + 调 `services`，**不要**在 router 里写 SQL 或调引擎。
- 业务逻辑放 `services/`，长任务放 `workers/`，模型推理只放 `engines/`；业务层只依赖 `TTSEngine` 等 Protocol，不要硬编码具体引擎。
- 任何 schema 变更走 **Alembic**，禁止手工改库。
- 前端 `web/src/types` 的 TS 类型要与后端 Pydantic schema 对齐。
- 改动范围较大前，先读 `docs/` 中对应文档（需求/设计/架构/接口），保持术语与状态机一致。
- 后端用 **uv**、前端用 **pnpm**；不要引入 pip/requirements.txt 或 npm/yarn。
- **单个代码文件 ≤ 500 行**（用户明确要求，指 `.py` / `.vue` / `.ts`）。超限就按「一个职责一个组件」
  拆：`views/` 只做编排，`components/` 承载展示与局部交互，跨页复用的纯逻辑放 `utils/`。
- **每个核心方法都要有中文注释**（「做什么 + 为什么」），非显而易见的参数与边界条件一并注明。

## 当前进度（POC 脚手架，已落地）

- `backend/`（uv）与 `web/`（pnpm）脚手架已按上文目录生成，均最小可跑。
- **已打通最小链路**：解析（分章→旁白/对话/心理分离→说话人识别→情绪推断→角色词典）+ 样章合成（StubTTS 生成可听 tone WAV 占位）+ SSE 进度。
- **v0.3「单书工作空间」已落地**（`design/DESIGN_SPEC.md` 的 Vue 实现）：
  - 后端：新增关系图 `Relation`、修改留痕 `EditLog`、版本快照 `Snapshot`、音频资产 `AudioAsset`/`ExportRecord` 等模型；
    新增 `graph_service` / `audit_service` / `asset_service` / `export_service` / `overview_service`；
    新增路由 `proofread` / `graph` / `audit` / `export` / `voices`（含克隆与标签）/ `roles`，以及作品 `restore`、`duplicate`；
    新增聚合接口 `GET /works/{id}/overview`（首屏一次拿回作品头 + 六段流水线 + 六项指标 + 角色与绑定 + 关系图 + 章节树 + 音频资产 + 留痕 + 快照）。
  - 前端：`views/WorkSpace.vue`（编排层，只管路由参数 / 吸顶子导航 / 区块动作编排；
    七个区块拆成 `components/workspace/` 下的 `WorkHero` `PipelineBar` `ParseOverview` `CastPanel`
    `GraphPanel` `ProofreadPanel` `AudioPanel` `AuditPanel` `ExportPanel` 九个子组件，各自 ≤ 350 行）；
    `views/Studio.vue` 按 `design/studio.html` 重做为四步向导，每一步一个
    `components/studio/Step*.vue`；音色库拆成 `components/voice/` 的 `VoiceCard` `CloneDialog` `TagDialog`；
    另有 `CastBinding.vue`、`RelationGraph.vue`、`Dashboard.vue`、`Settings.vue`；
    所有人工调整（片段改 / 关系改 / 绑定改）均写 `EditLog`，支持逐条回滚与快照整体回滚。
- **POC 占位（生产替换点，集中在 Protocol/接口后，详见 `backend/README.md` 与 `docs/功能落地对照.md` §6）**：
  - 解析 TTS：进程内 asyncio 替 Worker+Redis Stream；内存 `ProgressHub` 替 Redis Pub/Sub；
  - `StubTTSEngine` 替 IndexTTS/Qwen3-TTS；规则启发式解析 替 LLM 适配器；PBKDF2+JWT 为 POC 级鉴权。
- **完整栈基础设施已接入（`docker-compose.yml` 默认形态，非注释占位）**：
  - PostgreSQL 16 + pgvector：`SB_DATABASE_URL=postgresql+asyncpg://...@db:5432/speech_book`，
    扩展由 `backend/sql/001_extensions.sql` 在首次启动时创建；
  - 对象存储：`app/core/storage.py` 的 `MinioStorage`（签名直链下载），配置 `SB_STORAGE_BACKEND=minio`；
    **默认镜像 `versity/versitygw`**（MinIO 官方归档、`dl.min.io` 410、多数镜像源 403，
    versitygw 为 S3 协议兼容替代，改用 minio-py 标准客户端，换 `SB_MINIO_IMAGE=minio/minio:latest` 可切回）；
  - Redis：`app/core/redis_bus.py`（Pub/Sub 进度广播 + 任务 Stream `sb:tasks`），
    配置 `SB_PROGRESS_BACKEND=redis` / `SB_TASK_QUEUE_BACKEND=redis`；
  - 三者的客户端均为**软依赖**：连不上/初始化失败只告警并自动退回本地实现
    （`LocalStorage` / 内存 `ProgressHub`），POC 与完整栈共用同一份代码。
- 验证：`backend` 有 `tests/test_workspace_flow.py`（pytest 4 项通过）；本地可 `uv run uvicorn app.main:app` 起服务。
  **真实基础设施冒烟**（`scripts/smoke_infra.py`，在 backend 容器内跑）覆盖 注册→建书→导入→解析→
  合成→资产入库→音频可下载，当前 `PASS 12 / FAIL 0`；`scripts/prove_redis.py` 用 `redis-cli monitor`
  可验证进度确实走 Redis 的 `PUBLISH sb:progress:<task_id>`（而非降级到内存 Hub）。
  前端 `pnpm typecheck`（vue-tsc）零报错、`pnpm build`（vite）通过；`pnpm dev` 经 Vite 代理 `/api`、`/files` 到后端。
- 注意：文件 URL 为根路径 `/files/...`，**不经** axios 的 `/api/v1` 前缀（`<audio>` 元素直接请求，dev 下由 Vite 代理）。
- **Docker 完整栈已就位**：`docker-compose.yml` = db(pgvector) + redis + minio + backend + web/nginx；
  POC 形态用 `docker-compose.poc.yml` 覆盖（中间件 `scale: 0`，后端退回 SQLite/本地文件/内存进度）。
  基础镜像 `python:3.11-slim` / `node:22-alpine` / `nginx:alpine` / `pgvector/pgvector:pg16`
  / `redis:7-alpine` / `versity/versitygw:latest`（服务名仍叫 `minio`）；后端入口 `backend/docker-entrypoint.sh`
  会先探数据库端口再起 uvicorn。
  `cp .env.example .env && docker compose up -d --build` → `http://localhost`。
  完整镜像拉取命令、环境变量（`SB_` 前缀）、端口与排障见 **`docs/启动与部署.md`**（含 §2.1 冒烟验收）。
- **完整对照见 `docs/功能落地对照.md`**（需求 FR ⇄ 设计稿 ⇄ 代码的三向对照，含「未落地清单」）；
  v0.3 新增接口见 `docs/接口文档.md` §18。

### 本机环境注意（Windows）

`web/pnpm-workspace.yaml` 设置了 `nodeLinker: hoisted`。部分 Windows 环境**禁止创建符号链接**，
pnpm 默认 symlink 链接器会静默失败 —— `pnpm install` 显示成功但 `node_modules` 下依赖目录为空，
运行时报 `Cannot find module 'xxx'`。CI / 生产具备 symlink 权限时删掉该行即可恢复默认 `isolated`。

### 新增代码的两条硬约束

1. **核心方法必须写中文注释**：每个 service / store / 组件方法的上方用中文说明「做什么 + 为什么」，
   非显而易见的参数与边界条件一并注明（现有代码已按此执行，新增时保持一致）。
2. **路由顺序**：FastAPI 中静态路径（`/clone`、`/tags`、`/derive`、`/segments/batch`）必须注册在
   动态 `{id}` 路径之前，否则会被 id 匹配吃掉。
