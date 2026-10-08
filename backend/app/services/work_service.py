from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.models.asset import AudioAsset
from app.models.parse import Role
from app.models.voice import Bind
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
    """作品列表（排除回收站），支持状态筛选与书名模糊搜索。"""
    stmt = select(Work).where(Work.owner_id == owner_id, Work.status != "deleted")
    if status:
        stmt = stmt.where(Work.status == status)
    if keyword:
        stmt = stmt.where(Work.name.contains(keyword))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(Work.updated_at.desc())
                             .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return rows, total


async def restore_work(db: AsyncSession, work_id: int, owner_id: int) -> Work:
    """从回收站恢复作品（接口文档 §4.5）。

    只有 `status=deleted` 的作品能被恢复；恢复到 draft（草稿）态，
    用户需要重新走一遍流水线（或直接从已有解析结果继续）。
    """
    work = (await db.execute(select(Work).where(Work.id == work_id))).scalar_one_or_none()
    if not work or work.owner_id != owner_id:
        raise NotFound("作品不存在或无权访问")
    if work.status != "deleted":
        raise Conflict("作品未在回收站中")
    work.status = "draft"
    work.deleted_at = None
    await db.commit()
    await db.refresh(work)
    return work


async def duplicate_work(db: AsyncSession, work_id: int, owner_id: int, *,
                         reuse_bindings: bool = True, reuse_params: bool = True) -> Work:
    """复制作品（接口文档 §4.6），可用于同书的不同演绎版本。

    Args:
        work_id: 源作品 id。
        owner_id: 目标归属用户（只能复制到自己名下）。
        reuse_bindings: 是否沿用角色-音色绑定。
        reuse_params: 是否沿用绑定里的合成参数（语速/音高/音量）。

    Returns:
        新建的作品（status=draft，未复制章节文本见下方说明）。

    说明：MVP 阶段只复制「元信息 + 角色 + 绑定」，**不**复制章节与片段，
    因为复制后的成品音色版本不同，重新解析更合理；生产如需完整复制，
    再补 Chapter/Segment 的深拷贝即可。
    """
    src = await get_owned(db, work_id, owner_id)

    new_work = Work(
        owner_id=owner_id,
        name=f"{src.name}（副本）",
        author=src.author,
        intro=src.intro,
        type=src.type,
        lang=src.lang,
        cover_url=src.cover_url,
        status="draft",
        bindings_version="v1",
    )
    db.add(new_work)
    await db.flush()  # 先拿到 new_work.id，再复制子表

    if reuse_bindings:
        old_binds = (await db.execute(
            select(Bind).where(Bind.work_id == work_id)
        )).scalars().all()
        for b in old_binds:
            db.add(Bind(
                work_id=new_work.id,
                role_id=b.role_id,
                voice_id=b.voice_id,
                params_json=b.params_json if reuse_params else {},
            ))

        old_roles = (await db.execute(
            select(Role).where(Role.work_id == work_id)
        )).scalars().all()
        for r in old_roles:
            db.add(Role(
                work_id=new_work.id,
                name=r.name,
                level=r.level,
                aliases=list(r.aliases or []),
                profile_json=dict(r.profile_json or {}),
            ))

    await db.commit()
    await db.refresh(new_work)
    return new_work


async def work_summary(db: AsyncSession, work: Work) -> dict:
    """计算单张作品卡的「工作空间摘要」三指标（DESIGN_SPEC §5.3 / §7b.1）。

    Dashboard 卡片要在列表页就能判断「哪本书需要动手」，所以返回：
    - progress：整体完成度 0~100（喂给卡片进度条）
    - bound_roles / total_roles：已绑声纹 / 角色总数
    - audio_minutes：已配音时长（分钟）

    三个指标全部一次聚合查询，避免 N+1。
    """
    total_roles = (await db.execute(
        select(func.count(Role.id)).where(Role.work_id == work.id)
    )).scalar() or 0
    bound_roles = (await db.execute(
        select(func.count(Bind.id))
        .where(Bind.work_id == work.id, Bind.voice_id.isnot(None))
    )).scalar() or 0
    audio_seconds = (await db.execute(
        select(func.coalesce(func.sum(AudioAsset.duration), 0))
        .where(AudioAsset.work_id == work.id)
    )).scalar() or 0

    return {
        "progress": work.progress or 0,
        "bound_roles": int(bound_roles),
        "total_roles": int(total_roles),
        "audio_minutes": round(int(audio_seconds) / 60, 1),
    }
