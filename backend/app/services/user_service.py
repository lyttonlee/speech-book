from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

DEMO_EMAIL = "demo@demo.com"
DEMO_PASSWORD = "demo1234"


async def register(db: AsyncSession, email: str, password: str, nickname: str) -> User:
    exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists:
        raise Conflict("邮箱已注册")
    user = User(email=email, nickname=nickname or email.split("@")[0],
                password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": "",
        "token_type": "bearer",
        "expires_in": 86400,
    }


async def get_or_create_demo(db: AsyncSession) -> User:
    user = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
    if user:
        return user
    return await register(db, DEMO_EMAIL, DEMO_PASSWORD, "体验用户")
