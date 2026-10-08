"""人物关系图数据模型（对应 design/workspace.html 的 `#graph` 区块）。

关系图由「节点 = 角色」+「边 = 关系」两部分构成：
- 节点复用 `Role`（models/parse.py），不在Relation里冗余存角色名，避免改角色名后不同步；
- 边单独存 `Relation`，支持人工新增/改类型/调强度/删除，以及从解析结果自动推导。

设计约束（DESIGN_SPEC §5.3b / §7b.2）：
- `source=auto` 的边由解析阶段自动推导，前端显示为**虚线（待确认）**；
- `source=manual` 的边是人工确认/新增的，升为**强关系**，同时参与音色推荐排序权重；
- 一条边只存一个方向（from < to 的规范化存储），回显时前端双向都能取到。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# 边的语义类型（决定关系图配色，与前端 KIND_COLOR 约定一致）
RELATION_KINDS = ["narration", "kinship", "mate", "other"]
# 边的数据来源：auto=解析自动推导（待确认） / manual=人工确认或新增
RELATION_SOURCES = ["auto", "manual"]


class Relation(Base, TimestampMixin):
    """角色之间的语义关系边（人物关系图的一条连线）。"""

    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    # 关系起点角色 id；0 表示旁白(narrator)节点
    from_role_id: Mapped[int] = mapped_column(default=0)
    # 关系终点角色 id；0 表示旁白(narrator)节点
    to_role_id: Mapped[int] = mapped_column(default=0)
    # 关系展示文案，如「妻子」「同事」「师徒」
    label: Mapped[str] = mapped_column(String(64), default="")
    # 语义类型：narration=旁白叙述 / kinship=亲属 / mate=同伴 / other=其他
    kind: Mapped[str] = mapped_column(String(16), default="other")
    # 关系强度 0~1，前端用它映射连线线宽
    weight: Mapped[float] = mapped_column(default=0.5)
    # 数据来源：auto 待确认（虚线）/ manual 已确认（实线）
    source: Mapped[str] = mapped_column(String(16), default="auto")
    # 置信度：auto 边由解析给出，manual 边默认为 1.0
    confidence: Mapped[float] = mapped_column(default=0.0)
    # 扩展属性（如「结婚年份」「所属阵营」等画像补充）
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)
