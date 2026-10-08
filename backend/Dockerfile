# ============================================================
# 后端镜像：FastAPI + uv 管理依赖
# 依赖清单：fastapi / sqlalchemy / aiosqlite（POC）
#            asyncpg（PostgreSQL）/ redis（进度广播）/ minio（对象存储）
#
# 构建上下文：backend/（必须在 backend/ 目录下执行 docker build ..）
# 镜像内不做「选后端」的判断：用哪个后端由运行时的 SB_* 环境变量决定，
# 同一份镜像既能跑 POC（SQLite + 本地文件 + 内存进度），
# 也能跑完整栈（PostgreSQL + MinIO + Redis），见根目录 docker-compose.yml。
# ============================================================
FROM python:3.11-slim

# PYTHONUNBUFFERED：日志实时进 docker logs，不被缓冲吞掉
# UV_LINK_MODE=copy：容器层里不产生软链接，镜像可直接复制到别的机器
# PIP_NO_CACHE_DIR：不留 pip 缓存
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ------------------------------------------------------------ 依赖层（吃 Docker 缓存）
# 先装 uv 与依赖清单，再拷源码：业务代码改动不会触发重装依赖，构建快很多
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-editable
RUN rm -rf /root/.cache/uv   # uv 缓存能省 ~100MB 镜像体积，依赖已落在 /app/.venv

# ------------------------------------------------------------ 源码层
COPY app ./app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# /app/data：本地存储/临时缓冲目录，compose 里挂卷持久化（重建容器不丢）
RUN mkdir -p /app/data/synth && chmod +x /app/docker-entrypoint.sh

# uv sync 把包装进 /app/.venv，加进 PATH 后 CMD 才能直接跑 uvicorn
# 下面这些默认值 ≈ POC 形态；完整栈的取值由 docker-compose.yml 的 environment 覆盖
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    SB_DATABASE_URL="sqlite+aiosqlite:////app/data/speech_book.db" \
    SB_STORAGE_DIR="/app/data" \
    SB_STORAGE_BACKEND="local" \
    SB_PROGRESS_BACKEND="memory" \
    SB_TASK_QUEUE_BACKEND="memory" \
    SB_REDIS_URL="redis://redis:6379/0" \
    SB_MINIO_ENDPOINT="minio:9000" \
    SB_MINIO_ACCESS_KEY="minioadmin" \
    SB_MINIO_SECRET_KEY="minioadmin" \
    SB_MINIO_BUCKET="speech-book" \
    SB_MINIO_SECURE="false" \
    SB_MINIO_PUBLIC_BASE_URL="" \
    SB_JWT_SECRET="change-me-before-deploy" \
    SB_CORS_ORIGINS="*" \
    SB_DEBUG="false"

EXPOSE 8000

# 容器级健康检查（compose 里也有同样的定义，谁先跑都行）
# 打根路径 /health，不鉴权；顺带回显当前生效的 storage / progress 后端
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

# 入口脚本会先探一次数据库端口再 exec uvicorn，避免建表阶段 crash loop
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
