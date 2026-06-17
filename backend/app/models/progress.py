"""
SkillMap AI — VideoProgress ORM Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tracks per-user, per-video learning progress.
Each row represents one user's state for one video.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.video import Video
    from app.models.roadmap import Roadmap


class VideoProgress(Base, TimestampMixin):
    """
    Records a user's progress on a specific video.

    Design notes:
    - UniqueConstraint(user_id, video_id): enforces one progress row per
      (user, video) pair at the DATABASE level — not just in application code.
      This means even concurrent requests cannot create duplicates.
    - roadmap_id is denormalized here (it could be derived via video.roadmap_id)
      to allow fast single-table queries when loading an entire roadmap's
      progress dashboard without a JOIN through videos.
    - completed_at is set when is_completed flips to True; cleared if
      the user un-marks a video as complete.
    - user_notes is free-form text — the user's own annotations per video.
    """

    __tablename__ = "video_progress"

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_user_video_progress"),
    )

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
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized for fast roadmap-level progress queries
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    watch_time_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    user_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="progress",
    )
    video: Mapped["Video"] = relationship(
        "Video",
        back_populates="progress",
    )
    roadmap: Mapped["Roadmap"] = relationship(
        "Roadmap",
        back_populates="progress",
    )

    def __repr__(self) -> str:
        return (
            f"<VideoProgress user={self.user_id} "
            f"video={self.video_id} completed={self.is_completed}>"
        )
