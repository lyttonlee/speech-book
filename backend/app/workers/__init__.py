"""Worker进程入口（生产实现）。

POC 模式下任务在 API 进程内由 `app.tasks.runner.run_task` 以 asyncio 任务执行，
无需独立 Worker 进程。生产环境按 docs/架构设计.md §3 实现：
- base.py 提供 Redis Stream 消费组骨架（XREADGROUP + ACK + 失败重试）。
- parse_worker / synth_worker / clone_worker 各自消费对应队列。
"""
