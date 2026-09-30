from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TaskOut(BaseModel):
    id: str
    work_id: int | None = None
    type: str
    status: str
    progress: int
    stage: str = ""
    result_ref: str | None = None
    subtitle_ref: str | None = None
    payload: dict = {}
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
