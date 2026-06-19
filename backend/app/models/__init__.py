"""
SkillMap AI — Models Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralised import for all ORM models.

This module MUST be imported before Alembic autogenerate runs
(done in alembic/env.py) so that all Table objects are registered
on Base.metadata. Forgetting to import a model means Alembic will
not detect its table and will NOT generate migration code for it.
"""

from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.roadmap import Roadmap, RoadmapStatus
from app.models.video import Video, AINotesStatus
from app.models.progress import VideoProgress
from app.models.module import Module, ModuleVideo

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Roadmap",
    "RoadmapStatus",
    "Video",
    "AINotesStatus",
    "VideoProgress",
    "Module",
    "ModuleVideo",
]
