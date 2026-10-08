"""工作空间全景服务（workspace.html 首屏 `/works/{id}/overview`）。

设计图把「一本书做到哪了 / 解析出了什么 / 已经配好多少音」压到一页，
服务端需要一次给全，避免前端发十几个请求拼页面。本模块返回 7 组数据：

1. `work`          —— 作品头（封面、标题、状态、整体完成度 `.ring`）
2. `pipeline`      —— 6 段制作流水线状态与耗时（上传/解析/校对/声纹绑定/配音/导出）
3. `metrics`       —— 6 项量化指标（解析内容汇总）
4. `cast`          —— 角色总览卡 + 声纹绑定总览 + 克隆合规前置
5. `graph`         —— 关系图缩略（节点 + 边）
6. `chapters`      —— 章节树（每章片段数、状态）
7. `assets`        —— 已制作配音资产 + 最近修改留痕 + 版本快照

状态机口径见 docs/接口文档.md §16.1；流水线六段见 DESIGN_SPEC §5.3b。
"""
from __future__ import annotations

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse import Chapter, Role, Segment
from app.models.user import User
from app.models.voice import Bind, Voice
from app.models.work import Work
from app.services import asset_service, audit_service, graph_service
from app.services.work_service import get_owned

# 流水线六段（顺序即前端 pipeline 展示顺序）
PIPELINE_STAGES = [
    {"key": "upload", "label": "上传文本"},
    {"key": "parse", "label": "解析"},
    {"key": "proofread", "label": "人工校对"},
    {"key": "cast", "label": "声纹绑定"},
    {"key": "synth", "label": "合成配音"},
    {"key": "export", "label": "导出"},
]

# 作品状态 → 流水线六段各自处于什么状态（done/active/idle）
# 对应状态机：草稿→文本已上传→解析中→待校对→校对完成→合成中→合成完成→导出中→已完成
STATUS_TO_STAGE = {
    "draft": {"upload": "idle", "parse": "idle", "proofread": "idle",
              "cast": "idle", "synth": "idle", "export": "idle"},
    "text_uploaded": {"upload": "done", "parse": "active", "proofread": "idle",
                      "cast": "idle", "synth": "idle", "export": "idle"},
    "parsing": {"upload": "done", "parse": "active", "proofread": "idle",
                "cast": "idle", "synth": "idle", "export": "idle"},
    "pending_review": {"upload": "done", "parse": "done", "proofread": "active",
                       "cast": "idle", "synth": "idle", "export": "idle"},
    "review_done": {"upload": "done", "parse": "done", "proofread": "done",
                    "cast": "active", "synth": "idle", "export": "idle"},
    "synthesizing": {"upload": "done", "parse": "done", "proofread": "done",
                     "cast": "done", "synth": "active", "export": "idle"},
    "synth_done": {"upload": "done", "parse": "done", "proofread": "done",
                   "cast": "done", "synth": "done", "export": "idle"},
    "exporting": {"upload": "done", "parse": "done", "proofread": "done",
                  "cast": "done", "synth": "done", "export": "active"},
    "completed": {"upload": "done", "parse": "done", "proofread": "done",
                  "cast": "done", "synth": "done", "export": "done"},
}


def stage_status(work: Work) -> dict[str, str]:
    """根据作品状态推导六段流水线各自的状态（done / active / idle）。"""
    return STATUS_TO_STAGE.get(work.status, STATUS_TO_STAGE["draft"])


def _stage_seconds(work: Work, key: str) -> int:
    """取某段的耗时（秒）。

    优先读 `work.pipeline_json[key].seconds`（任务跑完时回填），
    没有则按状态返回 0 或估算值，前端只做展示不做精确计算。
    """
    pipe = work.pipeline_json or {}
    stage = pipe.get(key) or {}
    if isinstance(stage, dict) and stage.get("seconds") is not None:
        return int(stage["seconds"])
    return 0


def build_pipeline(work: Work) -> list[dict]:
    """生成前端 `.pipeline` 六段数据（含状态、耗时、进度、人工介入入口文案）。

    每个阶段附带 `actions`：设计图要求「不用回到向导页」就能介入，
    所以每段直接给出可执行动作（重跑 / 再校对 / 解绑重选 / 提速 / 预设）。
    """
    statuses = stage_status(work)
    out = []
    for i, st in enumerate(PIPELINE_STAGES):
        key = st["key"]
        pipe = work.pipeline_json or {}
        stage = pipe.get(key) or {}
        out.append({
            "key": key,
            "label": st["label"],
            "status": statuses.get(key, "idle"),
            "index": i,
            "seconds": _stage_seconds(work, key),
            "progress": int(stage.get("progress", 100 if statuses.get(key) == "done" else 0)),
            "actions": STAGE_ACTIONS.get(key, []),
        })
    return out


# 每段的「人工介入」按钮（对应 DESIGN_SPEC §5.3b）
STAGE_ACTIONS = {
    "upload": [{"key": "reupload", "label": "重新上传"}],
    "parse": [{"key": "rerun", "label": "重跑解析"}],
    "proofread": [{"key": "review", "label": "再校对"}],
    "cast": [{"key": "rebind", "label": "解绑重选"}],
    "synth": [{"key": "speedup", "label": "提速合成"}],
    "export": [{"key": "preset", "label": "导出预设"}],
}


