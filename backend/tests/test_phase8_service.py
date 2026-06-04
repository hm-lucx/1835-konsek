"""Phase 8 – GameService: optimistic locking, replay and snapshots."""
from __future__ import annotations

import asyncio
import dataclasses
import time
from collections.abc import AsyncIterator
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from eg1835.application.game_service import ConflictError, GameService, SubmitResult
from eg1835.domain.actions import BuyStartItem, Pass
from eg1835.domain.fsm import GameLoopPhase
from eg1835.domain.game_state import GameState
from eg1835.domain.serialization import dump_snapshot
from eg1835.infrastructure.db import Base, create_session_factory
from eg1835.infrastructure.repository import EventStore


async def _make_service(engine: AsyncEngine) -> GameService:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return GameService(create_session_factory(engine))


@pytest_asyncio.fixture
async def service() -> AsyncIterator[GameService]:
    """In-memory service sharing a single connection (sequential tests)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield await _make_service(engine)
    await engine.dispose()


@pytest_asyncio.fixture
async def file_service(tmp_path: object) -> AsyncIterator[GameService]:
    """File-backed service so separate sessions get separate connections."""
    db_path = f"{tmp_path}/concurrency.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", connect_args={"timeout": 30}
    )
    yield await _make_service(engine)
    await engine.dispose()


class TestOptimisticLocking:
    async def test_idempotent_submit_second_is_conflict(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        result = await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        assert result.sequence == 1
        # Same expected_seq again → the sequence is taken → conflict (HTTP 409).
        with pytest.raises(ConflictError):
            await service.submit_action(
                game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="LD"), 0
            )

    async def test_concurrent_submit_one_wins_one_conflicts(
        self, file_service: GameService
    ) -> None:
        game_id = await file_service.create_game(3)
        actions = (
            file_service.submit_action(
                game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
            ),
            file_service.submit_action(
                game_id, "Player 2", BuyStartItem(player_id="Player 2", item_id="LD"), 0
            ),
        )
        results = await asyncio.gather(*actions, return_exceptions=True)
        wins = [r for r in results if isinstance(r, SubmitResult)]
        conflicts = [r for r in results if isinstance(r, ConflictError)]
        assert len(wins) == 1
        assert len(conflicts) == 1

    async def test_event_store_rejects_duplicate_sequence(
        self, file_service: GameService
    ) -> None:
        # The UNIQUE(game_id, sequence) guard is what makes locking optimistic.
        store = EventStore()
        sf = file_service._session_factory  # noqa: SLF001 - white-box check
        game_id = await file_service.create_game(3)
        async with sf() as s1, s1.begin():
            await store.append_event(s1, game_id, 1, "Pass", {"player_id": "P1"}, "P1")
        with pytest.raises(IntegrityError):
            async with sf() as s2, s2.begin():
                await store.append_event(s2, game_id, 1, "Pass", {"player_id": "P2"}, "P2")


class TestReplay:
    async def test_replay_reconstructs_state(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        state = await service.get_state(game_id)
        assert state.cash_per_player["Player 1"] == 500  # 600 − 100 (NF)
        assert await service.current_sequence(game_id) == 1

    async def test_replay_uses_snapshot_plus_delta(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        store = EventStore()
        sf = service._session_factory  # noqa: SLF001
        snap = dataclasses.replace(GameState.initial(3), game_loop_phase=GameLoopPhase.AR)
        async with sf() as session, session.begin():
            await store.save_snapshot(session, game_id, 5, dump_snapshot(snap))
            await store.append_event(session, game_id, 6, "Pass", {"player_id": "P1"}, "P1")
            await store.append_event(session, game_id, 7, "Pass", {"player_id": "P2"}, "P2")
        # Replay loads the snapshot at 5 and applies only events 6 and 7.
        state = await service.replay(game_id, until_seq=7)
        assert state.ar_consecutive_passes == 2

    async def test_replay_1000_events_with_snapshot_under_one_second(
        self, service: GameService
    ) -> None:
        game_id = await service.create_game(4)
        store = EventStore()
        sf = service._session_factory  # noqa: SLF001
        snapshot_state = GameState.initial(4)
        async with sf() as session, session.begin():
            for seq in range(1, 1001):
                await store.append_event(
                    session, game_id, seq, "Pass", {"player_id": "Player 1"}, "Player 1"
                )
            await store.save_snapshot(session, game_id, 1000, dump_snapshot(snapshot_state))

        start = time.perf_counter()
        state = await service.replay(game_id, until_seq=1000)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
        # The snapshot at 1000 is used; no events are replayed past it.
        assert state == snapshot_state


class TestLegalActions:
    async def test_start_packet_phase_offers_buy_start_item(
        self, service: GameService
    ) -> None:
        game_id = await service.create_game(3)
        result = await service.get_legal_actions(game_id, "Player 1")
        actions = cast("list[dict[str, object]]", result["actions"])
        assert "buy_start_item" in {a["type"] for a in actions}

    async def test_pass_action_round_trips_through_service(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        result = await service.submit_action(game_id, "Player 1", Pass(player_id="Player 1"), 0)
        assert result.sequence == 1
