"""Application service orchestrating the domain over the event store (Phase 8).

The domain is the single source of truth: the service only (de)serialises,
persists events, and replays.  Concurrency is handled optimistically -- the
``UNIQUE (game_id, sequence)`` constraint lets exactly one of two racing writers
win; the loser surfaces as :class:`ConflictError` (HTTP 409).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.action_base import Action, RuleViolation
from ..domain.game_state import GameState
from ..domain.or_flow import current_actor, step
from ..domain.result import Err
from ..domain.serialization import (
    action_from_payload,
    action_to_payload,
    dump_snapshot,
    load_snapshot,
)
from ..infrastructure.repository import EventStore
from .view import build_view, legal_actions

# A snapshot is written every this-many events to keep replay cheap (issue #9).
SNAPSHOT_INTERVAL = 20


class GameServiceError(Exception):
    """Base class for service-level errors."""


class GameNotFoundError(GameServiceError):
    """The requested game does not exist (HTTP 404)."""


class ConflictError(GameServiceError):
    """Optimistic-locking conflict: stale ``expected_seq`` (HTTP 409)."""


class TurnError(GameServiceError):
    """The submitting player is not the one allowed to act (HTTP 403)."""


class ActionValidationError(GameServiceError):
    """The submitted action violates a game rule (HTTP 422)."""

    def __init__(self, violation: RuleViolation) -> None:
        super().__init__(f"[{violation.rule}] {violation.message}")
        self.violation = violation


@dataclass(frozen=True)
class SubmitResult:
    """Outcome of a successful action submission."""

    sequence: int
    state: GameState


class GameService:
    """Create games, accept actions and replay state from the event log."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        store: EventStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._store = store or EventStore()

    # ------------------------------------------------------------------ #
    # Game lifecycle                                                       #
    # ------------------------------------------------------------------ #

    async def create_game(self, num_players: int, creator_email: str | None = None) -> int:
        async with self._session_factory() as session, session.begin():
            game = await self._store.create_game(session, num_players)
            if creator_email is not None:
                user = await self._store.get_or_create_user(session, creator_email)
                await self._store.add_player(session, game.id, user.id, seat=0)
            return game.id

    async def join_game(self, game_id: int, user_email: str, seat: int) -> None:
        async with self._session_factory() as session, session.begin():
            game = await self._store.get_game(session, game_id)
            if game is None:
                raise GameNotFoundError(f"Game {game_id} not found")
            user = await self._store.get_or_create_user(session, user_email)
            try:
                await self._store.add_player(session, game_id, user.id, seat)
            except IntegrityError as exc:  # seat already taken
                raise ConflictError(f"Seat {seat} is already taken") from exc

    # ------------------------------------------------------------------ #
    # Replay                                                               #
    # ------------------------------------------------------------------ #

    async def replay(self, game_id: int, until_seq: int | None = None) -> GameState:
        async with self._session_factory() as session:
            return await self._replay(session, game_id, until_seq)

    async def get_state(self, game_id: int) -> GameState:
        return await self.replay(game_id)

    async def current_sequence(self, game_id: int) -> int:
        async with self._session_factory() as session:
            if await self._store.get_game(session, game_id) is None:
                raise GameNotFoundError(f"Game {game_id} not found")
            return await self._store.max_sequence(session, game_id)

    async def get_log(self, game_id: int) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            if await self._store.get_game(session, game_id) is None:
                raise GameNotFoundError(f"Game {game_id} not found")
            events = await self._store.load_events(session, game_id)
            return [
                {
                    "sequence": e.sequence,
                    "type": e.type,
                    "player_id": e.player_id,
                    "payload": e.payload,
                }
                for e in events
            ]

    async def _replay(
        self, session: AsyncSession, game_id: int, until_seq: int | None
    ) -> GameState:
        game = await self._store.get_game(session, game_id)
        if game is None:
            raise GameNotFoundError(f"Game {game_id} not found")

        snapshot = await self._store.latest_snapshot(session, game_id, until_seq)
        if snapshot is not None:
            state = load_snapshot(snapshot.state_blob)
            from_seq = snapshot.sequence + 1
        else:
            state = GameState.initial(game.num_players)
            from_seq = 1

        events = await self._store.load_events(session, game_id, from_seq, until_seq)
        for event in events:
            action = action_from_payload({"type": event.type, "payload": event.payload})
            state = step(action, state)
        return state

    # ------------------------------------------------------------------ #
    # Action submission (optimistic locking)                               #
    # ------------------------------------------------------------------ #

    async def submit_action(
        self, game_id: int, player_id: str, action: Action, expected_seq: int
    ) -> SubmitResult:
        new_seq = expected_seq + 1
        try:
            async with self._session_factory() as session, session.begin():
                current = await self._store.max_sequence(session, game_id)
                if expected_seq != current:
                    raise ConflictError(
                        f"Stale sequence: expected {current}, got {expected_seq}"
                    )

                state = await self._replay(session, game_id, expected_seq)
                actor = current_actor(state)
                if actor is not None and player_id != actor:
                    raise TurnError(
                        f"It is {actor}'s turn, not {player_id}'s"
                    )
                result = action.validate(state)
                if isinstance(result, Err):
                    raise ActionValidationError(result.error)
                new_state = step(action, state)

                encoded = action_to_payload(action)
                await self._store.append_event(
                    session,
                    game_id,
                    new_seq,
                    encoded["type"],
                    encoded["payload"],
                    player_id,
                )
                if new_seq % SNAPSHOT_INTERVAL == 0:
                    await self._store.save_snapshot(
                        session, game_id, new_seq, dump_snapshot(new_state)
                    )
                return SubmitResult(sequence=new_seq, state=new_state)
        except IntegrityError as exc:
            raise ConflictError(
                f"Sequence {new_seq} already exists for game {game_id}"
            ) from exc

    # ------------------------------------------------------------------ #
    # Frontend projections (Phase 9)                                       #
    # ------------------------------------------------------------------ #

    async def get_view(self, game_id: int) -> dict[str, object]:
        """Render view-model (board / stocks / players / companies) for the UI."""
        async with self._session_factory() as session:
            sequence = await self._store.max_sequence(session, game_id)
            state = await self._replay(session, game_id, None)
        return build_view(state, sequence)

    async def get_legal_actions(self, game_id: int, player_id: str) -> dict[str, object]:
        """Concrete legal actions for ``player_id`` in the current phase."""
        state = await self.get_state(game_id)
        return legal_actions(state, player_id)
