from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    author: str = ""
    intro: str = ""
    type: str = ""
    lang: str = "zh"
    cover_url: str = ""


class WorkUpdate(BaseModel):
    name: str | None = None
    author: str | None = None
    intro: str | None = None
    type: str | None = None
    cover_url: str | None = None


class WorkOut(BaseModel):
    id: int
    owner_id: int
    name: str
    author: str
    type: str
    lang: str
    status: str
    chapter_count: int = 0
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
