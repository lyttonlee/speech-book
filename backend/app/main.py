"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import (
    AppError,
    app_error_handler,
    unhandled_handler,
    validation_error_handler,
)
from app.core.response import ok
from app.routers import (
    auth,
    bindings,
    files,
    parse,
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
    await init_db()
    async with SessionLocal() as db:
        await seed_voices(db)
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
app.include_router(voices.router, prefix=PREFIX)
app.include_router(bindings.router, prefix=PREFIX)
app.include_router(synth.router, prefix=PREFIX)
app.include_router(tasks.router, prefix=PREFIX)
app.include_router(system.router, prefix=PREFIX)
app.include_router(files.static_router)  # /files/{path:path} at root


@app.get("/health")
async def health():
    return ok({"status": "ok", "poc_mode": settings.poc_mode})
