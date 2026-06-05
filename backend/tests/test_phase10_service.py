"""Phase 10 (Teil 1) – service-level turn enforcement and start-packet → OR flow."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from eg1835.application.game_service import GameService, TurnError
from eg1835.domain.actions import BuyStartItem
from eg1835.infrastructure.db import Base, create_session_factory


@pytest_asyncio.fixture
async def service() -> AsyncIterator[GameService]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield GameService(create_session_factory(engine))
    await engine.dispose()


class TestTurnEnforcement:
    async def test_out_of_turn_action_is_rejected(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        # Player 1 is the start player; Player 2 may not act yet.
        with pytest.raises(TurnError):
            await service.submit_action(
                game_id, "Player 2", BuyStartItem(player_id="Player 2", item_id="NF"), 0
            )

    async def test_current_player_may_act(self, service: GameService) -> None:
        game_id = await service.create_game(3)
        result = await service.submit_action(
            game_id, "Player 1", BuyStartItem(player_id="Player 1", item_id="NF"), 0
        )
        assert result.sequence == 1


class TestStartPacketToOperatingRound:
    async def test_buying_out_the_packet_enters_an_operating_round(
        self, service: GameService
    ) -> None:
        game_id = await service.create_game(3)

        for _ in range(20):  # safety bound; the packet has 6 items
            view = await service.get_view(game_id)
            if view["phase"] != "start_packet_ar":
                break
            actor = view["current_actor"]
            assert isinstance(actor, str)
            legal = await service.get_legal_actions(game_id, actor)
            actions = cast("list[dict[str, Any]]", legal["actions"])
            buys = [a for a in actions if a["type"] == "buy_start_item"]
            assert buys, "start-packet AR must offer buyable items"
            item_id = str(buys[0]["item_id"])
            await service.submit_action(
                game_id,
                actor,
                BuyStartItem(player_id=actor, item_id=item_id),
                cast("int", view["sequence"]),
            )

        view = await service.get_view(game_id)
        # The packet is empty → the first operating round has begun with a
        # concrete operating company and a resolvable actor.
        assert view["phase"] == "or"
        assert view["active_company_id"] is not None
        assert view["current_actor"] is not None
