"""Minimal passwordless (magic-link) authentication (Phase 10, Teil 2).

Deliberately small (the issue asks to keep auth minimal): request a one-time
token by email, verify it to obtain the user.  Email delivery is behind the
:class:`EmailSender` seam -- the default records links instead of sending, and a
production transport (e.g. Resend) plugs in without touching this service.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.repository import EventStore

TOKEN_TTL = timedelta(minutes=15)


class AuthError(Exception):
    """Raised when a magic-link token is unknown, expired or already used."""


class EmailSender(Protocol):
    """Sends a magic-link token to an email address."""

    def send_magic_link(self, email: str, token: str) -> None: ...


class NullEmailSender:
    """Default no-op sender (use a real transport in production)."""

    def send_magic_link(self, email: str, token: str) -> None:
        return None


@dataclass
class RecordingEmailSender:
    """Dev/test sender that records the issued links."""

    sent: list[tuple[str, str]] = field(default_factory=list)

    def send_magic_link(self, email: str, token: str) -> None:
        self.sent.append((email, token))


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    email: str


class AuthService:
    """Issues and verifies magic-link tokens."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        email_sender: EmailSender | None = None,
        store: EventStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._email_sender = email_sender or NullEmailSender()
        self._store = store or EventStore()

    async def request_magic_link(self, email: str) -> None:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + TOKEN_TTL
        async with self._session_factory() as session, session.begin():
            await self._store.create_magic_token(session, token, email, expires_at)
        self._email_sender.send_magic_link(email, token)

    async def verify(self, token: str) -> AuthenticatedUser:
        async with self._session_factory() as session, session.begin():
            record = await self._store.get_magic_token(session, token)
            if record is None or record.used:
                raise AuthError("Invalid or already-used token")
            # SQLite returns naive datetimes; treat a stored value as UTC.
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < datetime.now(UTC):
                raise AuthError("Token has expired")
            record.used = True
            user = await self._store.get_or_create_user(session, record.email)
            return AuthenticatedUser(user_id=user.id, email=user.email)
