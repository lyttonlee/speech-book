from __future__ import annotations

import uuid

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
                      vtype: str | None = None, owner_id: int | None = None,
                      page: int = 1, page_size: int = 20):
    """音色列表（接口文档 §8.1）。

    Args:
        tags: 标签交集过滤（同时命中才算匹配，音色库顶部标签筛选是多选交集）。
        vtype: builtin / clone 分类。
        owner_id: 只取某用户的克隆音色（配合 vtype=clone 用）。

    Returns:
        (rows, total)
    """
    stmt = select(Voice).where(Voice.status == "available")
    if vtype:
        stmt = stmt.where(Voice.type == vtype)
    if owner_id is not None:
        stmt = stmt.where(Voice.owner_id == owner_id)

    rows_all = (await db.execute(stmt.order_by(Voice.id))).scalars().all()
    # 标签过滤在 Python 侧做：SQLite/JSON 的 contains 语法与 PG 不一致，统一管理更简单
    if tags:
        wanted = set(tags)
        rows_all = [v for v in rows_all if wanted.issubset(set(v.tags_json or []))]

    total = len(rows_all)
    rows = rows_all[(page - 1) * page_size: page * page_size]
    return rows, total


async def update_voice(db: AsyncSession, voice_id: int, data: dict) -> Voice:
    """改音色名称与标签（§8.3）。内置音色也允许改展示名。"""
    v = await get_voice(db, voice_id)
    if "name" in data and data["name"]:
        v.name = data["name"]
    if "tags" in data and data["tags"] is not None:
        v.tags_json = list(data["tags"])
    await db.commit()
    await db.refresh(v)
    return v


async def delete_voice(db: AsyncSession, voice_id: int, *, force: bool = False) -> dict:
    """删除音色（§8.3）。被绑定引用时需 force=true 二次确认。

    Returns:
        {"deleted": voice_id, "unbound": 解绑数量}
    """
    from sqlalchemy import delete as _delete
    from app.models.voice import Bind

    v = await get_voice(db, voice_id)
    refs = (await db.execute(
        select(Bind).where(Bind.voice_id == voice_id)
    )).scalars().all()
    if refs and not force:
        # 先给前端返回影响范围，由用户确认后带 force=true 再删
        return {"need_confirm": True, "refs": len(refs), "deleted": None, "unbound": 0}

    unbound = 0
    if refs:
        await db.execute(_delete(Bind).where(Bind.voice_id == voice_id))
        unbound = len(refs)
    await db.delete(v)
    await db.commit()
    return {"need_confirm": False, "refs": unbound, "deleted": voice_id, "unbound": unbound}


async def preview_voice(db: AsyncSession, voice_id: int, *, text: str,
                        speed: float = 1.0) -> dict:
    """生成音色试听音频（§8.4）。

    用统一 TTSEngine 抽象合成一小段，存到本地存储后返回可播放 url；
    生产替换为真实引擎即可，接口签名不变（业务层只依赖 TTSEngine Protocol）。
    """
    from app.core.storage import public_url, save_bytes
    from app.engines.tts import VoiceRef, get_tts_engine, to_emotion_ir

    v = await get_voice(db, voice_id)
    engine = get_tts_engine()
    vref = VoiceRef(v.id, v.name, v.engine, v.engine_voice_id, timbre_of(v))
    # 试听统一用中性情绪，语速由入参控制（粗映射到 EmotionIR）
    ir = to_emotion_ir("neutral", 50)
    ir.speed = float(speed)
    wav = engine.synthesize(text or v.name, vref, ir)

    # 用 uuid 而非 hash 做文件名：hash(str) 受 PYTHONHASHSEED 影响跨进程不稳定
    rel = f"preview/{v.id}_{uuid.uuid4().hex[:8]}.wav"
    save_bytes(rel, wav)
    return {
        "audio_url": public_url(rel),
        "duration": round(len(wav) / 32000.0, 2),  # 16kHz 16bit 单声道 ≈ 32000 B/s
    }


# ------------------------------------------------------------ 音色标签管理


async def list_tags(db: AsyncSession, *, scope: str | None = None,
                    work_id: int | None = None) -> list[dict]:
    """音色标签列表（§8.5），带上被多少音色使用的计数。"""
    from app.models.voice import VoiceTag

    stmt = select(VoiceTag)
    if scope:
        stmt = stmt.where(VoiceTag.scope == scope)
    if work_id is not None:
        stmt = stmt.where(VoiceTag.work_id == work_id)
    tags = (await db.execute(stmt.order_by(VoiceTag.id))).scalars().all()
    return [{
        "id": t.id, "dim": t.dim, "value": t.value, "group": t.group,
        "scope": t.scope, "color": t.color, "usage_count": t.usage_count,
    } for t in tags]


async def create_tag(db: AsyncSession, *, dim: str, value: str, group: str | None = None,
                     scope: str = "global", work_id: int | None = None,
                     owner_id: int | None = None, color: str | None = None) -> dict:
    """新建音色标签（音色库「标签管理」弹窗的新建入口）。"""
    from app.models.voice import VoiceTag

    tag = VoiceTag(dim=dim, value=value, group=group, scope=scope,
                   work_id=work_id, owner_id=owner_id, color=color)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "dim": tag.dim, "value": tag.value}


