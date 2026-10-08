"""人物关系图路由（workspace.html `#graph` 区块）。

支撑设计图要求的「可编辑关系图」：
- 点节点看画像、改标签；
- 每条关系可改类型、调强度、删除、新增；
- 一键恢复自动推导（`derive`）。

路由注册顺序：`/graph/derive` 必须写在 `/graph/{relation_id}` **之前**，
否则 "derive" 会被当成 int 型的 relation_id 触发 422。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.response import ok
from app.core.security import get_current_user
from app.models.user import User
from app.services import graph_service, work_service

router = APIRouter(prefix="/works/{work_id}/graph", tags=["graph"])


@router.get("")
async def get_graph(work_id: int, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """整张关系图：nodes（角色）+ edges（关系），前端直接渲染 SVG。"""
    await work_service.get_owned(db, work_id, user.id)
    graph = await graph_service.to_graph(db, work_id)
    return ok(graph)


@router.post("/derive")
async def derive(work_id: int, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """从角色共现自动推导关系边（source=auto，前端显示虚线待确认）。

    已有的人工确认边（source=manual）不会被覆盖。
    """
    await work_service.get_owned(db, work_id, user.id)
    res = await graph_service.derive_relations(db, work_id)
    return ok(res)


@router.put("")
async def upsert(work_id: int, body: dict, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """新增或修改一条关系边。

    body = { id?, from_role_id, to_role_id, label, kind?, weight, source? }
    修改后 source 抬升为 manual，前端从虚线变实线（已确认强关系）。
    """
    await work_service.get_owned(db, work_id, user.id)
    rel = await graph_service.upsert_relation(
        db, work_id,
        relation_id=body.get("id"),
        from_role_id=int(body.get("from_role_id", 0)),
        to_role_id=int(body.get("to_role_id", 0)),
        label=body.get("label", ""),
        kind=body.get("kind"),
        weight=float(body.get("weight", 0.5)),
        source=body.get("source", "manual"),
    )
    return ok({"id": rel.id, "label": rel.label, "kind": rel.kind,
               "weight": rel.weight, "source": rel.source})


@router.delete("/{relation_id}")
async def delete_edge(work_id: int, relation_id: int,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """删除一条关系边（破坏性操作，前端已红色 + 二次确认）。"""
    await work_service.get_owned(db, work_id, user.id)
    await graph_service.delete_relation(db, work_id, relation_id)
    return ok({"deleted": relation_id})
