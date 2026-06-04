"""Phase 8 – end-of-game logic (rule 6)."""
from __future__ import annotations

import dataclasses

from eg1835.domain.fsm import GameLoopPhase
from eg1835.domain.game_end import (
    bank_is_empty,
    complete_operating_round,
    complete_stock_round,
    final_scores,
    pay_player_from_bank,
)
from eg1835.domain.game_state import GameState


def _state(**extra: object) -> GameState:
    return dataclasses.replace(GameState.initial(3), **extra)  # type: ignore[arg-type]


class TestBankEmptyInOR:
    """Bank empty during an OR → finish the running OR, then end (rule 6.1)."""

    def test_drain_in_or_schedules_and_ends_after_one_or(self) -> None:
        state = _state(game_loop_phase=GameLoopPhase.OR, bank_balance=100)
        # A payout the bank cannot fully cover drains it and notes the shortfall.
        state = pay_player_from_bank(state, "Player 1", 250)
        assert bank_is_empty(state)
        assert state.end_pending is True
        assert state.bank_owed["Player 1"] == 150  # 250 requested, 100 paid
        assert state.game_over is False
        # Finishing the current OR ends the game.
        state = complete_operating_round(state)
        assert state.game_over is True


class TestBankEmptyInAR:
    """Bank empty during an AR → finish the AR and one more OR (rule 6.1)."""

    def test_end_only_after_one_further_or(self) -> None:
        state = _state(game_loop_phase=GameLoopPhase.AR, bank_balance=0)
        state = pay_player_from_bank(state, "Player 1", 40)
        assert state.end_pending is True
        assert state.bank_owed["Player 1"] == 40

        # The stock round finishing does NOT end the game yet.
        state = complete_stock_round(state)
        assert state.game_over is False
        # The following operating round does.
        state = complete_operating_round(state)
        assert state.game_over is True


class TestFinalSettlement:
    """Rule 6.2: cash + owed + share value; company assets excluded."""

    def test_scores_include_owed_and_share_value(self) -> None:
        state = _state(
            cash_per_player={"Player 1": 500, "Player 2": 300, "Player 3": 0},
            bank_owed={"Player 1": 150},
            share_prices={"BY": 100, "SA": 120},
            player_shares={
                "Player 1": {"BY": 30},  # 3 certs × 100
                "Player 2": {"SA": 20},  # 2 certs × 120
                "Player 3": {},
            },
            company_cash={"BY": 9999},  # company assets must NOT count
        )
        scores = final_scores(state)
        assert scores["Player 1"] == 500 + 150 + 300
        assert scores["Player 2"] == 300 + 240
        assert scores["Player 3"] == 0

    def test_bankrupt_player_scores_zero(self) -> None:
        state = _state(
            cash_per_player={"Player 1": 999},
            bankrupt_players=frozenset({"Player 1"}),
        )
        assert final_scores(state)["Player 1"] == 0
