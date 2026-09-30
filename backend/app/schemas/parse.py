from __future__ import annotations

from pydantic import BaseModel


class SegmentOut(BaseModel):
    id: int
    chapter_id: int
    order: int
    type: str
    text: str
    speaker_role_id: int | None = None
    speaker_name: str | None = None
    emotion: str
    intensity: int
    confidence: float
    low_conf: bool

    model_config = {"from_attributes": True}


class ChapterSegments(BaseModel):
    chapter_id: int
    title: str
    order: int
    paragraphs: list  # simplified for POC: list of SegmentOut


class RoleOut(BaseModel):
    id: int
    name: str
    level: str
    aliases: list = []
    line_count: int = 0

    model_config = {"from_attributes": True}


class ReviewItem(BaseModel):
    segment_id: int
    type: str
    field: str
    suggestion: str
    confidence: float
