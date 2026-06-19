"""
SkillMap AI — Roadmap ORM Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A Roadmap is one YouTube playlist converted into a structured
learning path. One user can have many roadmaps.
"""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.video import Video
    from app.models.progress import VideoProgress
    from app.models.module import Module


class RoadmapStatus(str, enum.Enum):
    """
    Lifecycle states for a roadmap.
    """

    PROCESSING = "processing"
    ACTIVE = "active"
    ARCHIVED = "archived"

    # New granular statuses
    IMPORTING = "importing"
    GENERATING_MODULES = "generating_modules"
    GENERATING_NOTES = "generating_notes"
    BUILDING_SEARCH_INDEX = "building_search_index"
    READY = "ready"
    FAILED = "failed"


class Roadmap(Base, TimestampMixin):
    """
    Represents a YouTube playlist imported as a learning roadmap.

    Design notes:
    - playlist_id stores the raw YouTube playlist ID (e.g. "PLxxxxxx")
      separately from the full URL so queries can be done on ID alone
    - total_videos / completed_videos are denormalized counters —
      updated whenever video progress changes, avoids COUNT() queries
      on every dashboard load
    - status uses a Python Enum → PostgreSQL native ENUM type via SQLAlchemy
    """

    __tablename__ = "roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    playlist_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    playlist_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    total_videos: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completed_videos: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    status: Mapped[RoadmapStatus] = mapped_column(
        Enum(RoadmapStatus, name="roadmap_status_enum"),
        default=RoadmapStatus.PROCESSING,
        nullable=False,
    )
    insights_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="roadmaps",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="Video.position",  # always return videos in playlist order
        lazy="select",
    )
    progress: Mapped[list["VideoProgress"]] = relationship(
        "VideoProgress",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        lazy="select",
    )
    modules: Mapped[list["Module"]] = relationship(
        "Module",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="Module.position",
        lazy="select",
    )

    @property
    def completion_percentage(self) -> float:
        """Calculate roadmap completion as a percentage (0.0 – 100.0)."""
        if self.total_videos == 0:
            return 0.0
        return round((self.completed_videos / self.total_videos) * 100, 1)

    def __repr__(self) -> str:
        return f"<Roadmap id={self.id} title={self.title!r} status={self.status}>"
