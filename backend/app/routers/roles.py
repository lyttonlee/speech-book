from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import role_service, work_service
from app.services.role_service import get_or_create_role

router = APIRouter(prefix="/works/{work_id}/roles", tags=["roles"])


@router.get("")
async def list_roles(work_id: int, level: str | None = None,
                    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    return ok({"items": await role_service.list_roles(db, work_id, level=level), "total": 0, "page": 1, "page_size": 100})


@router.post("", status_code=201)
async def create_role(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    role = await get_or_create_role(db, work_id, body.get("name", "新角色"))
    return ok({"id": role.id, "name": role.name, "level": role.level})


@router.post("/{role_id}/merge")
async def merge_role(work_id: int, role_id: int, body: dict,
                    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    target = await role_service.merge_roles(db, role_id, body.get("source_role_ids", []))
    return ok({"id": target.id, "name": target.name})


@router.get("/{role_id}/recommend-voices")
async def recommend(work_id: int, role_id: int, top: int = 5,
                   db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    from app.services.voice_service import list_voices
    rows, _ = await list_voices(db, page_size=top)
    return ok({"items": [{"voice_id": v.id, "name": v.name, "score": 0.9,
                          "matched_tags": v.tags_json} for v in rows], "total": len(rows), "page": 1, "page_size": top})
