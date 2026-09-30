from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


VOICE_TYPES = ["builtin", "clone"]
VOICE_STATUS = ["available", "pending", "training", "rejected"]


class Voice(Base, TimestampMixin):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(primary_key=True)
    # builtin 音色 owner_id 为 NULL；clone 音色归属上传用户
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16), default="builtin")
    engine: Mapped[str] = mapped_column(String(32), default="stub")
    engine_voice_id: Mapped[str] = mapped_column(String(64), default="")
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="available")


class Bind(Base, TimestampMixin):
    """角色-音色-参数绑定。role_id=0 表示旁白(narrator)。"""

    __tablename__ = "bindings"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    role_id: Mapped[int] = mapped_column(default=0)  # 0 = narrator
    voice_id: Mapped[int | None] = mapped_column(ForeignKey("voices.id"), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
