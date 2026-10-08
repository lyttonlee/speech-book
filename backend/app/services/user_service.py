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


async def user_from_refresh_token(db: AsyncSession, refresh_token: str) -> User:
    """按 refresh_token 找到用户并重新签发 access_token（§3.3）。

    POC 说明：当前 `issue_tokens` 返回的 refresh_token 是空串，
    这里退化为「取演示/首个可用用户」，只为保证接口链路可用；
    生产应改成签发带type=refresh 的 JWT，校验通过后再取 user_id。
    """
    if refresh_token:
        from app.core.security import decode_token
        try:
            # create_access_token 写入的用户标识是 "sub"（见 security.py）
            payload = decode_token(refresh_token)
        except Exception:
            payload = None
        uid = payload.get("sub") if payload else None
        if uid:
            user = await db.get(User, int(uid))
            if user:
                return user
    # POC 兜底：演示账号
    return await get_or_create_demo(db)


async def realname_verify(db: AsyncSession, user: User, *, real_name: str,
                          id_card_no: str, consent_doc_url: str) -> dict:
    """实名认证（§3.5）。 POC 只校验必填项，通过后解锁声纹核验。

    Returns:
        {"realname_verified": bool, "voiceprint_required": bool}
    """
    from app.core.errors import BadRequest

    if not real_name or not id_card_no:
        raise BadRequest("请填写真实姓名与证件号")
    if not consent_doc_url:
        raise BadRequest("请先签署授权书并上传")

    user.realname_verified = True
    await db.commit()
    await db.refresh(user)
    # 实名后仍需声纹核验（本人）才能提交克隆
    return {
        "realname_verified": True,
        "voiceprint_required": not user.voiceprint_checked,
    }


async def voiceprint_check(db: AsyncSession, user: User) -> dict:
    """声纹核验（§3.6）。

    生产实现：接收若干条指定语句音频 → 提取声纹向量 → 与身份证照/历史样本比对
    确认是本人 → 通过后才允许 `POST /voices/clone`。
    POC 阶段没有比对能力，直接置通过并在返回值里标注是 POC 免检。
    """
    user.voiceprint_checked = True
    await db.commit()
    await db.refresh(user)
    return {"voiceprint_checked": True, "poc_note": "POC 环境免真实声纹比对"}


async def update_profile(db: AsyncSession, user: User, *, nickname: str | None = None) -> User:
    """改基本资料（设置页「基本信息」）。

    POC 只开放昵称：邮箱是登录标识不允许改（改了会让旧 token / 任务归属对不上），
    头像需要对象存储，后端尚未接入，前端对应入口也是占位。
    """
    if nickname is not None and nickname.strip():
        user.nickname = nickname.strip()
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, *, old_password: str,
                          new_password: str) -> dict:
    """修改密码（设置页「安全」）。

    校验旧密码后再写新密码，防止拿到 access_token 就能直接重置。
    密码强度只做最小长度校验，规则与注册保持一致。
    """
    if not verify_password(old_password, user.password_hash):
        raise BadRequest("当前密码不正确")
    if len(new_password or "") < 8:
        raise BadRequest("新密码至少 8 位")
    user.password_hash = hash_password(new_password)
    await db.commit()
    return {"changed": True}


async def get_or_create_demo(db: AsyncSession) -> User:
    user = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
    if user:
        return user
    return await register(db, DEMO_EMAIL, DEMO_PASSWORD, "体验用户")
