from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    user = await user_service.register(db, body.email, body.password, body.nickname)
    return ok(UserOut.model_validate(user).model_dump())


@router.post("/login")
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await user_service.authenticate(db, body.email, body.password)
    if not user:
        from app.core.errors import BadRequest
        raise BadRequest("邮箱或密码错误")
    return ok(await user_service.issue_tokens(user))


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(user).model_dump())


@router.post("/logout")
async def logout():
    return ok()
