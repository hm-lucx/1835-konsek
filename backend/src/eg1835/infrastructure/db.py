"""Async SQLAlchemy engine / session plumbing (Phase 8).

The production database is PostgreSQL; tests use SQLite (``aiosqlite``).  The
ORM is portable between them: JSONB degrades to JSON and BYTEA to BLOB.
"""
from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./konsek.db"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def normalize_database_url(url: str) -> str:
    """Map a plain driver URL onto its async counterpart.

    ``postgresql://`` → ``postgresql+psycopg://`` and ``sqlite://`` →
    ``sqlite+aiosqlite://`` so the same ``DATABASE_URL`` works for the sync
    tools (Alembic) and the async runtime.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def database_url() -> str:
    """Resolve the configured database URL (env ``DATABASE_URL`` or default)."""
    return normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


def create_engine(url: str | None = None) -> AsyncEngine:
    """Create an async engine for ``url`` (default: configured URL)."""
    return create_async_engine(url or database_url(), future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory that keeps objects usable after commit."""
    return async_sessionmaker(engine, expire_on_commit=False)
