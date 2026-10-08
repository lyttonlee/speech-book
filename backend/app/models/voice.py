from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


VOICE_TYPES = ["builtin", "clone"]
VOICE_STATUS = ["available", "pending", "training", "rejected"]


class Voice(Base, TimestampMixin):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(primary_key=True)
    # builtin 音色 owner_id 为 NULL；clone 音色归属上传用户
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16), default="builtin")
    engine: Mapped[str] = mapped_column(String(32), default="stub")
    engine_voice_id: Mapped[str] = mapped_column(String(64), default="")
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="available")


class VoiceTag(Base, TimestampMixin):
    """音色标签（音色卡上的 chip / 顶部标签筛选 / 自动匹配依据）。

    `dim` 是标签维度（如 性别=男声、年龄层=青年、气质=温柔），
    `scope=global` 为全局标签，`scope=work` 为某本书专属标签。
    """

    __tablename__ = "voice_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 标签所属用户；NULL 表示系统内置标签
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # 所在作品；scope=work 时必填，用于本书专属标签
    work_id: Mapped[int | None] = mapped_column(ForeignKey("works.id"), nullable=True)
    # 标签维度：性别 / 年龄层 / 气质 / 场景 …
    dim: Mapped[str] = mapped_column(String(32), default="")
    # 标签值：男声 / 青年 / 温柔 …
    value: Mapped[str] = mapped_column(String(64))
    # 标签分组（音色库卡片按组归类）
    group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 作用域：global=全局 / work=作品专属
    scope: Mapped[str] = mapped_column(String(16), default="global")
    # 标签配色（7 色板，前端渲染 chip）
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 使用该标签的音色数量（音色库标签管理弹窗展示）
    usage_count: Mapped[int] = mapped_column(Integer, default=0)


class Bind(Base, TimestampMixin):
    """角色-音色-参数绑定。role_id=0 表示旁白(narrator)。"""

    __tablename__ = "bindings"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    role_id: Mapped[int] = mapped_column(default=0)  # 0 = narrator
    voice_id: Mapped[int | None] = mapped_column(ForeignKey("voices.id"), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
