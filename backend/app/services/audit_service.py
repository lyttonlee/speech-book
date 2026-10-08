"""人工修改留痕与版本快照（workspace.html `#audit` 区块的服务层）。

核心职责：
1. `record()`  —— 任何人工改动都写一条 `EditLog`，落「改前值 / 改后值 / 对象 / 操作人」；
                 这是前端修改日志 diff（<del> 红 / <ins> 绿）与逐条回滚的唯一数据源。
2. `list_logs()` —— 按作品（可选按对象/类型/时间）翻页返回留痕列表。
3. `revert_log()` —— 逐条回滚：把某个 log 记录的字段值改回 old_value。
4. `create_snapshot()` / `list_snapshots()` / `restore_snapshot()` —— 版本胶囊与整体回滚。

设计约定（DESIGN_SPEC §7b.3）：改动只记 diff，不改动原业务表里的历史值；
回滚 = 按记录把字段写回 old_value，并再写一条 action=revert 的留痕，保证链路可追。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.audit import EDIT_ACTIONS, EditLog, WorkSnapshot
from app.models.work import Work


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串（接口文档 §1.2 统一要求）。"""
    return datetime.now(timezone.utc).isoformat()


async def record(
    db: AsyncSession,
    *,
    work_id: int,
    user_id: int | None = None,
    object_type: str,
    object_id: int | None = None,
    field: str,
    old_value: object | None,
    new_value: object | None,
    action: str = "update",
    note: str | None = None,
    snapshot_id: int | None = None,
) -> EditLog:
    """写一条人工修改留痕（工作空间每次保存都会调用）。

    Args:
        work_id: 所属作品。
        user_id: 操作人（用于审计追溯）。
        object_type: role / binding / segment / relation / work。
        object_id: 被改对象主键。
        field: 被改字段名，如 emotion / voice_id。
        old_value / new_value: 前后值；非字符串统一转 str 存储，渲染 diff 时前端再解析。
        action: update=人工改 / revert=回滚 / auto=重跑覆盖。
        note: 补充说明，如「按标签自动匹配」。
        snapshot_id: 归属的版本快照。

    Returns:
        已提交到数据库的 EditLog 实例。
    """
    # 标记作品已被人工介入（工作空间流水线与留痕区块据此高亮，橙条标识）
    work = await db.get(Work, work_id)
    if work is not None:
        work.manual_adjusted = True
    log = EditLog(
        work_id=work_id,
        user_id=user_id,
        object_type=object_type,
        object_id=object_id,
        field=field,
        old_value=None if old_value is None else str(old_value),
        new_value=None if new_value is None else str(new_value),
        action=action if action in EDIT_ACTIONS else "update",
        note=note,
        snapshot_id=snapshot_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_logs(
    db: AsyncSession,
    work_id: int,
    *,
    object_type: str | None = None,
    object_id: int | None = None,
    limit: int = 50,
) -> list[EditLog]:
    """查询某作品的修改留痕（默认按时间倒序，前端修改日志倒序展示）。"""
    stmt = select(EditLog).where(EditLog.work_id == work_id)
    if object_type:
        stmt = stmt.where(EditLog.object_type == object_type)
    if object_id is not None:
        stmt = stmt.where(EditLog.object_id == object_id)
    rows = (await db.execute(stmt.order_by(EditLog.id.desc()).limit(limit))).scalars().all()
    return list(rows)


async def to_diff(log: EditLog) -> dict:
    """把一条留痕转成前端 diff 结构（workspace.html `.log-row` 用）。

    返回 {id, object_type, object_id, field, old_value, new_value, action,
          note, created_at}；`created_at` 由 TimestampMixin 自动生成后转成
    ISO 8601 字符串，前端日志行按时间正序/倒序渲染。
    """
    created = getattr(log, "created_at", None)
    return {
        "id": log.id,
        "object_type": log.object_type,
        "object_id": log.object_id,
        "field": log.field,
        "old_value": log.old_value,
        "new_value": log.new_value,
        "action": log.action,
        "note": log.note,
        "created_at": created.isoformat() if created else _now_iso(),
    }


# ---------------------------------------------------------------- 版本快照


async def revert_log(db: AsyncSession, work_id: int, log_id: int,
                     user_id: int | None = None) -> dict:
    """逐条回滚：把某条留痕描述的那一个字段改回它的 old_value。

    按 `object_type` 分发到对应业务表：
    - role      → Role.name / level / aliases
    - binding   → Bind.voice_id / params_json
    - segment   → 委托 proofread_service.revert_segment（那里串 if 更复杂）
    - relation  → Relation.label / kind / weight
    - work      → 作品级字段（目前只支持 progress / name）

    回滚完成后再写一条 action=revert 的留痕，保证「回滚」本身也可追溯。

    Returns:
        {"reverted": bool, "object_type": str, "object_id": int, "field": str}
    """
    log = await db.get(EditLog, log_id)
    if not log or log.work_id != work_id:
        raise NotFound("修改记录不存在")

    field = log.field
    old_value = log.old_value
    reverted = False

    if log.object_type == "role":
        from app.models.parse import Role
        role = await db.get(Role, log.object_id)
        if role:
            setattr(role, field, old_value)
            reverted = True

    elif log.object_type == "binding":
        from app.models.voice import Bind
        from sqlalchemy import select as _select
        bind = (await db.execute(
            _select(Bind).where(Bind.work_id == work_id, Bind.role_id == log.object_id)
        )).scalar_one_or_none()
        if bind:
            # voice_id 存的是字符串，回滚时需要转回 int（空值或非法值落到 None）
            if field == "voice_id":
                try:
                    bind.voice_id = int(old_value) if old_value not in (None, "", "None") else None
                except ValueError:
                    bind.voice_id = None
            else:
                setattr(bind, field, old_value)
            reverted = True

    elif log.object_type == "segment":
        from app.services import proofread_service
        # 片段回滚复用 proofread_service 的实现（那里会按最早留痕取 AI 原值）
        res = await proofread_service.revert_segment(
            db, work_id, log.object_id, field, user_id
        )
        reverted = bool(res.get("reverted"))

    elif log.object_type == "relation":
        from app.models.graph import Relation
        rel = await db.get(Relation, log.object_id)
        if rel:
            # weight 是浮点，其余字段按字符串写回
            if field == "weight":
                try:
                    rel.weight = float(old_value)
                except (TypeError, ValueError):
                    rel.weight = 0.5
            else:
                setattr(rel, field, old_value)
            reverted = True

    elif log.object_type == "work":
        work = await db.get(Work, log.object_id)
        if work and hasattr(work, field):
            setattr(work, field, old_value)
            reverted = True

    if reverted and log.object_type != "segment":
        # segment 分支内部已经写过分字段留痕，这里避免重复记录
        current = await _current_value(db, log)
        await record(
            db,
            work_id=work_id,
            user_id=user_id,
            object_type=log.object_type,
            object_id=log.object_id,
            field=field,
            old_value=current,
            new_value=old_value,
            action="revert",
            note=f"逐条回滚 #{log_id}",
        )

    return {"reverted": reverted, "object_type": log.object_type,
            "object_id": log.object_id, "field": field}


async def _current_value(db: AsyncSession, log: EditLog) -> object | None:
    """取某条留痕对应字段的当前值（写回滚留痕时需要它作为 old_value）。"""
    try:
        if log.object_type == "role":
            from app.models.parse import Role
            obj = await db.get(Role, log.object_id)
        elif log.object_type == "relation":
            from app.models.graph import Relation
            obj = await db.get(Relation, log.object_id)
        elif log.object_type == "work":
            obj = await db.get(Work, log.object_id)
        else:
            return None
        return getattr(obj, log.field, None) if obj else None
    except Exception:
        return None


async def create_snapshot(db: AsyncSession, work_id: int, user_id: int | None,
                          label: str, payload: dict) -> WorkSnapshot:
    """保存一个版本快照（前端顶部 v1…vN 胶囊）。

    Args:
        work_id: 作品 id。
        user_id: 操作人。
        label: 快照标题，如「绑定完成后存档」。
        payload: 快照内容，通常含 roles / bindings / relations / params 的深拷贝。

    Returns:
        新的 WorkSnapshot（version 为该作品已有快照数 +1）。
    """
    count = (await db.execute(
        select(WorkSnapshot.id).where(WorkSnapshot.work_id == work_id)
    )).scalar() or 0
    snap = WorkSnapshot(
        work_id=work_id,
        user_id=user_id,
        version=count + 1,
        label=label or f"手动存档 v{count + 1}",
        payload_json=payload or {},
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


async def list_snapshots(db: AsyncSession, work_id: int) -> list[WorkSnapshot]:
    """列出某作品的全部版本快照（按版本号升序，对应 v1…vN 胶囊）。"""
    rows = (await db.execute(
        select(WorkSnapshot)
        .where(WorkSnapshot.work_id == work_id)
        .order_by(WorkSnapshot.version)
    )).scalars().all()
    return list(rows)


async def get_snapshot(db: AsyncSession, snapshot_id: int) -> WorkSnapshot:
    """取单个版本快照，不存在抛 404。"""
    snap = await db.get(WorkSnapshot, snapshot_id)
    if not snap:
        raise NotFound("版本快照不存在")
    return snap


async def restore_snapshot(db: AsyncSession, snapshot_id: int, user_id: int | None) -> dict:
    """整体回滚到某个版本快照。

    实现策略：直接返回快照里的 payload，由调用方（router/service）负责把
    角色 / 绑定 / 关系的字段批量写回，并对每个被改字段补写一条
    action=revert 的留痕，保证「整体回滚」本身也可追溯。

    Returns:
        快照 payload 原样返回，调用方按 object_type 分发写库。
    """
    snap = await get_snapshot(db, snapshot_id)
    payload = snap.payload_json or {}
    # 为这次回滚再留一条总账，方便审计
    await record(
        db,
        work_id=snap.work_id,
        user_id=user_id,
        object_type="work",
        object_id=snap.work_id,
        field="snapshot_restore",
        old_value=f"v{snap.version}",
        new_value="restored",
        action="revert",
        note=f"整体回滚到 v{snap.version}",
        snapshot_id=snap.id,
    )
    return payload
