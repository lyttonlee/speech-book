from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.models.work import Work, WORK_STATUSES


async def create_work(db: AsyncSession, owner_id: int, data: dict) -> Work:
    work = Work(owner_id=owner_id, status="draft", **data)
    db.add(work)
    await db.commit()
    await db.refresh(work)
    return work


async def get_owned(db: AsyncSession, work_id: int, owner_id: int) -> Work:
    work = (await db.execute(select(Work).where(Work.id == work_id))).scalar_one_or_none()
    if not work or work.owner_id != owner_id or work.status == "deleted":
        raise NotFound("作品不存在或无权访问")
    return work


async def update_work(db: AsyncSession, work: Work, data: dict) -> Work:
    for k, v in data.items():
        if v is not None:
            setattr(work, k, v)
    await db.commit()
    await db.refresh(work)
    return work


async def set_status(db: AsyncSession, work: Work, status: str) -> Work:
    if status not in WORK_STATUSES:
        raise BadRequest(f"非法状态: {status}")
    work.status = status
    await db.commit()
    await db.refresh(work)
    return work


async def list_works(db: AsyncSession, owner_id: int, *, status: str | None = None,
                     keyword: str | None = None, page: int = 1, page_size: int = 20):
    stmt = select(Work).where(Work.owner_id == owner_id, Work.status != "deleted")
    if status:
        stmt = stmt.where(Work.status == status)
    if keyword:
        stmt = stmt.where(Work.name.contains(keyword))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(Work.updated_at.desc())
                             .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return rows, total
