from __future__ import annotations

from pydantic import BaseModel


class Envelope(BaseModel):
    code: str = "OK"
    data: object | None = None
    request_id: str | None = None


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
