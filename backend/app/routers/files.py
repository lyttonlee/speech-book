from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.core.storage import serve
from app.engines.llm.parser import split_chapters
from app.models.parse import Chapter, Segment
from app.models.user import User
from app.models.work import Work
from app.services import work_service

# 业务路由：/works/{work_id}/files
router = APIRouter(prefix="/works/{work_id}/files", tags=["files"])

# 静态文件路由（POC 替代 MinIO 签名 URL），挂在根路径
static_router = APIRouter(tags=["static"])


@router.post("/chunks")
async def upload_chunk(work_id: int, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    # POC 直传文本，分片上传接口占位
    await work_service.get_owned(db, work_id, user.id)
    return ok({"received": 0, "total": 0})


@router.post("/merge")
async def merge(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
               user: User = Depends(get_current_user)):
    """POC 简化：直接接收整段文本内容并切分为章节。生产走分片上传+合并。"""
    await work_service.get_owned(db, work_id, user.id)
    content = body.get("content") or ""
    filename = body.get("filename", "upload.txt")
    chapters = split_chapters(content)
    await db.execute(Chapter.__table__.delete().where(Chapter.work_id == work_id))
    for i, (title, body_text) in enumerate(chapters):
        db.add(Chapter(work_id=work_id, order=i, title=title, text=body_text))
    work = await db.get(Work, work_id)
    if work:
        work.status = "text_uploaded"
        await db.commit()
    return ok({"status": "text_uploaded", "chapter_count": len(chapters), "filename": filename})


@router.get("/text")
async def get_text(work_id: int, chapter_id: int | None = Query(None),
                  db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    stmt = select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    if chapter_id:
        stmt = stmt.where(Chapter.id == chapter_id)
    chapters = (await db.execute(stmt)).scalars().all()
    return ok({
        "chapters": [
            {"id": c.id, "title": c.title, "order": c.order, "paragraphs": [
                {"id": 0, "order": 0, "text": p, "type": "text"}
                for p in [t for t in c.text.split("\n") if t.strip()]
            ]}
            for c in chapters
        ]
    })


@router.patch("/chapters/{chapter_id}")
async def patch_chapter(work_id: int, chapter_id: int, body: dict,
                       db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    ch = (await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.work_id == work_id)
    )).scalar_one_or_none()
    if not ch:
        from app.core.errors import NotFound
        raise NotFound("章节不存在")
    if "title" in body:
        ch.title = body["title"]
    await db.commit()
    return ok({"id": ch.id, "title": ch.title})


@router.post("/append")
async def append(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    text = body.get("content") or ""
    last = (await db.execute(
        select(Chapter.order).where(Chapter.work_id == work_id).order_by(Chapter.order.desc()).limit(1)
    )).scalar()
    order = (last or -1) + 1
    ch = Chapter(work_id=work_id, order=order, title=body.get("title", f"第{order+1}章"), text=text)
    db.add(ch)
    await db.commit()
    return ok({"id": ch.id, "order": ch.order})


@static_router.get("/files/{path:path}")
async def serve_file(path: str):
    return serve(path)
