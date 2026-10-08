"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.storage import storage
from app.core.errors import (
    AppError,
    app_error_handler,
    unhandled_handler,
    validation_error_handler,
)
from app.core.response import ok
from app.routers import (
    audit,
    auth,
    bindings,
    export,
    files,
    graph,
    parse,
    proofread,
    roles,
    synth,
    system,
    tasks,
    voices,
    works,
)
from app.services.voice_service import seed_voices

PREFIX = settings.api_v1_prefix


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 建表：SQLite / PostgreSQL 通用（SQLAlchemy create_all，幂等）
    await init_db()

    # 对象存储：首次启动确保桶存在（MinIO 模式下否则 PUT 会 404）
    # 不强制成功——local 模式或对象存储临时不可用时，服务照常起来
    try:
        await storage.ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("bucket ensure skipped: %s", exc)

    async with SessionLocal() as db:
        await seed_voices(db)

    # 预热 Redis 客户端（连不上只告警，progress 层会自动退回内存 Hub）
    if settings.progress_backend == "redis":
        from app.core.redis_bus import get_bus

        get_bus()

    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_handler)

app.include_router(auth.router, prefix=PREFIX)
app.include_router(works.router, prefix=PREFIX)
app.include_router(files.router, prefix=PREFIX)
app.include_router(parse.router, prefix=PREFIX)
app.include_router(roles.router, prefix=PREFIX)
app.include_router(proofread.router, prefix=PREFIX)
app.include_router(graph.router, prefix=PREFIX)
app.include_router(audit.router, prefix=PREFIX)
app.include_router(export.router, prefix=PREFIX)
app.include_router(voices.router, prefix=PREFIX)
app.include_router(bindings.router, prefix=PREFIX)
app.include_router(synth.router, prefix=PREFIX)
app.include_router(tasks.router, prefix=PREFIX)
app.include_router(system.router, prefix=PREFIX)
app.include_router(files.static_router)  # /files/{path:path} at root


@app.get("/health")
async def health():
    """健康检查：compose 的 healthcheck 打这个根路径。

    顺带回显当前生效的存储 / 进度后端，便于一眼判断容器用的是不是完整栈。
    """
    return ok({
        "status": "ok",
        "poc_mode": settings.poc_mode,
        "storage_backend": settings.storage_backend,
        "progress_backend": settings.progress_backend,
        "database": settings.database_url.split("://")[0],
    })
