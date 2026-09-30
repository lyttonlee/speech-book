from __future__ import annotations

from app.core.sse import hub


def publish(task_id: str, event: str, data: dict) -> None:
    hub.publish(task_id, event, data)


def latest(task_id: str) -> dict | None:
    return hub.latest(task_id)


def subscribe(task_id: str):
    return hub.subscribe(task_id)
