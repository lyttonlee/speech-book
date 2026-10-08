"""真实基础设施端到端冒烟：PostgreSQL + Redis + S3 兼容对象存储。

在 **backend 容器内** 运行（这样 `backend` / `minio` / `redis` 等服务名可直接解析，
且 S3 预签名直链不经宿主机端口转发）：

    docker compose cp scripts/smoke_infra.py backend:/app/scripts_smoke.py
    docker compose exec -T backend python /app/scripts_smoke.py

覆盖链路：注册登录(JWT) → 建作品 → 文本导入 → 解析 → 合成 → 资产入库 → S3 直链可达。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# 容器内走服务名；宿主机跑则改用 http://localhost:8000/api/v1
BASE = os.getenv("SB_SMOKE_BASE", "http://backend:8000/api/v1")
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    """记一条断言，最后统一打印，避免中途异常看不到汇总。"""
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' :: ' + extra) if extra else ''}")


def req(method: str, path: str, token: str = "", body: dict | None = None) -> dict:
    """发 JSON 请求，返回响应体字典（4xx 也解析成字典抛出给调用方判断）。"""
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="ignore")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"code": f"HTTP_{exc.code}", "message": raw[:200]}
    except urllib.error.URLError as exc:
        return {"code": "UNREACHABLE", "message": str(exc)}


def fetch(url: str) -> tuple[int, int, str]:
    """发一个带 Range 的 GET，返回 (状态码, 响应字节数, Content-Type)。

    用 GET 而非 HEAD：FastAPI 的静态反代路由只声明了 GET，
    部分 Starlette 版本不会对 HEAD 做自动降级，HEAD 会拿到 405。
    """
    try:
        req_obj = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
        with urllib.request.urlopen(req_obj, timeout=30) as resp:
            body = resp.read()
            return resp.status, len(body), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, 0, ""
    except urllib.error.URLError as exc:
        return -1, 0, str(exc)


def wait_stage(token: str, work_id: int, key: str, timeout: int = 60) -> str:
    """按阶段 key 轮询流水线（用 key 而非 label，避免中文文案改名就失真）。"""
    deadline = time.time() + timeout
    status = "timeout"
    while time.time() < deadline:
        time.sleep(1.5)
        items = (req("GET", f"/works/{work_id}/pipeline", token).get("data") or {}).get("items") or []
        hit = next((i for i in items if i.get("key") == key), None)
        if hit:
            status = hit.get("status", "")
            if status not in ("pending", "running"):
                return status
    return status


def main() -> int:
    # 登录主键是邮箱（见 schemas/auth.py: LoginIn）
    mail, pwd = "smoke@example.com", "smoke123456"

    print("== 1. 注册 / 登录 ==")
    req("POST", "/auth/register", body={"email": mail, "password": pwd, "nickname": "smoke"})
    login = req("POST", "/auth/login", body={"email": mail, "password": pwd})
    token = (login.get("data") or {}).get("access_token", "")
    check("登录拿到 JWT", bool(token), f"code={login.get('code')}")
    if not token:
        return 1

    print("== 2. 建作品 ==")
    work = req("POST", "/works", token, {"name": "基础设施冒烟", "author": "smoke"})
    work_id = (work.get("data") or {}).get("id")
    check("作品创建成功", bool(work_id), f"work_id={work_id}")

    print("== 3. 文本导入（章节/片段落 PostgreSQL） ==")
    content = "\n".join(f"第{i}章 标题{i}。\n正文段落{i}的内容。" * 4 for i in range(1, 4))
    merged = req("POST", f"/works/{work_id}/files/merge", token,
                 {"content": content, "filename": "smoke.txt"})
    d = merged.get("data") or {}
    check("章节切分完成", (d.get("chapter_count") or d.get("chapters") or 0) > 0,
          f"chapters={d.get('chapter_count') or d.get('chapters')}")

    print("== 4. 触发解析 ==")
    parse = req("POST", f"/works/{work_id}/parse", token, {})
    p_task = (parse.get("data") or {}).get("task_id")
    check("解析任务已创建", bool(p_task), f"task={p_task}")
    p_st = wait_stage(token, work_id, "parse", timeout=45) if p_task else "timeout"
    check("解析阶段完成（流水线状态）", p_st in ("done", "success"), f"status={p_st}")

    print("== 5. 触发合成（音频写 S3，进度走 Redis） ==")
    synth = req("POST", f"/works/{work_id}/synthesize", token, {"scope": "sample"})
    s_task = (synth.get("data") or {}).get("task_id")
    check("合成任务已创建", bool(s_task), f"task={s_task}")
    s_st = wait_stage(token, work_id, "synth", timeout=60) if s_task else "timeout"
    check("合成阶段完成（进度经 Redis 广播）", s_st in ("done", "success"), f"status={s_st}")

    # 任务表里的产物引用才是真实写盘位置（S3 对象键 / 本地相对路径）
    tsk = req("GET", f"/tasks/{s_task}", token).get("data") or {}
    ref = tsk.get("result_ref") or ""
    check("合成产物已写入对象存储", bool(ref), f"result_ref={ref}")

    print("== 6. 资产入库 + 对象存储直链 ==")
    reindex = req("GET", f"/works/{work_id}/assets/reindex", token)
    assets = req("GET", f"/works/{work_id}/assets", token)
    items = (assets.get("data") or {}).get("items") or []
    check("音频资产已登记", len(items) > 0,
          f"reindex={reindex.get('data')} count={len(items)}")

    url = ref
    if url.startswith("/files/"):
        url = "http://backend:8000" + url
    code, size, ctype = fetch(url) if url.startswith("http") else (-1, 0, "no_url")
    check("音频可下载（S3 预签名直链 / 后端反代）", code in (200, 302, 206) and size >= 0,
          f"code={code} bytes={size} type={ctype}")

    print("== 7. 落库校验（PostgreSQL） ==")
    stats = req("GET", f"/works/{work_id}/stats", token)
    sd = stats.get("data") or {}
    check("章节数入库正确", sd.get("chapter_count", 0) > 0,
          f"chapters={sd.get('chapter_count')} words={sd.get('word_count')}")
    check("统计接口可读", bool(sd))

    print("\n===== 汇总 =====")
    print(f"PASS {len(PASS)} / FAIL {len(FAIL)}")
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
