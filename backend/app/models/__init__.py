"""Model registry (import to register all tables on Base.metadata)."""
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.work import Work
from app.models.parse import Chapter, Segment, Role
from app.models.voice import Voice, Bind
from app.models.task import Task

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Work",
    "Chapter",
    "Segment",
    "Role",
    "Voice",
    "Bind",
    "Task",
]
