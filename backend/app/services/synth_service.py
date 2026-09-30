"""POC synth service: sample/full synthesis via the TTS engine abstraction."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import public_url, save_bytes
from app.engines.tts import VoiceRef, concatenate_wav, get_tts_engine, to_emotion_ir
from app.models.parse import Chapter, Segment
from app.models.task import Task
from app.models.voice import Bind, Voice
from app.models.work import Work
from app.services.voice_service import timbre_of

NARRATOR_TAG = "旁白"


async def run_synth(db: AsyncSession, task: Task, publish) -> None:
    work_id = task.work_id
    payload = task.payload_json or {}
    scope = payload.get("scope", "sample")
    chapter_ids = (payload.get("range") or {}).get("chapter_ids")

    stmt = select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    if scope == "sample":
        stmt = stmt.limit(2)
    elif scope == "range" and chapter_ids:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    chapters = (await db.execute(stmt)).scalars().all()

    # 绑定与音色
    binds = (await db.execute(select(Bind).where(Bind.work_id == work_id))).scalars().all()
    bind_map = {b.role_id: b for b in binds}
    voices = (await db.execute(select(Voice))).scalars().all()
    voice_by_id = {v.id: v for v in voices}
    narrator = next((v for v in voices if NARRATOR_TAG in (v.tags_json or [])), None) or voices[0]
    default_voice = next((v for v in voices if v is not narrator), voices[0])

    engine = get_tts_engine()

    segs = (await db.execute(
        select(Segment)
        .where(Segment.chapter_id.in_([c.id for c in chapters]))
        .order_by(Segment.chapter_id, Segment.order)
    )).scalars().all()

    total = len(segs)
    publish(task.id, "progress", {"progress": 10, "stage": f"准备合成 {total} 个片段"})

    wavs: list[bytes] = []
    done = 0
    for seg in segs:
        if seg.type in ("narration", "psychology"):
            b = bind_map.get(0)
            voice = voice_by_id.get(b.voice_id) if (b and b.voice_id) else narrator
        else:
            role_id = seg.speaker_role_id
            b = bind_map.get(role_id) if role_id else None
            voice = voice_by_id.get(b.voice_id) if (b and b.voice_id) else default_voice

        ir = to_emotion_ir(seg.emotion, seg.intensity)
        # 能力探测降级：stub 不支持 style_tag，传递时忽略即可（引擎内部只用 speed/pitch/volume）
        vref = VoiceRef(voice.id, voice.name, voice.engine, voice.engine_voice_id, timbre_of(voice))
        wavs.append(engine.synthesize(seg.text, vref, ir))

        done += 1
        if done % 5 == 0 or done == total:
            publish(task.id, "progress", {
                "progress": int(20 + 70 * done / max(1, total)),
                "stage": f"合成片段 {done}/{total}",
            })

    final = concatenate_wav(wavs)
    rel = f"synth/{task.id}.wav"
    save_bytes(rel, final)
    task.result_ref = public_url(rel)
    await db.commit()

    work = await db.get(Work, work_id)
    if work:
        work.status = "synth_done"
        await db.commit()

    publish(task.id, "progress", {"progress": 100, "stage": "合成完成"})
