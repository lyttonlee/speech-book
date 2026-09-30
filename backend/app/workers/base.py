"""Worker 消费组骨架（生产用，POC 未启用）。

保留接口契约，确保从「进程内执行」平滑切换到「Redis Stream 独立 Worker」。
"""
from __future__ import annotations


class WorkerBase:
    queue: str = "default"
    consumer_group: str = "wg"

    async def run_once(self, payload: dict) -> None:  # pragma: no cover - 生产实现
        raise NotImplementedError

    async def loop(self) -> None:  # pragma: no cover - 生产实现
        # XREADGROUP → run_once → XACK；失败入重试/死信
        raise NotImplementedError
