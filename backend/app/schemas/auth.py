from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=64)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 86400


class UserOut(BaseModel):
    id: int
    email: str
    nickname: str
    realname_verified: bool = False
    voiceprint_checked: bool = False
    role: str = "creator"

    model_config = {"from_attributes": True}
