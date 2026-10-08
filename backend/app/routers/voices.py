"""音色库路由（接口文档 §8 / §9）。

覆盖：列表检索、详情、编辑、删除（带引用影响范围二次确认）、试听、
标签管理、声音克隆提交与状态查询。

**路由顺序很重要**：`/clone`、`/clone/{task_id}`、`/tags` 必须写在
`/voices/{voice_id}` **之前**，否则 "clone" / "tags" 会被当成 int 型的
voice_id 触发 422（FastAPI 按注册顺序匹配）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import voice_service

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("")
async def list_voices_route(
    tags: str | None = Query(None, description="逗号分隔，多选交集"),
    type: str | None = Query(None),
    mine: bool = Query(False, description="只看我的克隆音色"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """音色列表（§8.1）：支持标签交集检索与 builtin/clone 分类。"""
    tag_list = [t for t in (tags or "").split(",") if t] or None
    rows, total = await voice_service.list_voices(
        db, tags=tag_list, vtype=type,
        owner_id=user.id if mine else None, page=page, page_size=page_size,
    )
    return ok({
        "items": await voice_service.attach_usage_counts(db, rows),
        "total": total, "page": page, "page_size": page_size,
    })


# ---------------------------------------------------------------- 克隆


@router.post("/clone")
async def submit_clone(body: dict, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """提交声音克隆（§9.1）。

    前置校验：实名 + 授权书 + 声纹核验（本人）+ 公众人物关键词库；
    未通过抛 422 CLONE_COMPLIANCE_FAILED / BANNED_PERSON。
    """
    res = await voice_service.submit_clone(
        db, user,
        name=body.get("name", ""),
        consent_doc_url=body.get("consent_doc_url", ""),
    )
    return ok(res)


@router.get("/clone/{task_id}")
async def clone_status(task_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """克隆任务状态（§9.2）：status / progress / voice_id / reject_reason。"""
    return ok(await voice_service.clone_status(db, task_id))


# ------------------------------------------------------------ 音色标签


@router.get("/tags")
async def list_tags(scope: str | None = Query(None), work_id: int | None = Query(None),
                    db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """音色标签列表（§8.5），带上使用计数，供标签管理弹窗展示。"""
    rows = await voice_service.list_tags(db, scope=scope, work_id=work_id)
    return ok({"items": rows, "total": len(rows), "page": 1, "page_size": len(rows)})


@router.post("/tags")
async def create_tag(body: dict, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """新建标签（音色库标签管理弹窗，支持 7 色板配色）。"""
    row = await voice_service.create_tag(
        db, dim=body.get("dim", ""), value=body.get("value", ""),
        group=body.get("group"), scope=body.get("scope", "global"),
        work_id=body.get("work_id"), owner_id=user.id, color=body.get("color"),
    )
    return ok(row)


@router.patch("/tags/{tag_id}")
async def update_tag(tag_id: int, body: dict, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """重命名 / 改配色（§8.5）。"""
    return ok(await voice_service.update_tag(db, tag_id, body or {}))


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """删除标签，同时从所有音色上摘除引用。"""
    await voice_service.delete_tag(db, tag_id)
    return ok({"deleted": tag_id})


# ------------------------------------------------------------ 单个音色


@router.get("/{voice_id}")
async def get_voice(voice_id: int, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """音色详情（§8.2）"""
    v = await voice_service.get_voice(db, voice_id)
    return ok(voice_service.to_voice_detail(v))


@router.patch("/{voice_id}")
async def update_voice(voice_id: int, body: dict, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """改音色名称 / 标签（§8.3）。"""
    v = await voice_service.update_voice(db, voice_id, body or {})
    return ok(voice_service.to_voice_row(v))


@router.delete("/{voice_id}")
async def delete_voice(voice_id: int, force: bool = Query(False),
                       db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """删除音色（§8.3）。被绑定引用时返回 {need_confirm: true, refs: n}，
    前端弹二次确认框后带 `?force=true` 再请求一次真正删除。
    """
    return ok(await voice_service.delete_voice(db, voice_id, force=force))


@router.post("/{voice_id}/preview")
async def preview_voice(voice_id: int, body: dict, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """生成试听音频（§8.4）。支持自定义试听文本与语速。"""
    res = await voice_service.preview_voice(
        db, voice_id,
        text=body.get("text", ""),
        speed=float(body.get("speed", 1.0)),
    )
    return ok(res)
