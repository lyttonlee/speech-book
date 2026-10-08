"""导出路由（接口文档 §14 / workspace.html `#export` 区块）。

导出 = 拼接 + 响度归一 + 字幕 + 隐式水印。POC 阶段不真跑 ffmpeg，
只落 `ExportRecord` 并把最近合成产物作为导出链接，保证前端导出历史与下载可用；
真实转码替换点在 `export_service.run_export()`。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import export_service, work_service

router = APIRouter(prefix="/works/{work_id}/export", tags=["export"])


@router.post("")
async def start_export(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """提交导出（§14.1）。

    body 支持：format / sample_rate / bitrate / with_subtitle / subtitle_fmt /
    include_sample 等（见 DESIGN_SPEC §5.3b 导出区块的片头片尾与 BGM 配置）。
    """
    work = await work_service.get_owned(db, work_id, user.id)
    rec = await export_service.create_export(
        db,
        work_id=work_id,
        fmt=body.get("format", "mp3"),
        params=body,
        source_task_id=body.get("task_id"),
        duration=int(body.get("duration", 0) or 0),
    )
    # POC 同步跑完（生产改为派发异步任务 + SSE 进度）
    await export_service.run_export(db, rec)
    # 导出后推进作品状态机：合成完成 → 导出中 → 已完成
    await work_service.set_status(db, work, "completed")
    return ok({"record_id": rec.id, "url": rec.url, "expires_at": rec.expires_at})


@router.get("")
async def list_exports(work_id: int, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """导出历史（§14.2）：前端导出记录表按时间倒序展示。"""
    await work_service.get_owned(db, work_id, user.id)
    rows = await export_service.list_exports(db, work_id)
    return ok({
        "items": [export_service.to_export_row(r) for r in rows],
        "total": len(rows), "page": 1, "page_size": len(rows),
    })
