from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


TASK_TYPES = ["parse", "synth", "clone"]
TASK_STATUS = ["pending", "running", "success", "failed", "partial"]


def _new_id() -> str:
    return "t-" + uuid.uuid4().hex[:12]


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    work_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(16), default="parse")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(128), default="")
    result_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subtitle_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
