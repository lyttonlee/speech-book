"""Local file storage (POC replacement for MinIO).

Stores artifacts under settings.storage_dir and serves them via the
/files/{path:path} static route mounted in main.py.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

from app.core.config import settings

_ROOT = Path(settings.storage_dir)


def _safe(rel: str) -> Path:
    target = (_ROOT / rel).resolve()
    if not str(target).startswith(str(_ROOT.resolve())):
        raise ValueError("invalid storage path")
    return target


def save_bytes(rel: str, data: bytes) -> str:
    target = _safe(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return rel


def public_url(rel: str) -> str:
    return f"/files/{rel}"


def read_bytes(rel: str) -> bytes:
    return _safe(rel).read_bytes()


def serve(rel: str) -> FileResponse:
    target = _safe(rel)
    if not target.exists():
        raise NotFound("文件不存在")
    return FileResponse(target)
