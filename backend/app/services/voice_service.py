from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.voice import Voice

# 内置音色（POC 种子）。production 由音色库管理。
_BUILTIN = [
    {"name": "旁白·中性", "type": "builtin", "engine": "stub", "tags": ["旁白"], "timbre": -6},
    {"name": "男声·青年", "type": "builtin", "engine": "stub", "tags": ["男声", "青年"], "timbre": 2},
    {"name": "女声·青年", "type": "builtin", "engine": "stub", "tags": ["女声", "青年"], "timbre": 8},
]


def _count_builtin(db: AsyncSession):
    return db.execute(select(func.count(Voice.id)).where(Voice.type == "builtin"))


async def seed_voices(db: AsyncSession) -> None:
    n = (await db.execute(select(func.count(Voice.id)).where(Voice.type == "builtin"))).scalar_one()
    if n >= len(_BUILTIN):
        return
    for v in _BUILTIN:
        db.add(Voice(
            name=v["name"], type=v["type"], engine=v["engine"],
            tags_json=v["tags"], status="available", engine_voice_id=str(v["timbre"]),
        ))
    await db.commit()


async def list_voices(db: AsyncSession, *, tags: list[str] | None = None,
                      vtype: str | None = None, page: int = 1, page_size: int = 20):
    stmt = select(Voice).where(Voice.status == "available")
    if vtype:
        stmt = stmt.where(Voice.type == vtype)
    rows = (await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all()
    total = (await db.execute(select(func.count(Voice.id)).where(Voice.status == "available"))).scalar_one()
    return rows, total


async def get_voice(db: AsyncSession, voice_id: int) -> Voice:
    v = (await db.execute(select(Voice).where(Voice.id == voice_id))).scalar_one_or_none()
    if not v:
        raise NotFound("音色不存在")
    return v


def timbre_of(voice: Voice) -> float:
    try:
        return float(voice.engine_voice_id)
    except (TypeError, ValueError):
        return (voice.id % 5) * 2 - 4
