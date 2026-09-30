from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


async def create_task(
    db: AsyncSession,
    *,
    work_id: int | None,
    type: str,
    payload: dict | None = None,
) -> Task:
    task = Task(work_id=work_id, type=type, status="pending", payload_json=payload or {})
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def dispatch(db: AsyncSession, task: Task) -> None:
    """Schedule execution. POC: in-process; production: XADD + ack in Worker."""
    from app.tasks.runner import run_task

    # mark running immediately so SSE subscribers see the start
    task.status = "running"
    task.progress = 0
    await db.commit()
    import asyncio

    asyncio.create_task(run_task(task.id))