async def update_tag(db: AsyncSession, tag_id: int, data: dict) -> dict:
    """重命名或修改标签配色（§8.5 PATCH /voice-tags/{id}）。"""
    from app.models.voice import VoiceTag

    tag = await db.get(VoiceTag, tag_id)
    if not tag:
        raise NotFound("标签不存在")
    if "value" in data and data["value"]:
        tag.value = data["value"]
    if "dim" in data and data["dim"]:
        tag.dim = data["dim"]
    if "color" in data:
        tag.color = data["color"]
    if "group" in data:
        tag.group = data["group"]
    await db.commit()
    return {"id": tag.id, "value": tag.value, "dim": tag.dim}


async def delete_tag(db: AsyncSession, tag_id: int) -> None:
    """删除标签；同时从所有音色的 tags 里摘掉它，避免留下悬空引用。"""
    from app.models.voice import VoiceTag

    tag = await db.get(VoiceTag, tag_id)
    if not tag:
        raise NotFound("标签不存在")
    # 摘除所有音色上的该标签
    voices = (await db.execute(select(Voice))).scalars().all()
    for v in voices:
        tags = list(v.tags_json or [])
        if tag.value in tags:
            tags.remove(tag.value)
            v.tags_json = tags
    await db.delete(tag)
    await db.commit()


# -------------------------------------------------------------- 声音克隆


# 公众人物禁克隆关键词库（生产应换成可运营配置表 + 定期更新）
BANNED_KEYWORDS = ["国家领导人", "明星", "演员", "歌手", "主持人", "配音演员"]


async def submit_clone(db: AsyncSession, user, *, name: str,
                       consent_doc_url: str = "") -> dict:
    """提交声音克隆（§9.1），前置合规校验后创建任务。

    校验顺序（接口文档 §9）：
    1. 实名认证通过（realname_verified）
    2. 已签署授权书（consent_doc_url 非空）
    3. 声纹核验为本人（voiceprint_checked）
    4. 未命中公众人物禁克隆关键词库 → BANNED_PERSON

    Returns:
        {"task_id", "voice_id", "status"}
    """
    from app.core.errors import BannedPerson, ComplianceFailed
    from app.models.task import Task

    if not user.realname_verified:
        raise ComplianceFailed("请先完成实名认证")
    if not consent_doc_url:
        raise ComplianceFailed("请上传并签署声音授权书")
    if not user.voiceprint_checked:
        raise ComplianceFailed("请先完成声纹核验（需本人朗读指定语句）")
    for kw in BANNED_KEYWORDS:
        if kw in (name or ""):
            raise BannedPerson(f"音色名含敏感词：{kw}")

    task = Task(work_id=None, type="clone", status="pending",
                payload_json={"name": name, "consent_doc_url": consent_doc_url})
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 先落一条 pending 的克隆音色，任务完成后由 worker 置为 available
    voice = Voice(owner_id=user.id, name=name, type="clone", engine="stub",
                  tags_json=["我的克隆"], status="pending",
                  engine_voice_id=f"clone-{task.id}")
    db.add(voice)
    await db.commit()
    await db.refresh(voice)

    from app.services import task_service
    if hasattr(task_service, "dispatch_clone"):
        await task_service.dispatch_clone(db, task)

    return {"task_id": task.id, "voice_id": voice.id, "status": "pending"}


async def clone_status(db: AsyncSession, task_id: str) -> dict:
    """克隆任务状态（§9.2）。"""
    from app.models.task import Task

    task = await db.get(Task, task_id)
    if not task or task.type != "clone":
        raise NotFound("克隆任务不存在")
    voice = (await db.execute(
        select(Voice).where(Voice.engine_voice_id == f"clone-{task_id}")
    )).scalar_one_or_none()
    return {
        "status": task.status,
        "progress": task.progress,
        "voice_id": voice.id if voice else None,
        "reject_reason": task.error,
    }


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


def to_voice_row(v: Voice) -> dict:
    """音色 → 列表/卡片一行（§8.1）。

    `usage_count` 统计有多少条绑定引用了该音色，音色库用它排序与
    删除前的「影响范围提示」。
    """
    from app.models.voice import Bind

    usage = getattr(v, "_usage_cache", None)
    return {
        "id": v.id,
        "name": v.name,
        "type": v.type,
        "engine": v.engine,
        "tags": list(v.tags_json or []),
        "status": v.status,
        "usage_count": usage if usage is not None else 0,
        "owner_id": v.owner_id,
    }


def to_voice_detail(v: Voice) -> dict:
    """音色 → 详情（§8.2），额外暴露引擎侧参数供调试与替换底座时用。"""
    row = to_voice_row(v)
    row.update({
        "engine_voice_id": v.engine_voice_id,
        "source": v.type,          # builtin / clone
        "sample_rate": 16000,      # POC StubTTS 固定采样率；生产按引擎能力返回
    })
    return row


async def attach_usage_counts(db: AsyncSession, voices: list[Voice]) -> list[dict]:
    """给一批音色补 usage_count（被多少条绑定引用）。

    一次 group by 查完再挂缓存属性，避免每张卡单独查一次导致 N+1。
    """
    from app.models.voice import Bind

    counts = (await db.execute(
        select(Bind.voice_id, func.count(Bind.id)).group_by(Bind.voice_id)
    )).all()
    cmap = {vid: int(c) for vid, c in counts}
    out = []
    for v in voices:
        v._usage_cache = cmap.get(v.id, 0)  # 临时挂载，to_voice_row 里读取
        out.append(to_voice_row(v))
    return out
