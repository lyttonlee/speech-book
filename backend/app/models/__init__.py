"""Model registry (import to register all tables on Base.metadata)."""
from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.work import Work
from app.models.parse import Chapter, Segment, Role
from app.models.graph import Relation
from app.models.audit import EditLog, WorkSnapshot
from app.models.asset import AudioAsset, ExportRecord
from app.models.voice import Voice, Bind, VoiceTag
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
    "VoiceTag",
    "Bind",
    "Task",
    "Relation",
    "EditLog",
    "WorkSnapshot",
    "AudioAsset",
    "ExportRecord",
]
