from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.task import Task


async def get_task(db: AsyncSession, task_id: str) -> Task:
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise NotFound("任务不存在")
    return task


async def list_tasks(db: AsyncSession, *, work_id: int | None = None, type: str | None = None,
                     status: str | None = None):
    stmt = select(Task)
    if work_id is not None:
        stmt = stmt.where(Task.work_id == work_id)
    if type:
        stmt = stmt.where(Task.type == type)
    if status:
        stmt = stmt.where(Task.status == status)
    return (await db.execute(stmt.order_by(Task.created_at.desc()))).scalars().all()
