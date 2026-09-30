from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
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
