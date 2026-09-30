from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import Conflict
from app.core.response import ok
from app.core.security import get_current_user
from app.models.task import Task
from app.models.user import User
from app.schemas.synth import SynthRequest
from app.services import work_service
from app.tasks import create_task, dispatch

router = APIRouter(prefix="/works/{work_id}/synthesize", tags=["synth"])


@router.post("")
async def start_synth(
    work_id: int,
    body: SynthRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    work = await work_service.get_owned(db, work_id, user.id)
    if work.status == "synthesizing":
        raise Conflict("合成进行中，请勿重复提交")
    if idempotency_key:
        prev = (await db.execute(
            select(Task).where(Task.work_id == work_id, Task.type == "synth",
                               Task.payload_json.contains({"idempotency_key": idempotency_key}))
        )).scalar_one_or_none()
        if prev:
            return ok({"task_id": prev.id, "status": prev.status, "reuse_sample": body.scope == "sample"})
    task = await create_task(db, work_id=work_id, type="synth", payload=body.model_dump())
    work.status = "synthesizing"
    await db.commit()
    await dispatch(db, task)
    return ok({"task_id": task.id, "status": "pending", "reuse_sample": body.scope == "sample"})


@router.get("/{task_id}")
async def synth_status(work_id: int, task_id: str, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        from app.core.errors import NotFound
        raise NotFound("任务不存在")
    return ok({
        "task_id": task.id, "status": task.status, "progress": task.progress,
        "audio_url": task.result_ref, "subtitle_url": task.subtitle_ref, "failed_segments": 0,
    })
