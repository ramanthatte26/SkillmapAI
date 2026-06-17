"""
SkillMap AI — SQLAlchemy Declarative Base & Shared Mixins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All ORM models inherit from Base (via DeclarativeBase).
TimestampMixin adds created_at / updated_at to any model without repetition.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    The single DeclarativeBase for all SQLAlchemy models.

    Why one Base?
    - Alembic autogenerate scans ALL tables reachable from Base.metadata
    - Relationships between models require a shared registry
    - Avoids circular imports: models import Base, not each other directly
    """
    pass


class TimestampMixin:
    """
    Reusable mixin that adds audit timestamp columns to any model.

    created_at: set once at INSERT time by the database server
    updated_at: automatically refreshed on every UPDATE by the database server

    Using server_default / onupdate with func.now() means the DB owns
    these values — they're accurate even when records are modified outside
    the application (e.g., manual SQL, migrations).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
