from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.response import ok
from app.core.security import decode_token
from app.models.user import User
from app.services import task_service, work_service
from app.tasks import dispatch, subscribe

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _resolve_user(db: AsyncSession, request: Request) -> User:
    """POC 简化鉴权：Bearer 头或 ?token= 均可（SSE 用 query）。生产统一用 get_current_user。"""
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise Unauthorized("缺少令牌")
    try:
        uid = int(decode_token(token)["sub"])
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    except Exception:
        user = None
    if not user:
        raise Unauthorized("无效令牌")
    return user


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _resolve_user(db, request)
    task = await task_service.get_task(db, task_id)
    if task.work_id:
        await work_service.get_owned(db, task.work_id, user.id)
    return ok({
        "id": task.id, "work_id": task.work_id, "type": task.type, "status": task.status,
        "progress": task.progress, "stage": task.stage, "result_ref": task.result_ref,
        "subtitle_ref": task.subtitle_ref, "payload": task.payload_json,
    })


@router.get("")
async def list_tasks(work_id: int | None = Query(None), type: str | None = Query(None),
                    status: str | None = Query(None),
                    request: Request = None, db: AsyncSession = Depends(get_db)):
    user = await _resolve_user(db, request)
    if work_id:
        await work_service.get_owned(db, work_id, user.id)
    rows = await task_service.list_tasks(db, work_id=work_id, type=type, status=status)
    return ok({"items": [{"id": t.id, "type": t.type, "status": t.status, "progress": t.progress}
                         for t in rows], "total": len(rows), "page": 1, "page_size": 100})


@router.get("/{task_id}/stream")
async def stream(task_id: str, token: str | None = Query(None),
                request: Request = None, db: AsyncSession = Depends(get_db)):
    user = await _resolve_user(db, request)
    task = await task_service.get_task(db, task_id)
    if task.work_id:
        await work_service.get_owned(db, task.work_id, user.id)

    async def gen():
        async for payload in subscribe(task_id):
            yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{task_id}/retry")
async def retry(task_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _resolve_user(db, request)
    task = await task_service.get_task(db, task_id)
    if task.work_id:
        await work_service.get_owned(db, task.work_id, user.id)
    if task.status != "failed":
        from app.core.errors import BadRequest
        raise BadRequest("仅失败任务可重试")
    from app.models.task import Task
    task.status = "pending"
    await db.commit()
    await dispatch(db, task)
    return ok({"task_id": task.id, "status": "pending"})
