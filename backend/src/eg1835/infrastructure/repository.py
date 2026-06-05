"""Async event-store repository (Phase 8).

Thin data-access layer over the ORM models.  All methods take the
:class:`AsyncSession` to use, so the caller controls the transaction boundary
(important for the optimistic-locking append in :class:`GameService`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Event, Game, MagicToken, Player, Snapshot, User


class EventStore:
    """Data access for games, players, events and snapshots."""

    # --- users / games / players ----------------------------------------

    async def create_user(self, session: AsyncSession, email: str) -> User:
        user = User(email=email)
        session.add(user)
        await session.flush()
        return user

    async def get_user_by_email(
        self, session: AsyncSession, email: str
    ) -> User | None:
        return await session.scalar(select(User).where(User.email == email))

    async def get_or_create_user(self, session: AsyncSession, email: str) -> User:
        """Return the existing user for ``email`` or insert a new one."""
        user = await self.get_user_by_email(session, email)
        if user is not None:
            return user
        return await self.create_user(session, email)

    # --- magic-link tokens ----------------------------------------------

    async def create_magic_token(
        self, session: AsyncSession, token: str, email: str, expires_at: datetime
    ) -> MagicToken:
        record = MagicToken(token=token, email=email, expires_at=expires_at)
        session.add(record)
        await session.flush()
        return record

    async def get_magic_token(
        self, session: AsyncSession, token: str
    ) -> MagicToken | None:
        record: MagicToken | None = await session.scalar(
            select(MagicToken).where(MagicToken.token == token)
        )
        return record


    async def create_game(self, session: AsyncSession, num_players: int) -> Game:
        game = Game(num_players=num_players, status="active")
        session.add(game)
        await session.flush()
        return game

    async def get_game(self, session: AsyncSession, game_id: int) -> Game | None:
        return await session.get(Game, game_id)

    async def list_games(self, session: AsyncSession) -> list[Game]:
        result = await session.scalars(select(Game).order_by(Game.id))
        return list(result)

    async def set_game_status(
        self, session: AsyncSession, game_id: int, status: str
    ) -> None:
        game = await session.get(Game, game_id)
        if game is not None:
            game.status = status

    async def add_player(
        self, session: AsyncSession, game_id: int, user_id: int, seat: int
    ) -> Player:
        player = Player(game_id=game_id, user_id=user_id, seat=seat)
        session.add(player)
        await session.flush()
        return player

    async def list_players(self, session: AsyncSession, game_id: int) -> list[Player]:
        result = await session.scalars(
            select(Player).where(Player.game_id == game_id).order_by(Player.seat)
        )
        return list(result)

    # --- events ----------------------------------------------------------

    async def max_sequence(self, session: AsyncSession, game_id: int) -> int:
        result = await session.scalar(
            select(func.max(Event.sequence)).where(Event.game_id == game_id)
        )
        return int(result or 0)

    async def append_event(
        self,
        session: AsyncSession,
        game_id: int,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
        player_id: str | None,
    ) -> Event:
        """Insert an event; flushing surfaces a UNIQUE conflict immediately."""
        event = Event(
            game_id=game_id,
            sequence=sequence,
            type=event_type,
            payload=payload,
            player_id=player_id,
        )
        session.add(event)
        await session.flush()  # raises IntegrityError on (game_id, sequence) clash
        return event

    async def load_events(
        self,
        session: AsyncSession,
        game_id: int,
        from_sequence: int = 1,
        to_sequence: int | None = None,
    ) -> list[Event]:
        stmt = select(Event).where(
            Event.game_id == game_id, Event.sequence >= from_sequence
        )
        if to_sequence is not None:
            stmt = stmt.where(Event.sequence <= to_sequence)
        result = await session.scalars(stmt.order_by(Event.sequence))
        return list(result)

    # --- snapshots -------------------------------------------------------

    async def save_snapshot(
        self, session: AsyncSession, game_id: int, sequence: int, blob: bytes
    ) -> None:
        session.add(Snapshot(game_id=game_id, sequence=sequence, state_blob=blob))
        await session.flush()

    async def latest_snapshot(
        self, session: AsyncSession, game_id: int, until_sequence: int | None = None
    ) -> Snapshot | None:
        stmt = select(Snapshot).where(Snapshot.game_id == game_id)
        if until_sequence is not None:
            stmt = stmt.where(Snapshot.sequence <= until_sequence)
        stmt = stmt.order_by(Snapshot.sequence.desc()).limit(1)
        snapshot: Snapshot | None = await session.scalar(stmt)
        return snapshot
