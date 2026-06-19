"""
SkillMap AI — Module & ModuleVideo ORM Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Defines learning modules (groupings of videos within a roadmap)
and the mapping table connecting modules to videos with custom positions.
"""

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.roadmap import Roadmap
    from app.models.video import Video


class Module(Base, TimestampMixin):
    """
    A single learning module within a Roadmap.
    One Roadmap has many Modules.
    """

    __tablename__ = "modules"

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
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    roadmap: Mapped["Roadmap"] = relationship(
        "Roadmap",
        back_populates="modules",
    )
    module_videos: Mapped[list["ModuleVideo"]] = relationship(
        "ModuleVideo",
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="ModuleVideo.position",
        lazy="select",
    )

    @property
    def videos(self) -> list["Video"]:
        """
        Helper property to access the underlying video list ordered
        by their position within this module.
        """
        return [mv.video for mv in self.module_videos]

    def __repr__(self) -> str:
        return f"<Module id={self.id} name={self.name!r} position={self.position}>"


class ModuleVideo(Base, TimestampMixin):
    """
    Association table mapping a Video to a Module with ordering.
    A video typically belongs to one module, but this structure supports
    flexible reuse across modules.
    """

    __tablename__ = "module_videos"

    __table_args__ = (
        UniqueConstraint("module_id", "video_id", name="uq_module_video"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    module: Mapped["Module"] = relationship(
        "Module",
        back_populates="module_videos",
    )
    video: Mapped["Video"] = relationship(
        "Video",
        back_populates="module_videos",
    )

    def __repr__(self) -> str:
        return (
            f"<ModuleVideo id={self.id} module_id={self.module_id} "
            f"video_id={self.video_id} position={self.position}>"
        )
