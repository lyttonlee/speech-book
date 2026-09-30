from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.work import WorkCreate, WorkOut, WorkUpdate
from app.services import work_service
from app.core.errors import NotFound

router = APIRouter(prefix="/works", tags=["works"])


@router.get("")
async def list_works(
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await work_service.list_works(
        db, user.id, status=status, keyword=keyword, page=page, page_size=page_size
    )
    return ok({
        "items": [WorkOut.model_validate(w).model_dump() for w in rows],
        "total": total, "page": page, "page_size": page_size,
    })


@router.post("", status_code=201)
async def create(body: WorkCreate, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)):
    work = await work_service.create_work(db, user.id, body.model_dump())
    return ok(WorkOut.model_validate(work).model_dump())


@router.get("/{work_id}")
async def get(work_id: int, db: AsyncSession = Depends(get_db),
             user: User = Depends(get_current_user)):
    work = await work_service.get_owned(db, work_id, user.id)
    return ok(WorkOut.model_validate(work).model_dump())


@router.patch("/{work_id}")
async def update(work_id: int, body: WorkUpdate, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)):
    work = await work_service.get_owned(db, work_id, user.id)
    work = await work_service.update_work(db, work, body.model_dump(exclude_unset=True))
    return ok(WorkOut.model_validate(work).model_dump())


@router.delete("/{work_id}")
async def delete(work_id: int, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)):
    work = await work_service.get_owned(db, work_id, user.id)
    await work_service.set_status(db, work, "deleted")
    return ok()


@router.get("/{work_id}/stats")
async def stats(work_id: int, db: AsyncSession = Depends(get_db),
               user: User = Depends(get_current_user)):
    work = await work_service.get_owned(db, work_id, user.id)
    from sqlalchemy import func, select
    from app.models.parse import Segment, Role, Chapter
    wc = (await db.execute(select(func.sum(func.length(Chapter.text))).where(Chapter.work_id == work_id))).scalar() or 0
    rc = (await db.execute(select(func.count(Role.id)).where(Role.work_id == work_id))).scalar() or 0
    cc = (await db.execute(select(func.count(Chapter.id)).where(Chapter.work_id == work_id))).scalar() or 0
    dr = (await db.execute(select(func.count(Segment.id)).where(Segment.chapter_id.in_(
        select(Chapter.id).where(Chapter.work_id == work_id)), Segment.type == "dialogue"))).scalar() or 0
    return ok({
        "word_count": wc, "chapter_count": cc, "role_count": rc,
        "dialogue_ratio": round(dr / max(1, (await db.execute(
            select(func.count(Segment.id)).where(Segment.chapter_id.in_(
                select(Chapter.id).where(Chapter.work_id == work_id))))).scalar() or 1), 3),
        "est_duration": 0, "synthed_duration": 0,
    })


@router.get("/{work_id}/analysis")
async def analysis(work_id: int, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    from sqlalchemy import func, select
    from app.models.parse import Segment, Chapter
    rows = (await db.execute(
        select(Segment.emotion, func.count(Segment.id))
        .where(Segment.chapter_id.in_(select(Chapter.id).where(Chapter.work_id == work_id)))
        .group_by(Segment.emotion)
    )).all()
    return ok({
        "emotion_distribution": {e: c for e, c in rows},
    })
