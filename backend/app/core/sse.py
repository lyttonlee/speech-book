"""In-memory progress hub for SSE (POC replacement for Redis pub/sub).

Production swaps this for a Redis-backed channel keyed by task_id.
"""
from __future__ import annotations

import asyncio

from app.core.errors import NotFound


class _Sub:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict] = asyncio.Queue()


class ProgressHub:
    def __init__(self) -> None:
        self._subs: dict[str, list[_Sub]] = {}
        self._latest: dict[str, dict] = {}

    def publish(self, task_id: str, event: str, data: dict) -> None:
        payload = {"event": event, "data": data}
        self._latest[task_id] = payload
        for sub in list(self._subs.get(task_id, [])):
            sub.queue.put_nowait(payload)

    def latest(self, task_id: str) -> dict | None:
        return self._latest.get(task_id)

    def subscribe(self, task_id: str):
        sub = _Sub()
        self._subs.setdefault(task_id, []).append(sub)

        async def gen():
            try:
                if task_id in self._latest:
                    yield self._latest[task_id]
                while True:
                    payload = await sub.queue.get()
                    yield payload
            finally:
                subs = self._subs.get(task_id)
                if subs and sub in subs:
                    subs.remove(sub)

        return gen()


hub = ProgressHub()
