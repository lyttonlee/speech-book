# speech-book-web

AI 有声书制作平台前端（POC 脚手架，pnpm 管理）。Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router。

## 技术栈

- **Vue 3** `<script setup>` + **TypeScript**
- **Vite** 5 开发/构建
- **Element Plus** 组件库 + `@element-plus/icons-vue`
- **Pinia** 状态管理（user / work store）
- **Vue Router** 路由（/login、/studio）
- **axios** 统一信封拦截器（`{ code, data, request_id }`）
- 原生 `EventSource`（SSE）订阅任务进度（`composables/useSSE.ts`）

## 包管理

本项目统一使用 **pnpm**：

```bash
pnpm install        # 安装依赖
pnpm dev            # 启动开发服务器（默认 http://localhost:5173）
pnpm build          # 产物输出到 dist/
pnpm preview        # 预览构建产物
pnpm typecheck      # vue-tsc 类型检查
```

> 注：本脚手架在 pnpm 11 下运行，`.npmrc` 与 `pnpm-workspace.yaml` 已针对沙箱做了构建脚本放行（`ignore-build-scripts` 等），请勿随意移除。

## 开发联调

`vite.config.ts` 已配置代理，开发期将前端请求转发到 FastAPI：

- `/api`  → `http://localhost:8000`（后端 API，前缀 `/api/v1`）
- `/files` → `http://localhost:8000`（音频/文件静态资源，根路径 `/files/...`）

启动后端（另开终端，`backend/` 目录）：

```bash
cd ../backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端文件 URL（`/files/...`）为**根路径相对**，由 `<audio>` 元素或浏览器直接请求，
不走 axios 的 `/api/v1` 前缀；Dev 下由 Vite 代理转发，生产由网关（nginx 等）代理。

## POC 范围说明

- 仅实现「解析 → 样章合成」最小链路的可视化：新建作品、粘贴文本、解析（旁白/对话分离、
  说话人识别、情绪推断）、样章/全本合成、SSE 进度、音频试听。
- 情绪/说话人为**规则启发式**（POC）；合成音频为 **StubTTS 可听 tone 占位**（非真实语音）。
- 鉴权为 POC 级 JWT（PBKDF2 哈希），存储为本地文件（替代 MinIO），任务为进程内执行
  （替代 Worker + Redis Stream）。生产替换点见 `backend/README.md`。

## 目录

```
src/
├── api/            # axios 封装与各模块请求
├── composables/    # useSSE（任务进度订阅）
├── router/         # 路由与登录守卫
├── stores/         # Pinia：user / work
├── types/          # 与后端 schema 对齐的类型
└── views/          # Login / Studio
```
