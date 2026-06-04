"""Alembic migration environment (Phase 8).

Runs synchronously: the async ``DATABASE_URL`` is mapped onto a sync driver
(psycopg works in both modes) so migrations need no event loop.
"""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import the models so their tables are registered on the metadata.
from eg1835.infrastructure import models  # noqa: F401
from eg1835.infrastructure.db import DEFAULT_DATABASE_URL, Base

config = context.config
target_metadata = Base.metadata


def _sync_url() -> str:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    # Strip async drivers -- Alembic runs synchronously.
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
