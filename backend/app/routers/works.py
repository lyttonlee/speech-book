from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.work import WorkCreate, WorkOut, WorkUpdate
from app.core.errors import NotFound
from app.services import asset_service
from app.services import work_service

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
    """作品列表（Dashboard 数据源）。

    除基础字段外，每张卡附带 `summary`（制作进度 / 已绑声纹 / 已配音三项指标），
    让用户在列表页就能判断哪本书需要动手（DESIGN_SPEC §7b.1）。
    """
    rows, total = await work_service.list_works(
        db, user.id, status=status, keyword=keyword, page=page, page_size=page_size
    )
    items = []
    for w in rows:
        item = WorkOut.model_validate(w).model_dump()
        item["summary"] = await work_service.work_summary(db, w)
        items.append(item)
    return ok({
        "items": items,
        "total": total, "page": page, "page_size": page_size,
    })


@router.post("/{work_id}/restore")
async def restore(work_id: int, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """从回收站恢复作品（接口文档 §4.5）。恢复到草稿态。"""
    work = await work_service.restore_work(db, work_id, user.id)
    return ok(WorkOut.model_validate(work).model_dump())


@router.post("/{work_id}/duplicate", status_code=201)
async def duplicate(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """复制作品（接口文档 §4.6）。

    body: { "reuse_bindings": true, "reuse_params": true }
    复用绑定时把角色与绑定一起复制过去，省得重新栓一遍音色。
    """
    work = await work_service.duplicate_work(
        db, work_id, user.id,
        reuse_bindings=bool(body.get("reuse_bindings", True)),
        reuse_params=bool(body.get("reuse_params", True)),
    )
    return ok(WorkOut.model_validate(work).model_dump())


@router.get("/{work_id}/overview")
async def overview(work_id: int, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """工作空间全景数据（DESIGN_SPEC §7 要求的服务端聚合接口）。

    一次返回：作品头 + 6 段流水线 + 6 项指标 + 角色与绑定 + 合规前置 +
    关系图缩略 + 章节树 + 音频资产 + 修改留痕 + 版本快照。
    避免前端为拼一屏发十几个请求。
    """
    from app.services.overview_service import build_overview
    data = await build_overview(db, work_id, user.id)
    return ok(data)


@router.get("/{work_id}/pipeline")
async def pipeline(work_id: int, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """制作流水线六段状态与耗时（workspace.html `.pipeline` 区块单独刷新用）。"""
    from app.services.overview_service import build_pipeline
    work = await work_service.get_owned(db, work_id, user.id)
    return ok({"items": build_pipeline(work), "total": 6, "page": 1, "page_size": 6})


@router.get("/{work_id}/assets")
async def assets(work_id: int, kind: str | None = Query(None),
                 db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """已制作配音资产列表（workspace.html 音频资产表）。"""
    await work_service.get_owned(db, work_id, user.id)
    rows = await asset_service.list_assets(db, work_id, kind=kind)
    return ok({
        "items": [asset_service.to_asset_row(a) for a in rows],
        "total": len(rows), "page": 1, "page_size": 100,
    })


@router.get("/{work_id}/assets/reindex")
async def assets_reindex(work_id: int, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """扫描历史合成任务补齐音频资产（幂等，页面列表与真实产物不同步时兜底）。"""
    await work_service.get_owned(db, work_id, user.id)
    res = await asset_service.reindex(db, work_id)
    return ok(res)


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
