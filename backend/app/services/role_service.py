from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.graph import Relation
from app.models.parse import Role, Segment
from app.models.voice import Bind
from app.services import audit_service


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


async def update_role(db: AsyncSession, work_id: int, role_id: int,
                      data: dict, user_id: int | None = None) -> Role:
    """改角色名 / 级别 / 别名 / 画像，每个改动字段各写一条留痕。

    「降为龙套」就是把 level 改成 extra；龙套合成走默认旁白/群杂，
    不强制绑音色（CLAUDE.md 关键领域规则）。
    """
    role = await db.get(Role, role_id)
    if not role or role.work_id != work_id:
        raise NotFound("角色不存在")

    for field in ("name", "level", "aliases"):
        if field in data and data[field] is not None:
            old = getattr(role, field)
            new = data[field]
            if old == new:
                continue
            setattr(role, field, new)
            await audit_service.record(
                db, work_id=work_id, user_id=user_id, object_type="role",
                object_id=role_id, field=field, old_value=old, new_value=new,
                action="update", note="人工调整角色",
            )

    # 画像整体替换（profile 是 JSON，按整体记一条留痕）
    if "profile" in data and data["profile"] is not None:
        old = role.profile_json
        role.profile_json = dict(data["profile"])
        await audit_service.record(
            db, work_id=work_id, user_id=user_id, object_type="role",
            object_id=role_id, field="profile", old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps(role.profile_json, ensure_ascii=False),
            action="update", note="人工调整角色画像",
        )

    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, work_id: int, role_id: int,
                      user_id: int | None = None) -> None:
    """删除角色，同时把它名下的片段置为未归属（需要重新指派说话人）。"""
    role = await db.get(Role, role_id)
    if not role or role.work_id != work_id:
        raise NotFound("角色不存在")

    # 片段解绑：speaker_role_id 置空，保留 speaker_name 便于人工重新指派
    await db.execute(
        Segment.__table__.update()
        .where(Segment.speaker_role_id == role_id)
        .values(speaker_role_id=None)
    )
    # 同时摘掉绑定与相关的关系边，避免留下悬空引用
    await db.execute(Bind.__table__.delete().where(
        Bind.work_id == work_id, Bind.role_id == role_id))
    await db.execute(Relation.__table__.delete().where(
        Relation.work_id == work_id,
        (Relation.from_role_id == role_id) | (Relation.to_role_id == role_id),
    ))

    await audit_service.record(
        db, work_id=work_id, user_id=user_id, object_type="role",
        object_id=role_id, field="deleted", old_value=role.name, new_value=None,
        action="update", note="删除角色",
    )
    await db.delete(role)
    await db.commit()


async def split_role(db: AsyncSession, work_id: int, role_id: int, *,
                     segment_ids: list[int], new_name: str,
                     user_id: int | None = None) -> dict:
    """把指定片段从原角色拆到一个新角色上。

    典型场景：解析把两个人误判成同一角色，人工挑出其中一部分台词分给新角色。

    Returns:
        {"new_role_id", "new_role_name", "moved": 实际迁移的片段数}
    """
    role = await db.get(Role, role_id)
    if not role or role.work_id != work_id:
        raise NotFound("角色不存在")
    if not segment_ids:
        raise NotFound("请先选择要拆出的片段")
    if not new_name:
        raise NotFound("请填写新角色名")

    new_role = Role(work_id=work_id, name=new_name, level="supporting", aliases=[])
    db.add(new_role)
    await db.flush()

    moved = 0
    for sid in segment_ids:
        seg = await db.get(Segment, sid)
        if not seg or seg.speaker_role_id != role_id:
            continue
        old = seg.speaker_role_id
        seg.speaker_role_id = new_role.id
        seg.speaker_name = new_name
        await audit_service.record(
            db, work_id=work_id, user_id=user_id, object_type="segment",
            object_id=sid, field="speaker_role_id", old_value=old,
            new_value=new_role.id, action="update", note=f"从「{role.name}」拆分",
        )
        moved += 1

    await db.commit()
    await db.refresh(new_role)
    return {"new_role_id": new_role.id, "new_role_name": new_role.name, "moved": moved}


async def role_stats(db: AsyncSession, work_id: int, role_id: int) -> dict:
    """角色台词统计（§7.5）：台词数 / 覆盖章节数 / 平均句长（字符）。"""
    role = await db.get(Role, role_id)
    if not role or role.work_id != work_id:
        raise NotFound("角色不存在")

    segs = (await db.execute(
        select(Segment).where(Segment.speaker_role_id == role_id)
    )).scalars().all()
    line_count = len(segs)
    chapter_count = len({s.chapter_id for s in segs})
    avg_len = round(sum(len(s.text or "") for s in segs) / line_count, 1) if line_count else 0
    return {"line_count": line_count, "chapter_count": chapter_count, "avg_sentence_len": avg_len}


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
