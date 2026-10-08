"""Application configuration (pydantic-settings)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Audiobook Studio"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./speech_book.db"

    # JWT
    jwt_secret: str = "dev-secret-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS
    cors_origins: list[str] = ["*"]

    # ------------------------------------------------------------ 本地文件存储
    # local：写 settings.storage_dir 目录，经 /files/{path} 反代出（POC 默认）
    storage_dir: str = "./data"

    # ------------------------------------------------------------ Redis
    # 用途：SSE 进度广播（progress_backend=redis）+ 生产任务队列（XADD + Worker）
    # 格式：redis://[:password@]host:port/db
    redis_url: str = "redis://redis:6379/0"
    # memory：进程内 ProgressHub（POC，多副本/重启即丢）
    # redis ：广播到所有后端副本，SSE 订阅端可横向扩容
    progress_backend: str = "memory"
    # 生产队列开关：true 时 dispatch 只写 Stream，由独立 worker 容器消费
    task_queue_backend: str = "memory"  # memory | redis

    # ------------------------------------------------------------ MinIO（S3 兼容对象存储）
    storage_backend: str = "local"  # local | minio
    minio_endpoint: str = "minio:9000"            # 容器内网地址，客户端直连用
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False                    # 内网走 http，公网部署改 true
    minio_bucket: str = "speech-book"
    # 直链前缀：留空 = 音频走后端 /files/ 反代（默认，便于鉴权）；
    # 填 "http://host:9000/speech-book" 则前端直连对象存储，省一层代理
    minio_public_base_url: str = ""

    # POC mode: in-process task execution; production replaces with Worker + Redis
    poc_mode: bool = True

    api_v1_prefix: str = "/api/v1"


settings = Settings()
