from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.parse import Role, Segment


async def list_roles(db: AsyncSession, work_id: int, *, level: str | None = None):
    stmt = select(Role).where(Role.work_id == work_id)
    if level:
        stmt = stmt.where(Role.level == level)
    roles = (await db.execute(stmt.order_by(Role.id))).scalars().all()
    # 统计台词数
    counts = (await db.execute(
        select(Segment.speaker_role_id, func.count(Segment.id))
        .where(Segment.speaker_role_id.isnot(None))
        .group_by(Segment.speaker_role_id)
    )).all()
    count_map = {rid: c for rid, c in counts}
    out = []
    for r in roles:
        d = {
            "id": r.id, "name": r.name, "level": r.level,
            "aliases": r.aliases or [], "line_count": count_map.get(r.id, 0),
        }
        out.append(d)
    return out


async def get_or_create_role(db: AsyncSession, work_id: int, name: str) -> Role:
    role = (await db.execute(
        select(Role).where(Role.work_id == work_id, Role.name == name)
    )).scalar_one_or_none()
    if role:
        return role
    role = Role(work_id=work_id, name=name, level="supporting", aliases=[])
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def merge_roles(db: AsyncSession, target_id: int, source_ids: list[int]) -> Role:
    target = await db.get(Role, target_id)
    if not target:
        raise NotFound("目标角色不存在")
    await db.execute(
        Role.__table__.update()
        .where(Role.id.in_(source_ids))
        .values(work_id=target.work_id)  # placeholder; real merge rewires segments
    )
    # 将来源角色的片段改挂到目标
    await db.execute(
        Segment.__table__.update()
        .where(Segment.speaker_role_id.in_(source_ids))
        .values(speaker_role_id=target_id)
    )
    await db.execute(
        Role.__table__.delete().where(Role.id.in_(source_ids))
    )
    await db.commit()
    return target
