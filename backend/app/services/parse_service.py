"""POC parse service: rule-based segmentation + role dictionary build."""
from __future__ import annotations

from collections import Counter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.llm.parser import llm_enrich, parse_paragraph
from app.engines.moderation import check_text
from app.models.parse import Chapter, Role, Segment
from app.models.task import Task
from app.models.work import Work

# 龙套阈值：台词少于该值的说话人归类为配角；可据语料调整
MAIN_LINE_THRESHOLD = 3


async def run_parse(db: AsyncSession, task: Task, publish) -> None:
    work_id = task.work_id
    work = await db.get(Work, work_id)
    if not work:
        raise RuntimeError("work not found")

    chapters = (await db.execute(
        select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    )).scalars().all()

    publish(task.id, "progress", {"progress": 5, "stage": "开始解析章节"})

    segs_meta: list[tuple[Segment, str | None]] = []
    order = 0
    for ch in chapters:
        paragraphs = [p for p in ch.text.split("\n") if p.strip()]
        for para in paragraphs:
            parsed = llm_enrich(parse_paragraph(para), context=ch.title)
            for ps in parsed:
                check_text(ps.text)  # POC 审核透传；生产据结果拦截
                seg = Segment(
                    chapter_id=ch.id,
                    order=order,
                    type=ps.type,
                    text=ps.text,
                    speaker_name=ps.speaker_name,
                    emotion=ps.emotion,
                    intensity=ps.intensity,
                    confidence=ps.confidence,
                    low_conf=ps.confidence < 0.7,
                )
                db.add(seg)
                segs_meta.append((seg, ps.speaker_name))
                order += 1

    publish(task.id, "progress", {"progress": 40, "stage": f"生成片段 {order} 个，识别说话人"})

    # 角色词典：复用同名角色，禁止每块独立新建
    name_counter = Counter(n for _, n in segs_meta if n)
    role_map: dict[str, int] = {}
    for name, cnt in name_counter.items():
        role = (await db.execute(
            select(Role).where(Role.work_id == work_id, Role.name == name)
        )).scalar_one_or_none()
        if not role:
            role = Role(
                work_id=work_id,
                name=name,
                level="main" if cnt >= MAIN_LINE_THRESHOLD else "supporting",
                aliases=[],
            )
            db.add(role)
            await db.flush()
        role_map[name] = role.id

    for seg, name in segs_meta:
        if name and name in role_map:
            seg.speaker_role_id = role_map[name]

    publish(task.id, "progress", {"progress": 75, "stage": "回写角色绑定"})
    work.status = "pending_review"
    await db.commit()
    publish(task.id, "progress", {"progress": 100, "stage": "解析完成，待校对"})