def _metrics(chapter_count: int, segment_count: int, role_count: int,
             bound_count: int, asset_seconds: int, low_conf_count: int) -> list[dict]:
    """生成解析内容汇总的 6 项量化指标（前端 `.metrics` 六连卡）。

    tone 决定强调色：hl=主题蓝 / ok=绿 / warn=橙 / danger=红。
    已绑声纹为 0 或存在待复核时转橙红，让用户在列表页就能判断哪本书要动手。
    """
    return [
        {"key": "chapter_count", "label": "章节", "value": chapter_count, "unit": "章", "tone": "hl"},
        {"key": "segment_count", "label": "片段", "value": segment_count, "unit": "条", "tone": "hl"},
        {"key": "role_count", "label": "角色", "value": role_count, "unit": "个", "tone": "hl"},
        {"key": "bound_count", "label": "已绑声纹", "value": bound_count, "unit": f"/{role_count or 0}", "tone": "ok" if bound_count else "warn"},
        {"key": "audio_seconds", "label": "已配音", "value": round(asset_seconds / 60, 1), "unit": "分钟", "tone": "ok" if asset_seconds else "hl"},
        {"key": "low_conf", "label": "待复核", "value": low_conf_count, "unit": "条", "tone": "danger" if low_conf_count else "ok"},
    ]


async def build_overview(db: AsyncSession, work_id: int, user_id: int) -> dict:
    """构建工作空间全景数据（一次返回前端首屏所需的全部区块）。

    Returns:
        dict，字段结构见模块 docstring。
    """
    work = await get_owned(db, work_id, user_id)

    # ---- 1. 角色与绑定 ----
    roles = (await db.execute(
        select(Role).where(Role.work_id == work_id).order_by(Role.id)
    )).scalars().all()
    binds = (await db.execute(
        select(Bind).where(Bind.work_id == work_id)
    )).scalars().all()
    voices = (await db.execute(select(Voice))).scalars().all()
    voice_map = {v.id: v for v in voices}

    bind_by_role = {b.role_id: b for b in binds}
    role_rows = []
    for r in roles:
        b = bind_by_role.get(r.id)
        voice = voice_map.get(b.voice_id) if b and b.voice_id else None
        profile = r.profile_json or {}
        role_rows.append({
            "id": r.id,
            "name": r.name,
            "level": r.level,
            "aliases": r.aliases or [],
            "profile": profile,
            "line_count": await _role_line_count(db, r.id),
            "bound_voice_id": b.voice_id if b else None,
            "bound_voice_name": voice.name if voice else None,
            "params": (b.params_json or {}) if b else {},
            "bound": bool(b and b.voice_id),
        })

    # ---- 2. 章节 / 片段统计 ----
    chapters = (await db.execute(
        select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.order)
    )).scalars().all()
    # 按章节聚合片段数与低置信数（Boolean 在 SQL 里不能直接 sum，先 cast 成整数）
    seg_agg = (await db.execute(
        select(Segment.chapter_id, func.count(Segment.id),
               func.sum(cast(Segment.low_conf, Integer)))
        .where(Segment.chapter_id.in_([c.id for c in chapters]))
        .group_by(Segment.chapter_id)
    )).all()
    seg_map = {cid: (cnt, int(lc or 0)) for cid, cnt, lc in seg_agg}
    total_segments = sum(v[0] for v in seg_map.values())

    chapter_rows = [{
        "id": c.id,
        "title": c.title or f"第 {c.order + 1} 章",
        "order": c.order,
        "segment_count": seg_map.get(c.id, (0, 0))[0],
        "low_conf_count": seg_map.get(c.id, (0, 0))[1],
        "status": "done" if seg_map.get(c.id, (0, 0))[0] else "empty",
    } for c in chapters]

    low_conf_count = sum(v[1] for v in seg_map.values())

    # ---- 3. 音频资产 ----
    assets = await asset_service.list_assets(db, work_id)
    asset_seconds = sum(a.duration for a in assets)

    # ---- 4. 克隆合规前置（用户维度）----
    user = await db.get(User, work.owner_id)
    compliance = {
        "realname_verified": bool(user.realname_verified) if user else False,
        "voiceprint_checked": bool(user.voiceprint_checked) if user else False,
        "banned_keywords_hit": False,  # 生产：比对公众人物禁克隆库
        "watermark_enabled": True,
    }

    # ---- 5. 关系图缩略 ----
    graph = await graph_service.to_graph(db, work_id)

    # ---- 6. 修改留痕 / 版本快照 ----
    logs = await audit_service.list_logs(db, work_id, limit=20)
    snaps = await audit_service.list_snapshots(db, work_id)

    return {
        "work": {
            "id": work.id,
            "name": work.name,
            "author": work.author,
            "type": work.type,
            "lang": work.lang,
            "cover_url": work.cover_url,
            "status": work.status,
            "progress": work.progress,
        },
        "pipeline": build_pipeline(work),
        "metrics": _metrics(
            len(chapters), total_segments, len(role_rows),
            sum(1 for r in role_rows if r["bound"]),
            asset_seconds, low_conf_count,
        ),
        "cast": {
            "roles": role_rows,
            "bindings": [{
                "role_id": b.role_id,
                "role_name": next((r["name"] for r in role_rows if r["id"] == b.role_id), "旁白"),
                "voice_id": b.voice_id,
                "voice_name": voice_map.get(b.voice_id).name if b.voice_id in voice_map else None,
                "params": b.params_json or {},
                "bound": bool(b.voice_id),
            } for b in binds],
            "compliance": compliance,
        },
        "graph": graph,
        "chapters": chapter_rows,
        "assets": [asset_service.to_asset_row(a) for a in assets],
        "edits": [await audit_service.to_diff(log) for log in logs],
        "snapshots": [{
            "id": s.id,
            "version": s.version,
            "label": s.label,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            } for s in snaps],
    }


async def _role_line_count(db: AsyncSession, role_id: int) -> int:
    """统计某角色的台词条数（角色卡上的台词数徽标）。"""
    cnt = (await db.execute(
        select(func.count(Segment.id)).where(Segment.speaker_role_id == role_id)
    )).scalar() or 0
    return int(cnt)
