"""工作空间端到端冒烟测试（对应 design/workspace.html 前端要用的全部接口）。

链路：注册登录 → 建作品 → 上传文本 → 解析 → 角色/绑定 → 校对改片段
→ 关系图（自动推导 + 人工改）→ 修改留痕 → 版本快照与回滚
→ 全景 overview → 合成样章 → 音频资产 → 导出 → 音色库与合规。

用 httpx AsyncClient + ASGITransport 直连 ASGI app（不起端口），
在同一个 event loop 里跑，因此 POC 的 `asyncio.create_task` 后台任务能被正常调度。
"""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionLocal, init_db
from app.main import app
from app.services.voice_service import seed_voices

# 测试用正文：两章、含旁白/对话/心理，能解析出说话人
SAMPLE = (
    "第一章 相遇\n"
    "张三说：“你好啊，好久不见。”\n"
    "李四回答：“你也好，最近可好？”\n"
    "第二章 心事\n"
    "她心中一阵难过……\n"
    "“我们走吧。”他说道。\n"
)

API = "/api/v1"


def unwrap(resp):
    """校验统一信封并把 data 取出来（docs §1.3）。"""
    body = resp.json()
    assert body.get("code") == "OK", f"接口返回异常: {body}"
    return body.get("data")


@pytest.fixture()
async def client():
    """准备数据库 + 内置音色，返回带登录态的 HTTP 客户端。"""
    await init_db()
    async with SessionLocal() as db:
        await seed_voices(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 注册（已存在则忽略）后登录，拿到 JWT
        await ac.post(f"{API}/auth/register",
                      json={"email": "ws@test.com", "password": "pwd12345", "nickname": "ws"})
        login = await ac.post(f"{API}/auth/login",
                              json={"email": "ws@test.com", "password": "pwd12345"})
        token = unwrap(login)["access_token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac


async def _wait_task(client, task_id: str, timeout: float = 15.0):
    """轮询等待后台任务跑到终态（POC 是进程内 asyncio 任务）。"""
    for _ in range(int(timeout / 0.2)):
        data = unwrap(await client.get(f"{API}/tasks/{task_id}"))
        if data["status"] in ("success", "failed", "partial"):
            return data
        await asyncio.sleep(0.2)
    raise AssertionError(f"任务 {task_id} 超时未完成")


async def test_workspace_end_to_end(client):
    # ---------- 1. 作品与文本 ----------
    work = unwrap(await client.post(f"{API}/works", json={"name": "雾港夜航", "author": "佚名"}))
    work_id = work["id"]
    merged = unwrap(await client.post(
        f"{API}/works/{work_id}/files/merge",
        json={"content": SAMPLE, "filename": "book.txt"},
    ))
    assert merged["chapter_count"] >= 2, "应至少切出两章"

    # ---------- 2. 解析 ----------
    parse = unwrap(await client.post(f"{API}/works/{work_id}/parse"))
    await _wait_task(client, parse["task_id"])
    detail = unwrap(await client.get(f"{API}/works/{work_id}"))
    assert detail["status"] == "pending_review", "解析完应进入待校对"

    roles = unwrap(await client.get(f"{API}/works/{work_id}/roles"))["items"]
    assert roles, "应解析出角色"

    # ---------- 3. 声纹绑定 ----------
    voices = unwrap(await client.get(f"{API}/voices"))["items"]
    assert voices, "应有内置音色"
    applied = unwrap(await client.put(
        f"{API}/works/{work_id}/bindings",
        json={"items": [{"role_id": 0, "voice_id": voices[0]["id"], "params": {"speed": 1.0}}]},
    ))
    assert applied["applied"] >= 1

    # ---------- 4. 校对：改单个片段 / 批量改 ----------
    board = unwrap(await client.get(f"{API}/works/{work_id}/proofread"))
    segs = board["paragraphs"][0]["segments"] if board["paragraphs"] else []
    assert segs, "应有可校对片段"
    seg_id = segs[0]["id"]

    patched = unwrap(await client.patch(
        f"{API}/works/{work_id}/segments/{seg_id}", json={"emotion": "happy", "intensity": 80}
    ))
    assert patched["changes"] == 2, "情绪与强度两处都应留痕"

    batch = unwrap(await client.post(
        f"{API}/works/{work_id}/segments/batch",
        json={"ids": [seg_id], "patch": {"type": "dialogue"}},
    ))
    assert batch["applied"] == 1

    # ---------- 5. 关系图：自动推导 + 人工新增 ----------
    derived = unwrap(await client.post(f"{API}/works/{work_id}/graph/derive"))
    assert derived["total"] >= 1, "共现应推导出至少一条边"

    graph_before = unwrap(await client.get(f"{API}/works/{work_id}/graph"))
    assert graph_before["edges"], "关系图应有边"

    role_a, role_b = roles[0]["id"], roles[-1]["id"]
    if role_a != role_b:
        upserted = unwrap(await client.put(
            f"{API}/works/{work_id}/graph",
            json={"from_role_id": role_a, "to_role_id": role_b,
                  "label": "同事", "weight": 0.55},
        ))
        assert upserted["source"] == "manual", "人工新增的边应升为强关系"
        assert upserted["kind"] == "mate", "「同事」应命中同伴类"

    # ---------- 6. 修改留痕 ----------
    edits = unwrap(await client.get(f"{API}/works/{work_id}/edits"))["items"]
    assert any(e["field"] in ("emotion", "intensity") for e in edits), "片段改动应留痕"

    # ---------- 7. 版本快照 + 整体回滚 ----------
    snap = unwrap(await client.post(
        f"{API}/works/{work_id}/snapshots", json={"label": "绑定完成后存档"}
    ))
    assert snap["version"] >= 1

    restored = unwrap(await client.post(
        f"{API}/works/{work_id}/snapshots/{snap['id']}/restore",
    ))
    assert restored["restored"] == snap["id"]

    # ---------- 8. 全景 overview（工作空间首屏） ----------
    ov = unwrap(await client.get(f"{API}/works/{work_id}/overview"))
    assert len(ov["pipeline"]) == 6, "流水线应为六段"
    assert len(ov["metrics"]) == 6, "解析汇总应为六项指标"
    assert ov["cast"]["compliance"]["realname_verified"] is False, "未实名时合规位应为假"
    assert ov["graph"]["nodes"], "全景应带回关系图节点"
    assert ov["chapters"], "全景应带回章节树"

    # ---------- 9. 合成样章 → 音频资产 ----------
    synth = unwrap(await client.post(
        f"{API}/works/{work_id}/synthesize", json={"scope": "sample"}
    ))
    await _wait_task(client, synth["task_id"])
    reindexed = unwrap(await client.get(f"{API}/works/{work_id}/assets/reindex"))
    assert reindexed["total"] >= 1, "合成产物应登记成音频资产"

    # ---------- 10. 导出 ----------
    exported = unwrap(await client.post(
        f"{API}/works/{work_id}/export",
        json={"format": "mp3", "with_subtitle": True, "subtitle_fmt": "srt"},
    ))
    assert exported["url"], "导出应产出链接"
    history = unwrap(await client.get(f"{API}/works/{work_id}/export"))["items"]
    assert history and history[0]["format"] == "mp3"

    # ---------- 11. 音色库：试听 / 标签 / 克隆合规 ----------
    previewed = unwrap(await client.post(
        f"{API}/voices/{voices[0]['id']}/preview", json={"text": "试听一下", "speed": 1.0}
    ))
    assert previewed["audio_url"], "试听应产出音频地址"

    tag = unwrap(await client.post(
        f"{API}/voices/tags", json={"dim": "气质", "value": "温柔", "color": "#38bdf8"}
    ))
    assert tag["id"]
    assert unwrap(await client.get(f"{API}/voices/tags"))["total"] >= 1

    # 未实名/未声纹 → 克隆应被合规拦截（422）
    resp = await client.post(f"{API}/voices/clone",
                             json={"name": "我的声音", "consent_doc_url": "http://x/consent.pdf"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "CLONE_COMPLIANCE_FAILED"

    # 走完实名 + 声纹后应能提交克隆
    assert unwrap(await client.post(
        f"{API}/auth/realname",
        json={"real_name": "测试", "id_card_no": "123456", "consent_doc_url": "http://x/c.pdf"},
    ))["realname_verified"] is True
    assert unwrap(await client.post(f"{API}/auth/voiceprint"))["voiceprint_checked"] is True
    clone = unwrap(await client.post(
        f"{API}/voices/clone", json={"name": "我的声音", "consent_doc_url": "http://x/c.pdf"}
    ))
    assert clone["task_id"], "合规通过后应能提交克隆任务"


async def test_work_list_has_summary(client):
    """Dashboard 作品卡要带三项摘要指标（DESIGN_SPEC §7b.1）。"""
    work = unwrap(await client.post(f"{API}/works", json={"name": "摘要测试"}))
    data = unwrap(await client.get(f"{API}/works"))
    row = next(r for r in data["items"] if r["id"] == work["id"])
    assert {"progress", "bound_roles", "total_roles", "audio_minutes"} <= set(row["summary"])


async def test_segment_revert_to_ai_value(client):
    """改过的片段应能一键还原为 AI 原值，并留下 revert 留痕。"""
    work = unwrap(await client.post(f"{API}/works", json={"name": "回滚测试"}))
    work_id = work["id"]
    await client.post(f"{API}/works/{work_id}/files/merge", json={"content": SAMPLE})
    parse = unwrap(await client.post(f"{API}/works/{work_id}/parse"))
    await _wait_task(client, parse["task_id"])

    board = unwrap(await client.get(f"{API}/works/{work_id}/proofread"))
    seg = board["paragraphs"][0]["segments"][0]
    old_emotion = seg["emotion"]

    await client.patch(f"{API}/works/{work_id}/segments/{seg['id']}",
                       json={"emotion": "angry"})
    reverted = unwrap(await client.post(
        f"{API}/works/{work_id}/segments/{seg['id']}/revert", json={"field": "emotion"}
    ))
    assert "emotion" in reverted["reverted"]
    assert reverted["segment"]["emotion"] == old_emotion, "应还原到 AI 原情绪"
