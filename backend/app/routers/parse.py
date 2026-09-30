from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import Conflict
from app.core.response import ok
from app.core.security import get_current_user
from app.engines.llm.parser import llm_enrich, parse_paragraph
from app.models.parse import Chapter, Segment
from app.models.task import Task
from app.models.user import User
from app.services import work_service
from app.tasks import create_task, dispatch

router = APIRouter(prefix="/works/{work_id}/parse", tags=["parse"])


@router.post("")
async def start_parse(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    work = await work_service.get_owned(db, work_id, user.id)
    if work.status == "parsing":
        raise Conflict("解析进行中，请勿重复提交")
    # 幂等：相同 key 返回已有任务
    if idempotency_key:
        prev = (await db.execute(
            select(Task).where(Task.work_id == work_id, Task.type == "parse",
                               Task.payload_json.contains({"idempotency_key": idempotency_key}))
        )).scalar_one_or_none()
        if prev:
            return ok({"task_id": prev.id, "status": prev.status})
    task = await create_task(db, work_id=work_id, type="parse",
                             payload={"idempotency_key": idempotency_key})
    work.status = "parsing"
    await db.commit()
    await dispatch(db, task)
    return ok({"task_id": task.id, "status": "pending"})


@router.get("/preview")
async def preview(work_id: int, chapter_id: int | None = Query(None),
                 db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    stmt = select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    if chapter_id:
        stmt = stmt.where(Chapter.id == chapter_id)
    ch = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not ch:
        return ok({"segments": []})
    out = []
    for para in [p for p in ch.text.split("\n") if p.strip()]:
        for ps in llm_enrich(parse_paragraph(para)):
            out.append({"type": ps.type, "text": ps.text, "speaker": ps.speaker_name,
                        "emotion": ps.emotion, "intensity": ps.intensity})
    return ok({"chapter": ch.title, "segments": out})


@router.get("/review-items")
async def review_items(work_id: int, type: str | None = Query(None),
                      low_conf_only: bool = Query(False),
                      db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    stmt = select(Segment).join(Chapter, Segment.chapter_id == Chapter.id).where(
        Chapter.work_id == work_id)
    segs = (await db.execute(stmt)).scalars().all()
    items = []
    for s in segs:
        if low_conf_only and not s.low_conf:
            continue
        if type and s.type != type:
            continue
        items.append({"segment_id": s.id, "type": s.type, "field": "speaker",
                      "suggestion": s.speaker_name or "未知", "confidence": s.confidence})
    return ok({"items": items})


@router.get("/segments")
async def list_segments(work_id: int, chapter_id: int | None = Query(None),
                       db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """POC 校对视图数据源：解析后的片段（类型/说话人/情绪/置信度）。"""
    from app.schemas.parse import SegmentOut
    await work_service.get_owned(db, work_id, user.id)
    stmt = select(Segment).join(Chapter, Segment.chapter_id == Chapter.id).where(
        Chapter.work_id == work_id)
    if chapter_id:
        stmt = stmt.where(Segment.chapter_id == chapter_id)
    segs = (await db.execute(stmt.order_by(Segment.chapter_id, Segment.order))).scalars().all()
    return ok({"items": [SegmentOut.model_validate(s).model_dump() for s in segs],
               "total": len(segs), "page": 1, "page_size": 1000})
