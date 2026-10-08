"""校对工作台路由（接口文档 §13）。

对应 workspace.html「已解析章节内容」区块：章节树 + 片段列表 + 片段属性面板 + 待复核队列。
路由保持薄：参数校验 + 鉴权 + 调 service，业务逻辑一律下沉到 `proofread_service`。

路由注册顺序注意：`/segments/batch` 必须写在 `/segments/{segment_id}` **之前**，
否则 "batch" 会被当成 int 型的 segment_id 触发 422。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import proofread_service, work_service

router = APIRouter(prefix="/works/{work_id}", tags=["proofread"])


@router.get("/proofread")
async def get_proofread(work_id: int, chapter_id: int | None = Query(None),
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """三栏校对数据（§13.1）：章节 / 片段明细 / 角色 / 音色。

    不带 chapter_id 时返回第一章，供前端首屏直接渲染。
    """
    await work_service.get_owned(db, work_id, user.id)
    board = await proofread_service.proofread_board(db, work_id, chapter_id)
    return ok(board)


@router.post("/segments/batch")
async def batch_patch(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """批量修改片段（§13.3）：body = { ids: [...], patch: {...} }。

    前端「批量操作栏」勾选多行后统一改说话人/类型/情绪时使用。
    """
    await work_service.get_owned(db, work_id, user.id)
    ids = body.get("ids") or []
    patch = body.get("patch") or {}
    res = await proofread_service.batch_patch_segments(db, work_id, ids, patch, user.id)
    return ok(res)


@router.patch("/segments/{segment_id}")
async def patch_segment(work_id: int, segment_id: int, body: dict,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """修改单个片段（§13.2）：类型 / 说话人 / 情绪 / 强度 / 正文。

    前端每次操作即时 PATCH（FR-808），后端幂等写字段 + 写修改留痕，
    AI 原值保留在 EditLog 里可一键还原。
    """
    await work_service.get_owned(db, work_id, user.id)
    res = await proofread_service.patch_segment(db, work_id, segment_id, body, user.id)
    return ok(res)


@router.get("/proofread/edits")
async def list_proofread_edits(work_id: int, segment_id: int | None = Query(None),
                               db: AsyncSession = Depends(get_db),
                               user: User = Depends(get_current_user)):
    """片段维度的修订历史（§13.4）：撤销 / 重做与「修改留痕」区块的数据源。"""
    await work_service.get_owned(db, work_id, user.id)
    rows = await proofread_service.list_edits(db, work_id, segment_id)
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows)})


@router.post("/segments/{segment_id}/revert")
async def revert_segment(work_id: int, segment_id: int, body: dict,
                         db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """把某个片段回滚到留痕里的旧值（AI 原值还原）。

    body = { "field": "emotion" } 或 { "field": "all" }；
    实现上委托 proofread_service 从最新一条 EditLog 取 old_value 写回。
    """
    await work_service.get_owned(db, work_id, user.id)
    field = body.get("field") or "all"
    res = await proofread_service.revert_segment(db, work_id, segment_id, field, user.id)
    return ok(res)
