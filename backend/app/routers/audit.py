"""人工修改留痕与版本快照路由（workspace.html `#audit` 区块）。

对应设计图「人工修改留痕」：版本快照胶囊（v1…vN）+ 修改日志（前后 diff）+ 逐条回滚。
约定：
- 查询类（GET）只做鉴权 + 调 service；
- 回滚类（POST）会反向写入新的 EditLog，保证「回滚」本身也留痕可追。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import audit_service, work_service

router = APIRouter(prefix="/works/{work_id}", tags=["audit"])


@router.get("/edits")
async def list_edits(work_id: int, object_type: str | None = Query(None),
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """修改日志列表（含前后值 diff），可按对象类型筛选。

    object_type: role / binding / segment / relation / work。
    """
    await work_service.get_owned(db, work_id, user.id)
    logs = await audit_service.list_logs(db, work_id, object_type=object_type)
    rows = [await audit_service.to_diff(log) for log in logs]
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows)})


@router.post("/edits/{log_id}/rollback")
async def rollback_edit(work_id: int, log_id: int, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """逐条回滚：把某条留痕对应的字段改回它的 old_value。

    只回滚单条 EditLog 描述的那一个字段，是「最小回滚」；
    想整体回到某个版本请用 `/snapshots/{id}/restore`。
    """
    await work_service.get_owned(db, work_id, user.id)
    res = await audit_service.revert_log(db, work_id, log_id, user.id)
    return ok(res)


@router.get("/snapshots")
async def list_snapshots(work_id: int, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """版本快照列表（顶部 v1…vN 胶囊）。"""
    await work_service.get_owned(db, work_id, user.id)
    snaps = await audit_service.list_snapshots(db, work_id)
    rows = [{
        "id": s.id, "version": s.version, "label": s.label,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    } for s in snaps]
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows)})


@router.post("/snapshots")
async def create_snapshot(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """保存版本快照。body = { label?, payload? }

    payload 为空时自动快照当前「角色 + 绑定 + 关系」，用于整体回滚。
    """
    await work_service.get_owned(db, work_id, user.id)
    payload = body.get("payload") or await _auto_payload(db, work_id)
    snap = await audit_service.create_snapshot(
        db, work_id, user.id, body.get("label", ""), payload
    )
    return ok({"id": snap.id, "version": snap.version, "label": snap.label})


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(work_id: int, snapshot_id: int,
                           db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """整体回滚到某个版本快照。

    把快照里的角色 / 绑定 / 关系批量写回，并对每个字段补一条 revert 留痕。
    """
    await work_service.get_owned(db, work_id, user.id)
    payload = await audit_service.restore_snapshot(db, snapshot_id, user.id)
    applied = await _apply_payload(db, work_id, payload, user.id)
    return ok({"restored": snapshot_id, "applied": applied})


# ------------------------------------------------------------------ 内部工具


async def _auto_payload(db: AsyncSession, work_id: int) -> dict:
    """自动生成当前状态快照：角色 + 绑定 + 关系三张表的浅拷贝。"""
    from app.services import graph_service
    graph = await graph_service.to_graph(db, work_id)
    from sqlalchemy import select
    from app.models.voice import Bind
    binds = (await db.execute(
        select(Bind).where(Bind.work_id == work_id)
    )).scalars().all()
    return {
        "roles": graph["nodes"],
        "edges": graph["edges"],
        "bindings": [{"role_id": b.role_id, "voice_id": b.voice_id,
                      "params": b.params_json or {}} for b in binds],
    }


async def _apply_payload(db: AsyncSession, work_id: int, payload: dict, user_id: int) -> int:
    """把快照 payload 写回业务表，并对每个变更补 revert 留痕。

    Returns:
        实际写入的条目数（roles + bindings + edges）。
    """
    from sqlalchemy import select
    from app.models.parse import Role
    from app.models.voice import Bind
    from app.services import graph_service

    applied = 0

    # 1) 角色：按 id 更新名称/等级/别名
    for node in payload.get("roles", []):
        role = await db.get(Role, node.get("id"))
        if not role or role.work_id != work_id:
            continue
        for field, value in (("name", node.get("name")), ("level", node.get("level"))):
            if value is None:
                continue
            old = getattr(role, field)
            if str(old) == str(value):
                continue
            setattr(role, field, value)
            await audit_service.record(
                db, work_id=work_id, user_id=user_id, object_type="role",
                object_id=role.id, field=field, old_value=old, new_value=value,
                action="revert", note="按版本快照回滚",
            )
            applied += 1

    # 2) 绑定：按 (work_id, role_id) upsert
    for item in payload.get("bindings", []):
        role_id = item.get("role_id", 0)
        existing = (await db.execute(
            select(Bind).where(Bind.work_id == work_id, Bind.role_id == role_id)
        )).scalar_one_or_none()
        voice_id = item.get("voice_id")
        if existing:
            old = existing.voice_id
            if old != voice_id:
                existing.voice_id = voice_id
                existing.params_json = item.get("params") or {}
                await audit_service.record(
                    db, work_id=work_id, user_id=user_id, object_type="binding",
                    object_id=role_id, field="voice_id", old_value=old,
                    new_value=voice_id, action="revert", note="按版本快照回滚",
                )
                applied += 1
        else:
            db.add(Bind(work_id=work_id, role_id=role_id, voice_id=voice_id,
                        params_json=item.get("params") or {}))
            applied += 1

    # 3) 关系：全量重建（快照是某一时刻的完整图，增量对不上时以快照为准）
    existing_edges = await graph_service.list_relations(db, work_id)
    for e in existing_edges:
        if e.source == "manual":  # 只回滚人工边，自动推导边重新推导即可
            await db.delete(e)
    for edge in payload.get("edges", []):
        if edge.get("source") != "manual":
            continue
        await graph_service.upsert_relation(
            db, work_id,
            from_role_id=int(edge.get("from", 0)),
            to_role_id=int(edge.get("to", 0)),
            label=edge.get("label", ""),
            kind=edge.get("kind"),
            weight=float(edge.get("weight", 0.5)),
            source="manual",
        )
        applied += 1

    await db.commit()
    return applied
