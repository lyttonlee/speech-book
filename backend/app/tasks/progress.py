"""任务进度广播：内存 Hub（POC）或 Redis Pub/Sub（完整栈）。

对外三个函数保持不变，调用点（parse/synth/runner）无需改：

    publish(task_id, event, data)  同步调用，内部按配置投递
    latest(task_id) -> dict | None
    subscribe(task_id)             异步生成器，供 SSE 路由消费

配置切换靠 ``SB_PROGRESS_BACKEND``：
    memory → 进程内 ProgressHub（默认，单副本够用）
    redis  → Redis Pub/Sub（多副本 / 重启后端也能续上进度）
"""
from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.redis_bus import get_bus
from app.core.sse import hub

logger = logging.getLogger(__name__)


def _payload(task_id: str, event: str, data: dict) -> dict:
    return {"event": event, "data": data}


def publish(task_id: str, event: str, data: dict) -> None:
    """投递一条进度事件。

    Redis 模式下用 ``loop.create_task`` 交给事件循环异步发，
    因此调用点保持原样的同步写法；没有运行中的事件循环（如单测）时退回内存 Hub。
    """
    payload = _payload(task_id, event, data)
    if settings.progress_backend != "redis":
        hub.publish(task_id, event, data)
        return

    bus = get_bus()
    if bus is None:
        hub.publish(task_id, event, data)
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 无事件循环：只能走内存
        hub.publish(task_id, event, data)
        return
    channel = bus.progress_channel(task_id)
    loop.create_task(bus.publish(channel, payload))


def latest(task_id: str) -> dict | None:
    """最近一条事件，供 SSE 连接建立时先补发，避免进度从 0 跳。"""
    if settings.progress_backend == "redis":
        bus = get_bus()
        if bus is not None:
            return _payload(task_id, "progress", {"progress": 0, "stage": "连接中"})
    return hub.latest(task_id)


async def subscribe(task_id: str):
    """订阅进度流：AsyncIterator[dict]，每个元素形如 {"event":..., "data":...}。"""
    if settings.progress_backend == "redis":
        bus = get_bus()
        if bus is not None:
            async for payload in bus.subscribe(bus.progress_channel(task_id)):
                yield payload
            return
    async for payload in hub.subscribe(task_id):
        yield payload
