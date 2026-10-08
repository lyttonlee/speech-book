#!/bin/sh
# ============================================================
# 后端容器入口：先等依赖服务就绪，再拉起 uvicorn
#
# 为什么需要它：compose 的 depends_on 只保证容器「启动」，
# 不保证 PostgreSQL 能连上；这里主动探一次 TCP，避免后端在
# 建表阶段就崩掉进入 crash loop。
# ============================================================
set -e

echo "[entrypoint] 等待数据库就绪…"
python - <<'PY'
"""从 SB_DATABASE_URL 里解析出 host:port 做 TCP 探活。

SQLite（POC）直接跳过；PostgreSQL 最多等 90s，超时也继续启动，
让 uvicorn 自己把真实错误打出来，比在这里直接退出更好排查。
"""
import os
import socket
import sys
import time
from urllib.parse import urlparse

url = os.getenv("SB_DATABASE_URL", "")
if not url.startswith("postgresql"):
    print("[entrypoint] SQLite / 非 PostgreSQL，跳过数据库等待")
    sys.exit(0)

# postgresql+asyncpg://user:pw@host:5432/db
# 用 urlparse 而不是 split(":")

# —— 手工切分会把 "db:5432/speech_book" 的库名误当成端口，int() 直接抛异常。
p = urlparse(url)
host = p.hostname
port = p.port or 5432

deadline = time.time() + 90
while time.time() < deadline:
    try:
        with socket.create_connection((host, int(port)), timeout=2):
            print(f"[entrypoint] 数据库 {host}:{port} 就绪")
            sys.exit(0)
    except OSError:
        print(f"[entrypoint] 数据库 {host}:{port} 还没起来，2s 后重试…")
        time.sleep(2)

print(f"[entrypoint] 等待数据库超时，继续执行（后端会自行重试）")
PY

echo "[entrypoint] 启动 uvicorn：app.main:app --host 0.0.0.0 --port 8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
