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


@router.post("/refresh")
async def refresh(body: dict, db: AsyncSession = Depends(get_db)):
    """刷新令牌（§3.3）。

    body = { "refresh_token": "..." }；POC 阶段 refresh_token 为空串，
    直接按当前 access_token 里的用户重新签发一张新的 access_token。
    """
    user = await user_service.user_from_refresh_token(db, body.get("refresh_token", ""))
    tokens = await user_service.issue_tokens(user)
    return ok({"access_token": tokens["access_token"]})


@router.patch("/me")
async def update_me(body: dict, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """改基本资料（设置页）。 body = { nickname? }

    邮箱作为登录标识不允许改；头像需对象存储，POC 未开放。
    """
    updated = await user_service.update_profile(db, user, nickname=body.get("nickname"))
    return ok(UserOut.model_validate(updated).model_dump())


@router.post("/password")
async def change_password(body: dict, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """修改密码（设置页「安全」）。 body = { old_password, new_password }"""
    return ok(await user_service.change_password(
        db, user,
        old_password=body.get("old_password", ""),
        new_password=body.get("new_password", ""),
    ))


@router.post("/realname")
async def realname(body: dict, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """实名认证（§3.5），克隆前置条件之一。

    body = { real_name, id_card_no, consent_doc_url }
    POC 只做非空校验并把 `realname_verified` 置真；生产应接第三方实名核验服务。
    """
    res = await user_service.realname_verify(
        db, user,
        real_name=body.get("real_name", ""),
        id_card_no=body.get("id_card_no", ""),
        consent_doc_url=body.get("consent_doc_url", ""),
    )
    return ok(res)


@router.post("/voiceprint")
async def voiceprint(db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """声纹核验（§3.6），通过后解锁克隆提交。

    POC 阶段没有音频比对能力，视为核验通过；生产需要用户朗读指定语句、
    做声纹向量比对确认「本人」。
    """
    res = await user_service.voiceprint_check(db, user)
    return ok(res)


@router.post("/logout")
async def logout():
    return ok()
