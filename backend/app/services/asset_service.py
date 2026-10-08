"""音频资产服务（workspace.html `#audio` 区块的「已制作配音」资产表）。

资产分四类（DESIGN_SPEC §7b.2）：
- `sample`：样章成品（前 1~2 章，用于用户先听后决定全本）
- `chapter`：分章成品（逐章可下载、可单章重合成）
- `role_track`：分角色单轨（旁白轨 role_id=0 / 某角色轨，前端双色波形双轨播放）
- `full`：全本成品

此外提供「重建全本书的资产索引」：`reindex` 会把已有合成任务产物扫描成资产行，
避免每次页面刷新都重复查合成目录。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AudioAsset
from app.models.task import Task


async def list_assets(db: AsyncSession, work_id: int, *, kind: str | None = None) -> list[AudioAsset]:
    """列出某作品的音频资产（按种类、创建时间倒序）。"""
    stmt = select(AudioAsset).where(AudioAsset.work_id == work_id)
    if kind:
        stmt = stmt.where(AudioAsset.kind == kind)
    rows = (await db.execute(
        stmt.order_by(AudioAsset.id.desc())
    )).scalars().all()
    return list(rows)


def to_asset_row(a: AudioAsset) -> dict:
    """把资产 ORM 转成前端音频资产表的一行。"""
    return {
        "id": a.id,
        "kind": a.kind,
        "chapter_id": a.chapter_id,
        "role_id": a.role_id,
        "url": a.url,
        "duration": a.duration,
        "size": a.size,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else "",
    }


async def add_asset(
    db: AsyncSession,
    *,
    work_id: int,
    kind: str,
    url: str,
    task_id: str | None = None,
    chapter_id: int | None = None,
    role_id: int | None = None,
    duration: int = 0,
    size: int = 0,
    params: dict | None = None,
    status: str = "ready",
) -> AudioAsset:
    """登记一条音频资产（合成任务完成后由 synth_service 调用）。"""
    asset = AudioAsset(
        work_id=work_id,
        task_id=task_id,
        kind=kind,
        chapter_id=chapter_id,
        role_id=role_id,
        url=url,
        duration=duration,
        size=size,
        params_json=params or {},
        status=status,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def reindex(db: AsyncSession, work_id: int) -> dict:
    """扫描该作品的历史合成任务，把还没登记成资产的补齐（幂等）。

    用于页面首屏「已制作配音」列表与真实资产表不同步时兜底，
    避免用户看到空列表（合成确实跑过、只是没写资产行）。

    Returns:
        {"added": 新增资产数, "total": 当前资产总数}
    """
    tasks = (await db.execute(
        select(Task).where(Task.work_id == work_id, Task.status == "success",
                           Task.result_ref.isnot(None))
    )).scalars().all()

    exist = {(a.task_id, a.kind, a.chapter_id, a.role_id) for a in await list_assets(db, work_id)}
    added = 0
    for t in tasks:
        payload = t.payload_json or {}
        # 合成任务 payload 里记了 scope，据此判断是样章还是全本
        kind = "sample" if payload.get("scope") == "sample" else "full"
        chapter_ids = (payload.get("range") or {}).get("chapter_ids")
        key = (t.id, kind, None, None)
        if key not in exist:
            await add_asset(
                db,
                work_id=work_id,
                kind=kind,
                task_id=t.id,
                url=t.result_ref or "",
                params=payload,
            )
            exist.add(key)
            added += 1

    # 分章资产：从 range 记录里把每章单独列一行，供「分章下载 / 单章重合成」
    total = len(await list_assets(db, work_id))
    return {"added": added, "total": total}
