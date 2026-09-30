from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/public-config")
async def public_config():
    return ok({
        "default_engine": "stub",
        "support_formats": ["txt", "md", "docx", "epub"],
        "max_file_mb": 50,
        "poc_mode": True,
    })


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return ok({"default_engine": "stub", "concurrency": 2, "moderation_policy": "pass_through"})


@router.get("/notifications")
async def notifications(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return ok({"items": [], "total": 0, "page": 1, "page_size": 20})


@router.get("/logs")
async def logs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return ok({"items": [], "total": 0, "page": 1, "page_size": 20})
