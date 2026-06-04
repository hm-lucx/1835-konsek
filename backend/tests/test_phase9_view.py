"""Phase 9 – frontend view projection and concrete legal-action enumeration."""
from __future__ import annotations

import dataclasses
import json

from eg1835.application.view import build_view, legal_actions
from eg1835.domain.fsm import GameLoopPhase
from eg1835.domain.game_state import GameState


class TestBuildView:
    def test_view_has_all_render_sections(self) -> None:
        view = build_view(GameState.initial(3), sequence=0)
        for key in ("board", "tiles", "stocks", "players", "companies", "train_prices"):
            assert key in view
        json.dumps(view)  # the whole view must be JSON-serializable

    def test_board_positions_are_keyed_axially(self) -> None:
        view = build_view(GameState.initial(3), sequence=0)
        positions = view["board"]["positions"]
        assert "3,0" in positions
        assert positions["3,0"]["coordinate"] == {"q": 3, "r": 0}
        assert positions["3,0"]["location_name"] == "Hamburg"

    def test_players_expose_cash_and_paper_limit(self) -> None:
        view = build_view(GameState.initial(3), sequence=0)
        player = view["players"][0]
        assert player["cash"] == 600
        assert player["paper_limit"] == 19  # 3-player base limit

    def test_stocks_group_companies_by_price_for_stacking(self) -> None:
        state = dataclasses.replace(
            GameState.initial(3),
            share_prices={"BY": 100, "SA": 100, "BA": 90},
        )
        stocks = build_view(state, sequence=0)["stocks"]
        assert stocks["share_price_order"]["100"] == ["BY", "SA"]
        assert stocks["share_price_order"]["90"] == ["BA"]

    def test_train_prices_match_promotion_table(self) -> None:
        prices = build_view(GameState.initial(3), sequence=0)["train_prices"]
        assert prices["4+4"] == 440
        assert prices["6+6"] == 720


class TestLegalActions:
    def test_start_packet_offers_buyable_items_and_pass(self) -> None:
        result = legal_actions(GameState.initial(3), "Player 1")
        assert result["phase"] == "start_packet_ar"
        types = {a["type"] for a in result["actions"]}
        assert "buy_start_item" in types
        assert "pass" in types
        # Action fields are inline (frontend contract), snake_case type.
        buy = next(a for a in result["actions"] if a["type"] == "buy_start_item")
        assert "item_id" in buy

    def test_ar_offers_buy_sell_pass(self) -> None:
        state = dataclasses.replace(
            GameState.initial(3),
            game_loop_phase=GameLoopPhase.AR,
            unsold_shares={"BY": 100},
            pool_shares={"SA": 20},
            player_shares={"Player 1": {"BY": 20}, "Player 2": {}, "Player 3": {}},
            share_prices={"BY": 100, "SA": 100},
        )
        actions = legal_actions(state, "Player 1")["actions"]
        types = {a["type"] for a in actions}
        assert {"buy_share_from_bank", "buy_share_from_pool", "sell_shares", "pass"} <= types

    def test_no_actions_when_game_over(self) -> None:
        state = dataclasses.replace(GameState.initial(3), game_over=True)
        assert legal_actions(state, "Player 1")["actions"] == []
