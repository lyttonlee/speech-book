from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


# 作品状态机（详见 docs/接口文档.md §16.1）
WORK_STATUSES = [
    "draft",            # 草稿
    "text_uploaded",    # 文本已上传
    "parsing",          # 解析中
    "pending_review",   # 待校对
    "review_done",      # 校对完成
    "synthesizing",     # 合成中
    "synth_done",       # 合成完成
    "exporting",        # 导出中
    "completed",        # 已完成
    "archived",         # 已归档
    "deleted",          # 已删除(回收站)
]


class Work(Base, TimestampMixin):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(128), default="")
    intro: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(32), default="")
    lang: Mapped[str] = mapped_column(String(8), default="zh")
    cover_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    # 整体完成度 0~100，直接喂给工作空间作品头的环形进度（.ring）
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # 制作流水线各段状态与耗时：
    #   {"upload": {"status":"done","seconds":12}, "parse": {"status":"active",...}, ...}
    # 六段见 DESIGN_SPEC §5.3b：upload / parse / proofread / cast / synth / export
    pipeline_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 绑定的版本标识；合成时带 bindings_version 做一致性校验
    bindings_version: Mapped[str] = mapped_column(String(32), default="v1")
    # 进入回收站的时间；非空即视为已删除（30 天后物理清理）
    deleted_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 是否已人工介入过（任一阶段被人工重跑/改过即置 True）
    manual_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
