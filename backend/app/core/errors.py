"""Unified error envelope + application exceptions."""
from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    code: str = "INTERNAL"
    status: int = 500
    message: str = "Internal error"

    def __init__(self, message: str | None = None, status: int | None = None, code: str | None = None):
        if message:
            self.message = message
        if status:
            self.status = status
        if code:
            self.code = code
        super().__init__(self.message)


class BadRequest(AppError):
    code = "INVALID_PARAM"
    status = 400
    message = "参数校验失败"


class Unauthorized(AppError):
    code = "UNAUTHORIZED"
    status = 401
    message = "未登录或令牌失效"


class Forbidden(AppError):
    code = "FORBIDDEN"
    status = 403
    message = "无权限"


class NotFound(AppError):
    code = "NOT_FOUND"
    status = 404
    message = "资源不存在"


class Conflict(AppError):
    code = "CONFLICT"
    status = 409
    message = "状态冲突"


class ComplianceFailed(AppError):
    """克隆合规前置未通过（未实名 / 无授权书 / 声纹不符本人）。"""

    code = "CLONE_COMPLIANCE_FAILED"
    status = 422
    message = "克隆合规前置未通过"


class BannedPerson(AppError):
    """命中公众人物禁克隆库。"""

    code = "BANNED_PERSON"
    status = 422
    message = "命中公众人物禁克隆名单"


class EngineUnavailable(AppError):
    code = "ENGINE_UNAVAILABLE"
    status = 503
    message = "引擎暂不可用"


def _envelope(code: str, message: str, request_id: str) -> dict:
    return {"code": code, "message": message, "request_id": request_id}


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status,
        content=_envelope(exc.code, exc.message, _rid(request)),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_envelope("INVALID_PARAM", "参数校验失败", _rid(request)),
    )


async def unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=_envelope("INTERNAL", "服务内部错误", _rid(request)),
    )


def _rid(request: Request) -> str:
    return request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
