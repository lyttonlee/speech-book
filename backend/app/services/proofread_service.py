"""校对工作台服务（workspace.html 已解析章节 + 待复核队列）。

对应接口文档 §13 与 DESIGN_SPEC §5.3b「片段行」：
- 片段行支持改文本 / 改说话人 / 改情绪强度 / 改类型归属 / 重合成单段 / 删除；
- 前端视觉编码：橙左边框 = 人工改过，红左边框 = 低置信待复核；
- 前端每次操作即时 `PATCH`，后端幂等写字段 + 写留痕（FR-808）。

本模块统一处理「改字段 → 落库 → 写 EditLog」，避免各处重复埋点。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.parse import Chapter, Role, Segment
from app.models.voice import Voice
from app.schemas.parse import SegmentOut
from app.services import audit_service

# 允许人工单独修改的片段字段白名单（避免把 id/chapter_id 等结构字段开放成可改）
PATCHABLE_FIELDS = {
    "type",            # narration / dialogue / psychology
    "text",            # 片段正文（人工改稿）
    "speaker_role_id", # 说话人归属
    "speaker_name",    # 说话人显示名（未建角色时的临时名）
    "emotion",         # 情绪
    "intensity",       # 情绪强度 0~100
    "confidence",      # 置信度（人工确认低置信片段）
}

# 片段字段 → 中文名（前端修改日志里显示「情绪强度」而不是 intensity）
FIELD_LABELS = {
    "type": "类型",
    "text": "正文",
    "speaker_role_id": "说话人",
    "speaker_name": "说话人名",
    "emotion": "情绪",
    "intensity": "情绪强度",
    "confidence": "置信度",
}


async def get_segment(db: AsyncSession, segment_id: int) -> Segment:
    """取片段，不存在抛 404。"""
    seg = await db.get(Segment, segment_id)
    if not seg:
        raise NotFound("片段不存在")
    return seg


async def proofread_board(db: AsyncSession, work_id: int, chapter_id: int | None = None) -> dict:
    """三栏校对数据（接口文档 §13.1）。

    返回：
    {
      "chapter": {id, title, order} | null,
      "paragraphs": [{id, order, text, segments: [SegmentOut]}],
      "roles": [{id, name, level}],
      "voices": [{id, name}]
    }
    `chapter_id` 为空时取该书第一章，供前端首屏直接渲染。
    """
    stmt = select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    if chapter_id:
        stmt = stmt.where(Chapter.id == chapter_id)
    ch = (await db.execute(stmt.limit(1))).scalar_one_or_none()

    if not ch:
        return {"chapter": None, "paragraphs": [], "roles": [], "voices": []}

    segs = (await db.execute(
        select(Segment)
        .where(Segment.chapter_id == ch.id)
        .order_by(Segment.order)
    )).scalars().all()

    roles = (await db.execute(
        select(Role).where(Role.work_id == work_id).order_by(Role.id)
    )).scalars().all()
    voices = (await db.execute(
        select(Voice).where(Voice.status == "available").order_by(Voice.id)
    )).scalars().all()

    return {
        "chapter": {"id": ch.id, "title": ch.title, "order": ch.order},
        "paragraphs": [{
            "id": s.id,
            "order": s.order,
            "text": s.text,
            "segments": [SegmentOut.model_validate(s).model_dump()],
        } for s in segs],
        "roles": [{"id": r.id, "name": r.name, "level": r.level} for r in roles],
        "voices": [{"id": v.id, "name": v.name} for v in voices],
    }


async def patch_segment(
    db: AsyncSession,
    work_id: int,
    segment_id: int,
    patch: dict,
    user_id: int | None = None,
) -> dict:
    """修改单个片段字段并写留痕（接口文档 §13.2）。

    只处理白名单字段；每个实际变化的字段各写一条 EditLog，
    前端修改日志因此能按字段颗粒度展示 diff 并支持逐条回滚。

    Returns:
        {"segment": SegmentOut 序列化结果, "changes": 实际改动的字段数}
    """
    seg = await get_segment(db, segment_id)
    # 简单归属校验：片段必须属于当前作品（防越权改别人的书）
    chapter = await db.get(Chapter, seg.chapter_id)
    if not chapter or chapter.work_id != work_id:
        raise NotFound("片段不存在")

    changes = 0
    for field, value in (patch or {}).items():
        if field not in PATCHABLE_FIELDS:
            continue
        old = getattr(seg, field, None)
        if old == value:
            continue  # 幂等：值没变不写日志
        # 同步 speaker_name：人工改说话人角色时把显示名一起带上，前端片段卡直接显示
        if field == "speaker_role_id" and value:
            role = await db.get(Role, value)
            if role:
                seg.speaker_name = role.name
        setattr(seg, field, value)
        await audit_service.record(
            db,
            work_id=work_id,
            user_id=user_id,
            object_type="segment",
            object_id=segment_id,
            field=field,
            old_value=old,
            new_value=value,
            action="update",
            note=f"改{FIELD_LABELS.get(field, field)}",
        )
        changes += 1

    if changes:
        # 人工改过后重新判定低置信红条：置信度被人工抬升则摘掉红条
        try:
            seg.low_conf = bool(float(seg.confidence) < 0.7)
        except (TypeError, ValueError):
            seg.low_conf = False
        await db.commit()
        await db.refresh(seg)

    return {"segment": SegmentOut.model_validate(seg).model_dump(), "changes": changes}


async def batch_patch_segments(
    db: AsyncSession,
    work_id: int,
    ids: list[int],
    patch: dict,
    user_id: int | None = None,
) -> dict:
    """批量修改多个片段（接口文档 §13.3，前端「批量操作栏」用）。

    逐个调用 `patch_segment`，任一片段失败不影响其余片段（逐条独立写留痕）。

    Returns:
        {"applied": 成功条数, "total": 请求条数, "failed": 失败 id 列表}
    """
    applied = 0
    failed: list[int] = []
    for sid in ids or []:
        try:
            await patch_segment(db, work_id, sid, patch, user_id)
            applied += 1
        except Exception:
            failed.append(sid)
    return {"applied": applied, "total": len(ids or []), "failed": failed}


async def revert_segment(
    db: AsyncSession,
    work_id: int,
    segment_id: int,
    field: str = "all",
    user_id: int | None = None,
) -> dict:
    """把片段字段回滚到「人工改之前」的值（AI 原值还原）。

    实现：从该片段最近的 EditLog 里取出每个字段的 old_value（最早一条即 AI 原值），
    写回 Segment，并补一条 action=revert 的留痕，保证回滚本身也被记录。

    Args:
        work_id: 作品 id（用于归属校验与留痕）。
        segment_id: 片段 id。
        field: 指定回滚哪个字段；"all" 表示回滚该片段的全部已改字段。
        user_id: 操作人。

    Returns:
        {"segment": 回滚后的片段, "reverted": 实际回滚的字段列表}
    """
    seg = await get_segment(db, segment_id)
    chapter = await db.get(Chapter, seg.chapter_id)
    if not chapter or chapter.work_id != work_id:
        raise NotFound("片段不存在")

    logs = await audit_service.list_logs(
        db, work_id, object_type="segment", object_id=segment_id
    )
    # list_logs 是倒序（最新在前），反转后最早一条即为 AI 原值
    logs = list(reversed(logs))

    # 每个字段取最早一次改动前的 old_value
    ai_original: dict[str, object] = {}
    for log in logs:
        if log.field in ai_original:
            continue
        ai_original[log.field] = log.old_value

    targets = [field] if field and field != "all" else list(ai_original.keys())
    reverted: list[str] = []
    for f in targets:
        if f not in PATCHABLE_FIELDS:
            continue
        old = ai_original.get(f)
        cur = getattr(seg, f, None)
        if old is None or str(old) == str(cur):
            continue  # 没有可回滚的差异
        # old_value 存的是字符串，按目标字段类型还原，避免把 int 存成 str
        typeof = type(cur)
        try:
            value = typeof(old) if typeof is not type(None) else old
        except (TypeError, ValueError):
            value = old
        setattr(seg, f, value)
        await audit_service.record(
            db,
            work_id=work_id,
            user_id=user_id,
            object_type="segment",
            object_id=segment_id,
            field=f,
            old_value=cur,
            new_value=value,
            action="revert",
            note=f"还原{FIELD_LABELS.get(f, f)}为 AI 原值",
        )
        reverted.append(f)

    if reverted:
        try:
            seg.low_conf = bool(float(seg.confidence) < 0.7)
        except (TypeError, ValueError):
            seg.low_conf = False
        await db.commit()
        await db.refresh(seg)

    return {"segment": SegmentOut.model_validate(seg).model_dump(), "reverted": reverted}


async def list_edits(db: AsyncSession, work_id: int, segment_id: int | None = None) -> list[dict]:
    """某作品的片段修改留痕（接口文档 §13.4，工作空间「修改留痕」区块用）。"""
    logs = await audit_service.list_logs(db, work_id, object_type="segment", object_id=segment_id)
    return [await audit_service.to_diff(log) for log in logs]
