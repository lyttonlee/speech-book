from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.models.voice import Bind
from app.services import work_service

router = APIRouter(prefix="/works/{work_id}/bindings", tags=["bindings"])


@router.get("")
async def list_bindings(work_id: int, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    rows = (await db.execute(select(Bind).where(Bind.work_id == work_id))).scalars().all()
    return ok({"items": [{"role_id": b.role_id, "voice_id": b.voice_id, "params": b.params_json}
                         for b in rows], "total": len(rows), "page": 1, "page_size": 100})


@router.put("")
async def set_bindings(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    items = body.get("items", [])
    # upsert by (work_id, role_id)
    for it in items:
        role_id = it.get("role_id", 0)
        voice_id = it.get("voice_id")
        params = it.get("params", {})
        existing = (await db.execute(
            select(Bind).where(Bind.work_id == work_id, Bind.role_id == role_id)
        )).scalar_one_or_none()
        if existing:
            existing.voice_id = voice_id
            existing.params_json = params
        else:
            db.add(Bind(work_id=work_id, role_id=role_id, voice_id=voice_id, params_json=params))
    await db.commit()
    return ok({"applied": len(items)})


@router.post("/auto")
async def auto_bind(work_id: int, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    from app.services.voice_service import list_voices
    voices, _ = await list_voices(db, page_size=10)
    male = next((v for v in voices if "男声" in (v.tags_json or [])), voices[0] if voices else None)
    narrator = next((v for v in voices if "旁白" in (v.tags_json or [])), None)
    applied = 0
    for v in voices:
        role_id = 0 if (v.tags_json and "旁白" in v.tags_json) else v.id
        existing = (await db.execute(
            select(Bind).where(Bind.work_id == work_id, Bind.role_id == role_id)
        )).scalar_one_or_none()
        if not existing and v is not None:
            db.add(Bind(work_id=work_id, role_id=role_id, voice_id=v.id, params_json={}))
            applied += 1
    await db.commit()
    return ok({"applied": applied})
