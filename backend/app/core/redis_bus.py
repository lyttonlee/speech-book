"""Redis 通道（可选组件，缺失也能跑）。

两个用途：
    1) SSE 进度广播 —— 订阅端在任意副本都能收到事件，后端可横向扩容；
    2) 生产任务队列 —— dispatch 时 XADD，独立 worker 容器 XREADGROUP 消费。

设计原则：**软依赖**。Redis 连不上只告警、不抛异常，
POC（不起 Redis 容器）与完整栈（起 Redis）用同一份代码、同一批调用点。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# 进度频道统一前缀：便于运维侧 redis-cli monitor 里一眼筛出来
PROGRESS_PREFIX = "sb:progress:"

# 生产任务队列（Stream），worker 侧 XREADGROUP 消费
TASK_STREAM = "sb:tasks"


class RedisBus:
    """Redis Pub/Sub 薄封装：publish 发 JSON，subscribe 产出 dict。"""

    def __init__(self, url: str | None = None) -> None:
        import redis.asyncio as aioredis

        self.url = url or settings.redis_url
        # decode_responses=True：拿回来的是 str，省掉到处 decode
        self.client = aioredis.from_url(self.url, decode_responses=True)

    @staticmethod
    def progress_channel(task_id: str) -> str:
        return f"{PROGRESS_PREFIX}{task_id}"

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        """广播一条进度。Redis 不可用时不 upward 抛错，只记日志。"""
        try:
            await self.client.publish(channel, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis publish %s failed: %s", channel, exc)

    async def subscribe(self, channel: str):
        """订阅频道并逐条 yield 解码后的 dict；断线自动重订阅。"""
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(timeout=30.0)
                if msg and msg.get("data") and msg["data"] != 1:  # 1 = 订阅确认
                    try:
                        yield json.loads(msg["data"])
                    except json.JSONDecodeError:
                        logger.warning("redis: 非 JSON 载荷被丢弃")
                else:
                    # 30s 空闲：主动让出事件循环，顺便探测连接是否断开
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis subscribe %s ended: %s", channel, exc)
        finally:
            try:
                await pubsub.close()
            except Exception:  # noqa: BLE001
                pass

    async def enqueue(self, payload: dict[str, Any]) -> str | None:
        """任务入 Stream（生产用），返回消息 ID；Redis 不可用返回 None。"""
        try:
            msg_id = await self.client.xadd(TASK_STREAM, {"payload": json.dumps(payload, ensure_ascii=False)})
            return msg_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis xadd failed: %s", exc)
            return None

    async def close(self) -> None:
        try:
            await self.client.aclose()
        except Exception:  # noqa: BLE001
            pass


# 单例：整个进程共用一条连接，避免每个 SSE 连接各建一个池
_bus: RedisBus | None = None


def get_bus() -> RedisBus | None:
    """懒加载 Redis 客户端；不可用时返回 None（调用方走内存降级）。"""
    global _bus
    if _bus is None:
        try:
            _bus = RedisBus()
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis client init failed, fallback to memory: %s", exc)
            return None
    return _bus
