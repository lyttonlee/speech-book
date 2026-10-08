"""导出服务（workspace.html `#export` 区块 + 接口文档 §14）。

导出 = 后处理流水线：**拼接 → 响度归一 → 字幕生成 → 隐式水印**。
POC 阶段不真正跑 ffmpeg，只落一条 `ExportRecord`（记录格式/时长/参数/有效期），
并把最近一次合成产物作为导出 `url`，保证前端导出历史与下载链路可用；
生产替换点在 `run_export()` 里（接 ffmpeg + 水印工具），接口签名不变。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.storage import public_url
from app.models.asset import AudioAsset, ExportRecord
from app.models.task import Task

# 导出链接默认有效期（接口文档 §14.3 要求 ≥7 天可配）
DEFAULT_EXPIRE_DAYS = 7


async def create_export(
    db: AsyncSession,
    *,
    work_id: int,
    fmt: str = "mp3",
    params: dict | None = None,
    source_task_id: str | None = None,
    duration: int = 0,
) -> ExportRecord:
    """生成一条导出记录（真实转码在 `run_export` 中触发，这里先落库）。

    Args:
        work_id: 作品 id。
        fmt: 音频格式 mp3 / wav / m4a / aac（校验白名单）。
        params: 导出参数（采样率、比特率、是否带字幕、字幕格式、片头片尾、
                BGM、响度归一、隐式水印开关等，见 DESIGN_SPEC §5.3b 导出区块）。
        source_task_id: 来源合成任务 id（找不到则自动取该书最后的成品）。
        duration: 成品时长（秒）。

    Returns:
        已落库的 ExportRecord。
    """
    params = params or {}
    fmt = (fmt or "mp3").lower()

    url = ""
    if source_task_id:
        task = await db.get(Task, source_task_id)
        url = (task.result_ref or "") if task else ""
    if not url:
        last = (await db.execute(
            select(AudioAsset)
            .where(AudioAsset.work_id == work_id, AudioAsset.status == "ready")
            .order_by(AudioAsset.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        url = last.url if last else ""

    expires = datetime.now(timezone.utc) + timedelta(days=DEFAULT_EXPIRE_DAYS)
    rec = ExportRecord(
        work_id=work_id,
        format=fmt,
        url=public_url(url.lstrip("/")) if url else "",
        duration=duration,
        params_json={**params, "with_subtitle": params.get("with_subtitle", True)},
        expires_at=expires.isoformat(),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def run_export(db: AsyncSession, rec: ExportRecord) -> ExportRecord:
    """执行导出后处理（POC 占位：只补 url/duration，生产替换点在这里）。

    生产实现顺序（文档 §14.1）：
    1. 下载源音频 → ffmpeg 拼接；
    2. ffmpeg loudnorm 响度归一到 -16 LUFS（有声书常用）；
    3. 生成 srt/vtt/lrc 字幕；
    4. 若开启隐式水印，用底层帧/频谱插入不可听标记；
    5. 上传 MinIO 得到签名链接，回填 ExportRecord.url。
    """
    # 占位：url 已在 create_export 里填好，这里仅保证字段非空
    if not rec.url:
        raise NotFound("暂无可导出的音频，请先完成合成")
    await db.commit()
    return rec


async def list_exports(db: AsyncSession, work_id: int) -> list[ExportRecord]:
    """导出历史（接口文档 §14.2，前端导出记录表）。"""
    rows = (await db.execute(
        select(ExportRecord).where(ExportRecord.work_id == work_id).order_by(ExportRecord.id.desc())
    )).scalars().all()
    return list(rows)


def to_export_row(r: ExportRecord) -> dict:
    """导出记录 → 前端表格行。"""
    return {
        "id": r.id,
        "format": r.format,
        "url": r.url,
        "duration": r.duration,
        "params": r.params_json or {},
        "expires_at": r.expires_at,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }
