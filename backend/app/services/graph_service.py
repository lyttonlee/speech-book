"""人物关系图服务（workspace.html `#graph` 区块）。

对应设计图约定（DESIGN_SPEC §5.3b / §7b.2）：
- 图 = 节点（复用 `Role`，旁白为虚拟节点 role_id=0）+ 边（`Relation`）；
- `kind` 决定配色（旁白叙述 / 亲属 / 同伴 / 其他），`weight` 决定连线线宽
  （前端：线宽 = weight，虚线 = source=auto 待确认）；
- 人工确认过的边 `source=manual` 升为强关系，参与音色推荐排序权重。

本模块提供三类能力：
1. 读写边（人工新增 / 改类型 / 调强度 / 删除）；
2. 从文本共现自动推导边（M2 关系图谱的最小可用实现，source=auto）；
3. 汇总整张图给工作空间「解析内容汇总」里的关系图缩略使用。
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.graph import RELATION_KINDS, Relation
from app.models.parse import Chapter, Role, Segment

# 亲属类关系关键词 → kind=kinship（命中即标为亲属关系）
KIN_WORDS = ["母亲", "父亲", "妈妈", "爸爸", "妻子", "丈夫", "妹妹", "哥哥",
             "姐姐", "弟弟", "女儿", "儿子", "女友", "男友", "老师", "师父"]
# 同伴类关系关键词 → kind=mate
MATE_WORDS = ["同事", "同学", "朋友", "搭档", "队友", "伙伴", "室友", "邻居"]

# 自动推导时的最小共现次数：同一章节里出现 ≥2 次才认为有关系
DERIVE_MIN_CO_OCCURRENCE = 2


def normalize_pair(a: int, b: int) -> tuple[int, int]:
    """把一对角色规范化成 (小 id, 大 id)。

    关系边只存一个方向，避免 (3,7) 和 (7,3) 被当成两条边渲染成两次连线。
    """
    return (a, b) if a <= b else (b, a)


def guess_kind(label: str) -> str:
    """根据关系文案猜测语义类型（亲属 / 同伴 / 旁白叙述 / 其他）。

    用于前端把人工输入的关系文案（如「妻子」）落到具体配色上。
    """
    if not label:
        return "other"
    for w in KIN_WORDS:
        if w in label:
            return "kinship"
    for w in MATE_WORDS:
        if w in label:
            return "mate"
    return "other"


async def list_relations(db: AsyncSession, work_id: int) -> list[Relation]:
    """列出某作品的全部关系边（按 id 正序，前端按此顺序渲染）。"""
    rows = (await db.execute(
        select(Relation).where(Relation.work_id == work_id).order_by(Relation.id)
    )).scalars().all()
    return list(rows)


async def to_graph(db: AsyncSession, work_id: int) -> dict:
    """把角色 + 关系边汇总成前端可直接渲染的图结构（含关系图缩略）。

    返回：
    {
      "nodes": [{id, name, level, line_count, aliases, color_hint}],
      "edges": [{id, from, to, label, kind, weight, source}]
    }
    `color_hint` 取角色画像 `profile.color`（JSON 里可预置），前端映射节点配色。
    """
    roles = (await db.execute(
        select(Role).where(Role.work_id == work_id).order_by(Role.id)
    )).scalars().all()

    nodes: list[dict] = []
    for r in roles:
        profile = r.profile_json or {}
        nodes.append({
            "id": r.id,
            "name": r.name,
            "level": r.level,
            "aliases": r.aliases or [],
            "line_count": 0,
            "color_hint": profile.get("color", ""),
        })

    edges = []
    for e in await list_relations(db, work_id):
        edges.append({
            "id": e.id,
            "from": e.from_role_id,
            "to": e.to_role_id,
            "label": e.label,
            "kind": e.kind,
            "weight": e.weight,
            "source": e.source,
        })

    return {"nodes": nodes, "edges": edges}


async def upsert_relation(
    db: AsyncSession,
    work_id: int,
    *,
    relation_id: int | None = None,
    from_role_id: int,
    to_role_id: int,
    label: str = "",
    kind: str | None = None,
    weight: float = 0.5,
    source: str = "manual",
) -> Relation:
    """新增或更新一条关系边。

    - 传 `relation_id` 走更新（改类型 / 调强度 / 改文案，同时把 source 抬到 manual
      表示「人工确认」，前端从虚线变实线）；
    - 不传则新建，按 (from, to) 规范化后去重，已存在则直接覆盖参数而不是插重复边。
    """
    a, b = normalize_pair(int(from_role_id), int(to_role_id))
    if a == b:
        raise NotFound("关系不能指向自己")

    if relation_id:
        rel = await db.get(Relation, relation_id)
        if not rel or rel.work_id != work_id:
            raise NotFound("关系不存在")
    else:
        rel = (await db.execute(
            select(Relation).where(
                Relation.work_id == work_id,
                Relation.from_role_id == a,
                Relation.to_role_id == b,
            )
        )).scalar_one_or_none()
        if not rel:
            rel = Relation(work_id=work_id, from_role_id=a, to_role_id=b)
            db.add(rel)

    rel.label = label or rel.label
    rel.kind = kind or rel.kind or guess_kind(rel.label)
    if rel.kind not in RELATION_KINDS:
        rel.kind = "other"
    rel.weight = max(0.0, min(1.0, float(weight)))
    # 人工编辑过的边一律升为 manual（虚线 → 实线）
    rel.source = source if source == "auto" else "manual"
    rel.confidence = 1.0 if rel.source == "manual" else (rel.confidence or 0.5)

    await db.commit()
    await db.refresh(rel)
    return rel


async def delete_relation(db: AsyncSession, work_id: int, relation_id: int) -> None:
    """删除一条关系边（破坏性操作，前端已二次确认）。"""
    rel = await db.get(Relation, relation_id)
    if not rel or rel.work_id != work_id:
        raise NotFound("关系不存在")
    await db.delete(rel)
    await db.commit()


async def derive_relations(db: AsyncSession, work_id: int) -> dict:
    """从「同一章节里共同出现的角色」自动推导关系边（source=auto，前端显示虚线）。

    规则（M2 关系图谱的最小实现）：
    1. 按章节聚合出现过的角色集合；
    2. 同一章里 ≥ `DERIVE_MIN_CO_OCCURRENCE` 次共同出现的角色对生成一条边；
    3. 边文案取双方角色名的组合，kind 用 `guess_kind` 猜；
    4. 已存在的同类边（source=manual）不覆盖，避免抹掉人工确认结果。

    Returns:
        {"derived": 新增边数, "total": 当前总边数}
    """
    # 取本书全部片段（顺带 join 章节以过滤 work_id）
    segs = (await db.execute(
        select(Segment)
        .join(Chapter, Segment.chapter_id == Chapter.id)
        .where(Chapter.work_id == work_id)
    )).scalars().all()

    # {chapter_id: {role_id: 命中次数}}
    chapter_roles: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for s in segs:
        if s.speaker_role_id:
            chapter_roles[s.chapter_id][s.speaker_role_id] += 1

    existing = {normalize_pair(e.from_role_id, e.to_role_id) for e in await list_relations(db, work_id)}

    # 先一次性取好角色名，避免在循环里 await 查询（也能省掉重复查库）
    all_role_ids = {rid for hits in chapter_roles.values() for rid in hits}
    name_map = {rid: await _role_name(db, rid) for rid in all_role_ids}

    created = 0
    for _ch_id, role_hits in chapter_roles.items():
        ids = sorted(role_hits)
        for i, x in enumerate(ids):
            for y in ids[i + 1:]:
                pair = (x, y)
                if pair in existing:
                    continue
                rel = Relation(
                    work_id=work_id,
                    from_role_id=pair[0],
                    to_role_id=pair[1],
                    label=f"{name_map.get(x, '未知')} 与 {name_map.get(y, '未知')}",
                    kind="mate",
                    weight=min(1.0, 0.3 + 0.1 * min(role_hits[x], role_hits[y])),
                    source="auto",
                    confidence=min(0.9, 0.4 + 0.05 * min(role_hits[x], role_hits[y])),
                )
                db.add(rel)
                existing.add(pair)
                created += 1

    if created:
        await db.commit()
    return {"derived": created, "total": len(existing)}


async def _role_name(db: AsyncSession, role_id: int) -> str:
    """取角色名（补全自动推导边的默认文案）；查不到回退成「未知角色」。"""
    if role_id == 0:
        return "旁白"
    role = await db.get(Role, role_id)
    return role.name if role else "未知角色"
