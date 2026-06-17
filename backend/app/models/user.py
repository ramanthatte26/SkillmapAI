"""
SkillMap AI — User ORM Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Represents an authenticated user account.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    # Imported only for type hints — avoids circular imports at runtime.
    from app.models.roadmap import Roadmap
    from app.models.progress import VideoProgress


class User(Base, TimestampMixin):
    """
    Core user entity.

    Design notes:
    - UUID PK: non-sequential, safe to expose in URLs (no enumeration)
    - email + username are both unique: email is the login identifier,
      username is the display handle
    - hashed_password stores the bcrypt hash — NEVER the plaintext
    - is_active: soft-disable accounts without deletion
    - is_verified: placeholder for future email verification flow
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    roadmaps: Mapped[list["Roadmap"]] = relationship(
        "Roadmap",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    progress: Mapped[list["VideoProgress"]] = relationship(
        "VideoProgress",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
