"""
SkillMap AI — Database Engine & Session Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Configures SQLAlchemy 2.0 with:
  - Connection pooling (QueuePool, tuned for web workloads)
  - A session factory that is safe to use per-request
  - A convenience get_db() generator for FastAPI Depends()
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────
# pool_pre_ping=True: validates connections before use (handles DB restarts)
# pool_size=5: number of persistent connections kept open
# max_overflow=10: extra connections allowed beyond pool_size under load
# pool_recycle=1800: recycle connections every 30 min (avoids stale TCP issues)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    echo=settings.debug,  # log SQL statements only in debug mode
)

# ── Session Factory ───────────────────────────────────────────────
# autocommit=False: transactions must be explicitly committed
# autoflush=False: prevents implicit flushes that can cause confusing bugs
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The session is always closed in the finally block, even if the
    request handler raises an exception. SQLAlchemy rolls back any
    uncommitted transaction on session.close().
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
