"""音频资产与导出记录数据模型（对应 workspace.html 的 `#audio` / `#export` 区块）。

`AudioAsset` 是工作空间「已制作配音」列表的数据源，覆盖设计图里的四类资产：
- sample：样章成品（前 1~2 章，全角色混流）
- chapter：分章成品（逐章可单独下载与重合成）
- role_track：分角色单轨（旁白轨 / 某角色轨，前端双色波形用）
- full：全本成品

`ExportRecord` 记录导出（拼接 + 响度归一 + 字幕 + 隐式水印）的产物与有效期，
对应接口文档 §14.2 的导出历史。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# 资产种类：sample=样章 / chapter=分章 / role_track=分角色轨 / full=全本
ASSET_KINDS = ["sample", "chapter", "role_track", "full"]
# 资产状态：ready=可下载 / processing=生成中 / failed=失败
ASSET_STATUSES = ["ready", "processing", "failed"]

# 导出格式（接口文档 §14.1）
EXPORT_FORMATS = ["mp3", "wav", "m4a", "aac"]
# 字幕格式
SUBTITLE_FORMATS = ["srt", "vtt", "lrc"]


class AudioAsset(Base, TimestampMixin):
    """一条已制作音频资产（工作空间音频资产表的一行）。"""

    __tablename__ = "audio_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    # 关联任务（来源合成任务 id，便于任务完成后回填与重试）
    task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 资产种类
    kind: Mapped[str] = mapped_column(String(16), default="chapter")
    # 分章资产指向哪一章；sample/full 为 NULL
    chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 分角色轨指向哪个角色；旁白轨固定存 0
    role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 音频访问路径（经 /files/{path} 静态路由或 MinIO 签名链接）
    url: Mapped[str] = mapped_column(String(512), default="")
    # 时长（秒），前端波形与资产表展示
    duration: Mapped[int] = mapped_column(Integer, default=0)
    # 文件体积（字节）
    size: Mapped[int] = mapped_column(Integer, default=0)
    # 合成参数快照（引擎、scope、语速等），便于复现与重合成
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 资产状态
    status: Mapped[str] = mapped_column(String(16), default="ready")


class ExportRecord(Base, TimestampMixin):
    """一次导出任务产物（导出历史的一行）。"""

    __tablename__ = "export_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    # 导出格式：mp3 / wav / m4a / aac
    format: Mapped[str] = mapped_column(String(8), default="mp3")
    # 导出产物路径
    url: Mapped[str] = mapped_column(String(512), default="")
    # 字幕产物路径（可选）
    subtitle_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 成品时长（秒）
    duration: Mapped[int] = mapped_column(Integer, default=0)
    # 导出参数（规格 / 是否带字幕 / 是否片头片尾 / 响度归一等）
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 下载链接过期时间（ISO 字符串）；接口要求有效期 ≥7 天可配
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
