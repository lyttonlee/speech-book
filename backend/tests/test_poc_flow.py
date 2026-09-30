"""POC end-to-end: parse + sample synthesis (offline, no external deps)."""
from sqlalchemy import select

from app.core.db import SessionLocal, init_db
from app.core.storage import read_bytes
from app.engines.llm.parser import split_chapters
from app.models.parse import Chapter, Role, Segment
from app.models.task import Task
from app.models.work import Work
from app.services.parse_service import run_parse
from app.services.synth_service import run_synth
from app.services.user_service import register
from app.services.work_service import create_work


SAMPLE = (
    "第一章\n"
    "张三说：“你好啊，好久不见。”\n"
    "李四回答：“你也好，最近可好？”\n"
    "第二章\n"
    "她心中一阵难过……\n"
    "“我们走吧。”他说道。\n"
)


async def test_parse_and_sample_synth():
    await init_db()
    async with SessionLocal() as db:
        from app.services.voice_service import seed_voices
        await seed_voices(db)

        user = await register(db, "poc@test.com", "password123", "poc")
        work = await create_work(db, user.id, {"name": "POC 测试", "author": "tester"})

        for i, (title, body) in enumerate(split_chapters(SAMPLE)):
            db.add(Chapter(work_id=work.id, order=i, title=title, text=body))
        await db.commit()

        parse_task = Task(work_id=work.id, type="parse", status="pending", payload_json={})
        db.add(parse_task)
        await db.commit()
        await db.refresh(parse_task)
        await run_parse(db, parse_task, lambda *a, **k: None)

        segs = (await db.execute(select(Segment))).scalars().all()
        assert len(segs) > 0, "应解析出片段"
        roles = (await db.execute(select(Role))).scalars().all()
        assert any(r.name == "张三" for r in roles), "应识别说话人张三"
        w = await db.get(Work, work.id)
        assert w.status == "pending_review"

        synth_task = Task(work_id=work.id, type="synth", status="pending",
                         payload_json={"scope": "sample"})
        db.add(synth_task)
        await db.commit()
        await db.refresh(synth_task)
        await run_synth(db, synth_task, lambda *a, **k: None)

        assert synth_task.result_ref and synth_task.result_ref.endswith(".wav")
        rel = synth_task.result_ref.replace("/files/", "")
        data = read_bytes(rel)
        assert data[:4] == b"RIFF", "应生成有效 WAV"
        assert len(data) > 44, "WAV 应有音频数据"
