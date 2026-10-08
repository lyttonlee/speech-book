"""验证 SSE 进度是真的经 Redis 广播（而非降级到进程内内存 Hub）。

用法（在 backend 容器内，配合外部启动的 `redis-cli monitor`）：
    docker compose cp scripts/prove_redis.py backend:/app/prove_redis.py
    docker compose exec -T redis redis-cli monitor &
    docker compose exec -T backend python /app/prove_redis.py
"""
from __future__ import annotations

import json
import time
import urllib.request

BASE = "http://backend:8000/api/v1"


def rq(method: str, path: str, token: str = "", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    token = rq("POST", "/auth/login", body={
        "email": "smoke@example.com", "password": "smoke123456",
    })["data"]["access_token"]

    work_id = rq("POST", "/works", token, {"name": "redis 广播验证"})["data"]["id"]
    rq("POST", f"/works/{work_id}/files/merge", token, {
        "content": "第一章 开头。\n“你来了。”她说。\n\n第二章 继续。\n“嗯。”他说。",
        "filename": "redis.txt",
    })
    rq("POST", f"/works/{work_id}/parse", token, {})
    task = rq("POST", f"/works/{work_id}/synthesize", token, {"scope": "sample"})
    print("合成任务已触发：", task.get("data"), flush=True)
    time.sleep(6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
