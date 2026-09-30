"""In-process task runner (POC). Mirrors the Worker contract for production."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.errors import EngineUnavailable
from app.models.task import Task
from app.tasks.progress import publish


async def run_task(task_id: str) -> None:
    async with SessionLocal() as db:
        task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
        if not task:
            return
        try:
            if task.type == "parse":
                from app.services.parse_service import run_parse

                await run_parse(db, task, publish)
            elif task.type == "synth":
                from app.services.synth_service import run_synth

                await run_synth(db, task, publish)
            elif task.type == "clone":
                # POC: clone not implemented; mark unavailable
                raise EngineUnavailable("克隆引擎未在 POC 中实现")
            else:
                raise ValueError(f"unknown task type {task.type}")

            task.status = "success"
            task.progress = 100
            task.stage = "完成"
            await db.commit()
            publish(task_id, "done", {
                "status": "success",
                "result_ref": task.result_ref,
                "subtitle_ref": task.subtitle_ref,
            })
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error = str(exc)
                await db.commit()
            publish(task_id, "error", {
                "status": "failed",
                "message": type(exc).__name__,
                "detail": str(exc),
            })
