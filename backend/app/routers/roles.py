from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import role_service, work_service
from app.services.role_service import get_or_create_role

router = APIRouter(prefix="/works/{work_id}/roles", tags=["roles"])


@router.get("")
async def list_roles(work_id: int, level: str | None = None,
                    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    return ok({"items": await role_service.list_roles(db, work_id, level=level), "total": 0, "page": 1, "page_size": 100})


@router.post("", status_code=201)
async def create_role(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    role = await get_or_create_role(db, work_id, body.get("name", "新角色"))
    return ok({"id": role.id, "name": role.name, "level": role.level})


@router.post("/{role_id}/merge")
async def merge_role(work_id: int, role_id: int, body: dict,
                    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    target = await role_service.merge_roles(db, role_id, body.get("source_role_ids", []))
    return ok({"id": target.id, "name": target.name})


@router.get("/{role_id}/stats")
async def role_stats(work_id: int, role_id: int, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """角色台词统计（§7.5）：台词数 / 覆盖章节数 / 平均句长。"""
    await work_service.get_owned(db, work_id, user.id)
    return ok(await role_service.role_stats(db, work_id, role_id))


@router.patch("/{role_id}")
async def update_role(work_id: int, role_id: int, body: dict,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """改角色名 / 级别 / 别名 / 画像（§7.3）。

    降为龙套就是把 level 改成 extra（龙套走默认旁白/群杂，不强制绑音色）。
    每个被改字段都会写一条修改留痕，前端「修改留痕」区块可查 diff 与回滚。
    """
    await work_service.get_owned(db, work_id, user.id)
    role = await role_service.update_role(db, work_id, role_id, body or {}, user.id)
    return ok({"id": role.id, "name": role.name, "level": role.level, "aliases": role.aliases})


@router.delete("/{role_id}")
async def delete_role(work_id: int, role_id: int, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """删除角色（破坏性操作，前端已二次确认）。

    删除后该角色名下的片段会变成未归属（speaker_role_id=NULL），
    需要重新指派说话人，因此前端会提示「台词会变为未归属」。
    """
    await work_service.get_owned(db, work_id, user.id)
    await role_service.delete_role(db, work_id, role_id, user.id)
    return ok({"deleted": role_id})


@router.post("/{role_id}/split")
async def split_role(work_id: int, role_id: int, body: dict,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """拆分角色：把指定片段从原角色拆到新角色（工作空间「角色合并拆分」用）。

    body = { "segment_ids": [...], "new_name": "角色B" }
    """
    await work_service.get_owned(db, work_id, user.id)
    res = await role_service.split_role(
        db, work_id, role_id,
        segment_ids=body.get("segment_ids", []),
        new_name=body.get("new_name", ""),
        user_id=user.id,
    )
    return ok(res)


@router.get("/{role_id}/recommend-voices")
async def recommend(work_id: int, role_id: int, top: int = 5,
                   db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await work_service.get_owned(db, work_id, user.id)
    from app.services.voice_service import list_voices
    rows, _ = await list_voices(db, page_size=top)
    return ok({"items": [{"voice_id": v.id, "name": v.name, "score": 0.9,
                          "matched_tags": v.tags_json} for v in rows], "total": len(rows), "page": 1, "page_size": top})
