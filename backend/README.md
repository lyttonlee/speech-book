# Speech-Book Backend (POC)

有声书智能制作平台后端 **POC 脚手架**，由 `uv` 管理。实现了「解析 + 样章合成」最小可跑链路。

## 运行

```bash
uv sync                      # 安装依赖（生成 .venv + uv.lock）
uv run uvicorn app.main:app --reload --port 8000
```

健康检查：`GET /health`。根路径提供 Swagger：`GET /docs`。

## 与《架构设计》的差异（POC 降级）

| 生产（架构设计） | POC 实现 | 原因 |
| --- | --- | --- |
| PostgreSQL + pgvector | SQLite (aiosqlite) | 本地零依赖即可跑通链路 |
| Redis Stream + Worker 进程 | 进程内 asyncio 任务 (`tasks/runner.py`) | 免去中间件，演示主链路 |
| MinIO 对象存储 | 本地文件目录 (`SB_STORAGE_DIR`) + `/files` 静态路由 | 音频直接可访问 |
| 真实 LLM / TTS 模型 | 规则解析 + `StubTTSEngine`（生成可听 tone WAV） | 离线可跑，验证抽象层 |
| 内容安全审核服务 | `engines/moderation` 透传 | 预留接口 |

生产切换点（已用 Protocol/接口隔离）：
- `engines/llm/parser.py` 的 `llm_enrich` → 接入真实 LLM 适配器。
- `engines/tts/stub.py` 的 `get_tts_engine` → 返回 IndexTTSEngine / Qwen3TTSEngine。
- `tasks/dispatch.py` 的 `dispatch` → 改为 `XADD` 入 Redis Stream。
- `core/db.py` 的 `database_url` → 切换为 PostgreSQL+pgvector 连接串。

## 目录

见 `app/` 下：`core`(config/security/db/errors/sse/storage) · `models` · `schemas` ·
`routers`(薄层) · `services`(业务) · `engines`(LLM/TTS/moderation) · `tasks`(派发/执行/进度)。

## 测试

```bash
uv run pytest
```

`tests/test_poc_flow.py` 验证：上传文本 → 解析出旁白/对话/说话人/情绪 → 角色词典 → 样章合成生成有效 WAV。
