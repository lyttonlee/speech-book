from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


SEGMENT_TYPES = ["narration", "dialogue", "psychology"]  # 旁白/对话/心理描写
ROLE_LEVELS = ["main", "supporting", "extra"]            # 主角/配角/龙套


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text, default="")


class Segment(Base, TimestampMixin):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(16), default="narration")
    text: Mapped[str] = mapped_column(Text, default="")
    speaker_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emotion: Mapped[str] = mapped_column(String(16), default="neutral")
    intensity: Mapped[int] = mapped_column(Integer, default=50)
    confidence: Mapped[float] = mapped_column(default=0.8)
    low_conf: Mapped[bool] = mapped_column(default=False)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16), default="supporting")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
