"""
Alembic env.py — Migration Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This file is run by Alembic when executing `alembic upgrade head`
or any migration command. It connects to the database and runs
migrations in either 'offline' or 'online' mode.

Key integration points:
1. DATABASE_URL is pulled from app Settings (single source of truth).
2. target_metadata is set to Base.metadata — enables autogenerate.
3. ALL models must be imported (via app.models) for autogenerate to detect tables.
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Path setup ────────────────────────────────────────────────────
# Add the backend/ directory to sys.path so app.* imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import app modules ────────────────────────────────────────────
from app.config import get_settings
from app.models.base import Base

# CRITICAL: Import ALL models so their tables are registered on Base.metadata.
# Alembic's autogenerate compares Base.metadata against the live DB schema.
# Any model NOT imported here will be INVISIBLE to autogenerate.
import app.models  # noqa: F401 — side effect import registers all models

# ── Alembic config ────────────────────────────────────────────────
config = context.config

# Interpret alembic.ini's [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our SQLAlchemy metadata
target_metadata = Base.metadata

# Override the sqlalchemy.url from alembic.ini with the one from Settings.
# This ensures we never duplicate DATABASE_URL in two places.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """
    Offline mode: generate SQL migration scripts without a live DB connection.
    Useful for generating SQL to review or apply manually in production.

    Usage: alembic upgrade head --sql > migrations.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,        # detect column type changes
        compare_server_default=True,  # detect server_default changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: apply migrations directly to a live database connection.
    This is the standard mode for development and CI/CD.

    Usage: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # use NullPool for migrations (no connection pooling needed)
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
