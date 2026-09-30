from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services.voice_service import list_voices

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("")
async def list_voices_route(
    tags: str | None = Query(None),
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tag_list = [t for t in (tags or "").split(",") if t] or None
    rows, total = await list_voices(db, tags=tag_list, vtype=type, page=page, page_size=page_size)
    return ok({
        "items": [{"id": v.id, "name": v.name, "type": v.type, "engine": v.engine,
                   "tags": v.tags_json, "status": v.status} for v in rows],
        "total": total, "page": page, "page_size": page_size,
    })


@router.get("/{voice_id}")
async def get_voice(voice_id: int, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    from app.services.voice_service import get_voice
    v = await get_voice(db, voice_id)
    return ok({"id": v.id, "name": v.name, "engine": v.engine, "tags": v.tags_json, "status": v.status})
