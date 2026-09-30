from __future__ import annotations

from pydantic import BaseModel


class SynthRequest(BaseModel):
    scope: str = "sample"            # sample | full | range
    range: dict | None = None       # { "chapter_ids": [1,2] } when scope=range
    bindings_version: str = "current"
    export: dict | None = None      # { "format": "mp3", "with_subtitle": true }


class SynthStatus(BaseModel):
    task_id: str
    status: str
    progress: int
    audio_url: str | None = None
    subtitle_url: str | None = None
    failed_segments: int = 0
