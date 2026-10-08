"""人工修改留痕与版本快照数据模型（对应 workspace.html 的 `#audit` 区块）。

设计约束（DESIGN_SPEC §5.3b / §7b.4）：
- 任何 AI 产出的字段被人工改动，都要写一条 `EditLog`（前后值 + 操作人 + 对象），
  这样前端才能渲染「修改日志 diff」并支持**逐条回滚**；
- 用户手动保存一批改动时可以打一个 `WorkSnapshot`（版本胶囊 v1…vN），
  支持**整体回滚**到某个历史版本；
- EditLog 的 `object_type` 覆盖工作空间里所有可改对象：
  role / binding / segment / relation / work。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# 可留痕的业务对象类型（与前端「修改留痕」区块的筛选一致）
EDIT_OBJECT_TYPES = ["role", "binding", "segment", "relation", "work"]
# 留痕动作：update=改字段 / revert=回滚 / auto=AI 重跑覆盖
EDIT_ACTIONS = ["update", "revert", "auto"]


class EditLog(Base, TimestampMixin):
    """一条人工修改记录（工作空间「修改日志」的一行 + 前后 diff 的来源）。"""

    __tablename__ = "edit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    # 操作人（审计要求可追溯到人）
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 被改对象类型：role/binding/segment/relation/work
    object_type: Mapped[str] = mapped_column(String(16), default="work")
    # 被改对象主键（segment 存片段 id，relation 存关系 id）
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 被改字段名，如 speaker_role_id / emotion / voice_id
    field: Mapped[str] = mapped_column(String(64), default="")
    # 修改前的值（前端渲染 <del> 红字）
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 修改后的值（前端渲染 <ins> 绿字）
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 动作类型：update=人工改 / revert=回滚 / auto=重跑覆盖
    action: Mapped[str] = mapped_column(String(16), default="update")
    # 版本快照号（回滚或手动保存时写入，便于按版本聚合展示）
    snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 附加说明（如「按标签自动匹配」）
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class WorkSnapshot(Base, TimestampMixin):
    """作品版本快照（工作空间顶部的 v1…vN 胶囊）。"""

    __tablename__ = "work_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 版本号，从 1 递增，前端展示为 v1 / v2 / …
    version: Mapped[int] = mapped_column(Integer, default=1)
    # 快照标题，如「绑定完成后存档」
    label: Mapped[str] = mapped_column(String(128), default="")
    # 快照内容：当前绑定 / 角色 / 关系 / 片段关键字段的深拷贝
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
