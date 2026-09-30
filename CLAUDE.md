# CLAUDE.md

本项目面向 AI 编码代理（Claude Code / WorkBuddy 等）的指引文件。改动代码前请先阅读本文件与 `docs/` 下对应文档。

## 项目简介

**有声书智能制作平台（AI Audiobook Studio）**：上传小说文本 → AI 解析（旁白/对话/心理描写分离、说话人识别、情绪分析、角色画像）→ 音色匹配 → 多角色 TTS 合成 → 导出音频 + 字幕。
首期（MVP）聚焦**音频闭环 + 情绪分析 + 自研声音克隆（合规前置）**。

## 技术栈

- **前端**：Vue 3（`<script setup>` + TypeScript）+ Vite + Element Plus + Pinia + Vue Router + 原生 `EventSource`（SSE）。包管理：**pnpm**。
- **后端**：Python 3.11+ / **FastAPI**（async，Pydantic v2）。包管理：**uv**。全栈 Python（API 服务与异步 Worker 同语言），不引入 Go/Java。
- **存储**：PostgreSQL + pgvector（向量）/ MinIO（S3 对象存储）/ Redis（缓存 + Redis Stream 任务队列 + 进度）。
- **引擎适配层（Python + GPU）**：LLM 解析适配器；本地 TTS（IndexTTS / Qwen3-TTS，统一 `TTSEngine` 抽象）；自研声音克隆；内容安全审核。
- **音频处理**：ffmpeg / pydub。

## 仓库结构

```text
speech-book/
├── backend/                 # FastAPI 应用（uv 管理）
│   └── app/
│       ├── main.py          # 入口：挂载路由/SSE/静态、CORS、异常、生命周期
│       ├── core/            # config / security(JWT) / db / redis / errors / sse / storage
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
├── web/                     # Vue3 SPA（pnpm 管理）
│   └── src/
│       ├── router/ stores/ api/ composables/ components/ views/ types/
│   ├── package.json
│   └── pnpm-lock.yaml
└── docs/                    # 需求文档.md / 设计文档.md / 架构设计.md / 接口文档.md
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
- 开发：`pnpm dev`（Vite dev server，代理 `/api`、`/stream`）
- 构建：`pnpm build`（产出 `dist/`）
- 校验：`pnpm lint` / `pnpm typecheck`

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

## 当前进度（POC 脚手架，已落地）

- `backend/`（uv）与 `web/`（pnpm）脚手架已按上文目录生成，均最小可跑。
- **已打通最小链路**：解析（分章→旁白/对话/心理分离→说话人识别→情绪推断→角色词典）+ 样章合成（StubTTS 生成可听 tone WAV 占位）+ SSE 进度。
- **POC 占位（生产替换点，集中在 Protocol/接口后，详见 `backend/README.md`）**：
  - 存储 SQLite+aiosqlite 替 PG+pgvector；本地文件 替 MinIO；
  - 进程内 asyncio 任务 替 Worker+Redis Stream；内存 `ProgressHub` 替 Redis；
  - `StubTTSEngine` 替 IndexTTS/Qwen3-TTS；规则启发式解析 替 LLM 适配器；PBKDF2+JWT 为 POC 级鉴权。
- 验证：`backend` 有 `tests/test_poc_flow.py`（pytest 通过）；本地可 `uv run uvicorn app.main:app` 起服务。前端 `pnpm dev` 经 Vite 代理 `/api`、`/files` 到后端。
- 注意：文件 URL 为根路径 `/files/...`，**不经** axios 的 `/api/v1` 前缀（`<audio>` 元素直接请求，dev 下由 Vite 代理）。
