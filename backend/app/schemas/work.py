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
    """作品输出模型（接口文档 §4.1/§4.3）。

    `intro` 与 `cover_url` 是列表卡片与详情页都要展示的字段，
    早期版本漏了导致前端拿不到封面，这里按文档补齐。
    """
    id: int
    owner_id: int
    name: str
    author: str
    intro: str = ""
    type: str
    lang: str
    cover_url: str = ""
    status: str
    chapter_count: int = 0
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
