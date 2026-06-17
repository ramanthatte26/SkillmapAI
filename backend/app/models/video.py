"""
SkillMap AI — Video ORM Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A Video represents one item within a Roadmap (i.e., one video
from the YouTube playlist). Each video has a position (its
order in the playlist) and optional AI-generated notes.
"""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.roadmap import Roadmap
    from app.models.progress import VideoProgress


class AINotesStatus(str, enum.Enum):
    """
    Tracks the async AI note-generation pipeline state per video.

    pending:    Not yet queued for generation
    generating: AI job is in-flight
    done:       Notes are ready to display
    failed:     Generation failed (can be retried)
    """

    PENDING = "pending"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


class Video(Base, TimestampMixin):
    """
    A single YouTube video within a Roadmap.

    Design notes:
    - youtube_id (11 chars) is the raw video ID extracted from the URL
      (e.g. "dQw4w9WgXcQ"). Stored separately from the full URL.
    - position determines ordering within the roadmap — replicated from
      the playlist's original order, 0-indexed.
    - ai_notes stores the full AI-generated summary text (nullable until generated).
    - ai_notes_status drives frontend UI state (spinner / ready / error).
    """

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    youtube_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    ai_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_notes_status: Mapped[AINotesStatus] = mapped_column(
        Enum(AINotesStatus, name="ai_notes_status_enum"),
        default=AINotesStatus.PENDING,
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    roadmap: Mapped["Roadmap"] = relationship(
        "Roadmap",
        back_populates="videos",
    )
    progress: Mapped[list["VideoProgress"]] = relationship(
        "VideoProgress",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def youtube_url(self) -> str:
        """Construct the full YouTube watch URL from the stored ID."""
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    @property
    def duration_formatted(self) -> str:
        """Return human-readable duration string (e.g. '1h 23m 45s')."""
        if self.duration_seconds is None:
            return "Unknown"
        h, rem = divmod(self.duration_seconds, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"<Video id={self.id} youtube_id={self.youtube_id!r} "
            f"position={self.position}>"
        )
