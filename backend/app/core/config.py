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

    # Local storage (POC replacement for MinIO)
    storage_dir: str = "./data"

    # POC mode: in-process task execution + in-memory progress hub
    # (production replaces with Redis Stream + Worker processes)
    poc_mode: bool = True

    api_v1_prefix: str = "/api/v1"


settings = Settings()
