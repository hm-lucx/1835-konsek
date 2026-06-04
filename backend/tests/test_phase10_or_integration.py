"""Phase 10 (Teil 1) – OR integration: board state, routing revenue, OR flow."""
from __future__ import annotations

import dataclasses

from eg1835.domain.actions import (
    DeclareDividend,
    LayTile,
    PlaceStation,
    RunTrains,
)
from eg1835.domain.fsm import GameLoopPhase, ORPhase
from eg1835.domain.game_state import GameState
from eg1835.domain.or_flow import current_actor, progress_or
from eg1835.domain.or_revenue import company_revenue


def _or(or_phase: ORPhase = ORPhase.BUILD, *, active: str = "BY", **extra: object) -> GameState:
    base = GameState.initial(3)
    defaults: dict[str, object] = {
        "game_loop_phase": GameLoopPhase.OR,
        "or_phase": or_phase,
        "active_company_id": active,
    }
    defaults.update(extra)
    return dataclasses.replace(base, **defaults)  # type: ignore[arg-type]


class TestBoardMutation:
    def test_lay_tile_records_placement(self) -> None:
        state = _or(ORPhase.BUILD, company_directors={"BY": "Player 1"})
        state = LayTile(player_id="Player 1", tile_id=7, q=5, r=3).apply(state)
        assert state.placed_tiles["5,3"] == 7

    def test_place_station_records_marker(self) -> None:
        state = _or(ORPhase.STATION, company_cash={"BY": 1000})
        state = PlaceStation(
            player_id="Player 1", company_id="BY", q=4, r=2, distance=1
        ).apply(state)
        assert "BY" in state.placed_stations["4,2"]


class TestRoutingRevenue:
    def test_revenue_from_home_and_train(self) -> None:
        # BY's home (München) connects to Augsburg; a 2-Lok runs both (30 + 10).
        state = _or(colored_phase=1, company_trains={"BY": [1]})  # tier 1 = "2"-Lok
        assert company_revenue(state, "BY") == 40

    def test_no_train_means_no_revenue(self) -> None:
        state = _or(colored_phase=1, company_trains={"BY": []})
        assert company_revenue(state, "BY") == 0

    def test_run_trains_stores_revenue_and_dividend_pays_from_bank(self) -> None:
        state = _or(
            ORPhase.RUN,
            colored_phase=1,
            company_trains={"BY": [1]},
            company_directors={"BY": "Player 1"},
            player_shares={"Player 1": {"BY": 100}, "Player 2": {}, "Player 3": {}},
            share_prices={"BY": 100},
            company_cash={"BY": 0},
        )
        bank_before = state.bank_balance
        state = RunTrains(player_id="Player 1", company_id="BY").apply(state)
        assert state.last_run_revenue["BY"] == 40
        assert state.or_phase == ORPhase.DIVIDEND_DECISION

        # amount=0 → use the computed revenue; full holder gets all 40 from the bank.
        state = DeclareDividend(player_id="Player 1", company_id="BY", amount=0).apply(state)
        assert state.cash_per_player["Player 1"] == 600 + 40
        assert state.bank_balance == bank_before - 40
        assert state.share_prices["BY"] == 110  # payout steps price up


class TestORFlow:
    def test_or_initialises_operating_order_by_price(self) -> None:
        state = _or(
            active=None,  # type: ignore[arg-type]
            company_status={"BY": "launched", "SA": "launched"},
            share_prices={"BY": 100, "SA": 120},
            company_directors={"BY": "Player 1", "SA": "Player 2"},
        )
        state = progress_or(state)
        # Higher price operates first (rule 5.3.4).
        assert state.operating_order == ("SA", "BY")
        assert state.active_company_id == "SA"
        assert state.or_phase == ORPhase.BUILD

    def test_done_hands_over_to_next_company(self) -> None:
        state = _or(
            ORPhase.DONE,
            active="SA",
            operating_order=("SA", "BY"),
            operating_index=0,
            company_status={"BY": "launched", "SA": "launched"},
            company_directors={"BY": "Player 1", "SA": "Player 2"},
        )
        state = progress_or(state)
        assert state.active_company_id == "BY"
        assert "SA" in state.companies_operated_this_or
        assert state.or_phase == ORPhase.BUILD

    def test_last_company_done_starts_stock_round(self) -> None:
        state = _or(
            ORPhase.DONE,
            active="BY",
            operating_order=("BY",),
            operating_index=0,
            ors_per_set=1,
            ors_completed_in_set=0,
            company_status={"BY": "launched"},
            company_directors={"BY": "Player 1"},
        )
        state = progress_or(state)
        assert state.game_loop_phase == GameLoopPhase.AR
        assert state.active_company_id is None

    def test_or_set_chains_second_round(self) -> None:
        state = _or(
            ORPhase.DONE,
            active="BY",
            operating_order=("BY",),
            operating_index=0,
            ors_per_set=2,
            ors_completed_in_set=0,
            company_status={"BY": "launched"},
            company_directors={"BY": "Player 1"},
        )
        state = progress_or(state)
        # Still an OR (second of the set), fresh turn for the first company.
        assert state.game_loop_phase == GameLoopPhase.OR
        assert state.ors_completed_in_set == 1
        assert state.active_company_id == "BY"

    def test_bank_empty_ends_game_at_or_boundary(self) -> None:
        state = _or(
            ORPhase.DONE,
            active="BY",
            operating_order=("BY",),
            operating_index=0,
            ors_per_set=1,
            company_status={"BY": "launched"},
            company_directors={"BY": "Player 1"},
            end_pending=True,
            pending_final_ors=1,
        )
        state = progress_or(state)
        assert state.game_over is True


class TestCurrentActor:
    def test_ar_actor_is_current_player(self) -> None:
        state = dataclasses.replace(
            GameState.initial(3),
            game_loop_phase=GameLoopPhase.AR,
            current_player_index=1,
        )
        assert current_actor(state) == "Player 2"

    def test_or_actor_is_director(self) -> None:
        state = _or(active="BY", company_directors={"BY": "Player 3"})
        assert current_actor(state) == "Player 3"

    def test_no_actor_when_game_over(self) -> None:
        assert current_actor(dataclasses.replace(GameState.initial(3), game_over=True)) is None
