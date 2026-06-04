"""Tests for Phase 4: Action System & State Machine.

Each class maps to one acceptance criterion from issue #5.
Rule references point to the Hans-im-Glück 1835 rulebook.
"""
from __future__ import annotations

import dataclasses

import pytest

from eg1835.domain.actions import (
    BuyShareFromBank,
    BuyTrainFromBank,
    BuyTrainFromCompany,
    DeclareDividend,
    LayTile,
    Pass,
    PlaceStation,
    RunTrains,
    SellShares,
    UpgradeTile,
    WithholdDividend,
)
from eg1835.domain.fsm import GameLoopPhase, ORPhase
from eg1835.domain.game_state import GameState
from eg1835.domain.result import Err, Ok

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _ar_state(num_players: int = 3) -> GameState:
    """GameState in a regular AR with a freshly reset pass chain."""
    return dataclasses.replace(
        GameState.initial(num_players),
        game_loop_phase=GameLoopPhase.AR,
    )


def _or_state(or_phase: ORPhase = ORPhase.BUILD) -> GameState:
    """GameState placed in an OR at the given sub-phase."""
    base = GameState.initial(3)
    return dataclasses.replace(
        base,
        game_loop_phase=GameLoopPhase.OR,
        or_phase=or_phase,
        active_company_id="BY",
        company_cash={"BY": 10_000},  # effectively unlimited funds
        available_trains={1: 9, 2: 8, 3: 6, 4: 5, 5: 3, 6: 2},
    )


# ---------------------------------------------------------------------------
# 1. Property-Test: apply is deterministic
# ---------------------------------------------------------------------------


class TestApplyDeterministic:
    """Calling apply twice on the same (state, action) pair must yield equal results."""

    def test_pass_in_ar_is_deterministic(self) -> None:
        state = _ar_state()
        action = Pass(player_id="Player 1")
        assert action.apply(state) == action.apply(state)

    def test_sell_in_ar_is_deterministic(self) -> None:
        state = _ar_state()
        action = SellShares(player_id="Player 1", company_id="BY", percent=10)
        assert action.apply(state) == action.apply(state)

    def test_buy_train_is_deterministic(self) -> None:
        state = _or_state(ORPhase.BUY_TRAIN)
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=2)
        assert action.apply(state) == action.apply(state)

    def test_run_trains_is_deterministic(self) -> None:
        state = _or_state(ORPhase.RUN)
        action = RunTrains(player_id="Player 1", company_id="BY", route_values=[30, 20])
        assert action.apply(state) == action.apply(state)


# ---------------------------------------------------------------------------
# 2. Property-Test: validate succeeds → apply does not raise
# ---------------------------------------------------------------------------


class TestValidateImpliesApplySafe:
    """If validate returns Ok, apply must never raise an exception."""

    @pytest.mark.parametrize(
        "action",
        [
            Pass(player_id="Player 1"),
            SellShares(player_id="Player 1", company_id="BY", percent=10),
            BuyShareFromBank(player_id="Player 1", company_id="BY", percent=10),
        ],
    )
    def test_ar_actions_safe_after_validate(
        self, action: Pass | SellShares | BuyShareFromBank
    ) -> None:
        state = _ar_state()
        result = action.validate(state)
        if isinstance(result, Ok):
            action.apply(state)  # must not raise

    def test_lay_tile_safe_after_validate(self) -> None:
        state = _or_state(ORPhase.BUILD)
        action = LayTile(player_id="Player 1", tile_id=6, q=2, r=1)
        result = action.validate(state)
        if isinstance(result, Ok):
            action.apply(state)

    def test_run_trains_safe_after_validate(self) -> None:
        state = _or_state(ORPhase.RUN)
        action = RunTrains(player_id="Player 1", company_id="BY", route_values=[40])
        result = action.validate(state)
        assert isinstance(result, Ok)
        action.apply(state)

    def test_buy_train_safe_after_validate(self) -> None:
        state = _or_state(ORPhase.BUY_TRAIN)
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=1)
        result = action.validate(state)
        assert isinstance(result, Ok)
        action.apply(state)

    def test_buy_train_validate_fails_no_stock(self) -> None:
        state = dataclasses.replace(
            _or_state(ORPhase.BUY_TRAIN),
            available_trains={1: 0, 2: 8, 3: 6, 4: 5, 5: 3, 6: 2},
        )
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=1)
        assert isinstance(action.validate(state), Err)

    def test_buy_train_validate_fails_insufficient_funds(self) -> None:
        state = dataclasses.replace(
            _or_state(ORPhase.BUY_TRAIN),
            company_cash={"BY": 0},
        )
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=2)
        assert isinstance(action.validate(state), Err)


# ---------------------------------------------------------------------------
# 3. FSM-Test: OR sub-phase order is enforced (BUILD→STATION→RUN→BUY_TRAIN)
# ---------------------------------------------------------------------------


class TestORPhaseOrder:
    """Actions are only valid in their designated OR sub-phase (rule 5.4)."""

    def test_run_trains_rejected_in_build_phase(self) -> None:
        state = _or_state(ORPhase.BUILD)
        action = RunTrains(player_id="Player 1", company_id="BY", route_values=[20])
        assert isinstance(action.validate(state), Err)

    def test_lay_tile_rejected_outside_build_phase(self) -> None:
        for phase in (ORPhase.STATION, ORPhase.RUN, ORPhase.BUY_TRAIN):
            state = _or_state(phase)
            action = LayTile(player_id="Player 1", tile_id=6, q=2, r=1)
            assert isinstance(action.validate(state), Err), f"LayTile accepted in {phase}"

    def test_declare_dividend_rejected_outside_dividend_phase(self) -> None:
        for phase in (ORPhase.BUILD, ORPhase.STATION, ORPhase.RUN, ORPhase.BUY_TRAIN):
            state = _or_state(phase)
            action = DeclareDividend(player_id="Player 1", company_id="BY", amount=60)
            assert isinstance(action.validate(state), Err), f"DeclareDividend accepted in {phase}"

    def test_buy_train_rejected_in_run_phase(self) -> None:
        state = _or_state(ORPhase.RUN)
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=1)
        assert isinstance(action.validate(state), Err)

    def test_place_station_accepted_only_in_station_phase(self) -> None:
        for phase in (ORPhase.BUILD, ORPhase.RUN, ORPhase.BUY_TRAIN):
            state = _or_state(phase)
            action = PlaceStation(player_id="Player 1", company_id="BY", q=3, r=0)
            assert isinstance(action.validate(state), Err), f"PlaceStation accepted in {phase}"
        state = _or_state(ORPhase.STATION)
        assert isinstance(
            PlaceStation(player_id="Player 1", company_id="BY", q=3, r=0).validate(state), Ok
        )

    def test_full_or_sequence_transitions_correctly(self) -> None:
        """Walk through the full BUILD→…→DONE sequence using Pass and real actions."""
        state = _or_state(ORPhase.BUILD)
        assert state.or_phase == ORPhase.BUILD

        # BUILD → STATION via Pass
        state = Pass(player_id="Player 1").apply(state)
        assert state.or_phase == ORPhase.STATION

        # STATION → RUN via Pass
        state = Pass(player_id="Player 1").apply(state)
        assert state.or_phase == ORPhase.RUN

        # RUN → DIVIDEND_DECISION via RunTrains
        state = RunTrains(
            player_id="Player 1", company_id="BY", route_values=[30]
        ).apply(state)
        assert state.or_phase == ORPhase.DIVIDEND_DECISION

        # DIVIDEND_DECISION → BUY_TRAIN via DeclareDividend
        state = DeclareDividend(
            player_id="Player 1", company_id="BY", amount=30
        ).apply(state)
        assert state.or_phase == ORPhase.BUY_TRAIN

        # BUY_TRAIN → DONE via Pass
        state = Pass(player_id="Player 1").apply(state)
        assert state.or_phase == ORPhase.DONE

    def test_withhold_dividend_also_transitions_to_buy_train(self) -> None:
        state = _or_state(ORPhase.DIVIDEND_DECISION)
        state = WithholdDividend(player_id="Player 1", company_id="BY").apply(state)
        assert state.or_phase == ORPhase.BUY_TRAIN

    def test_or_actions_rejected_in_ar(self) -> None:
        state = _ar_state()
        assert isinstance(
            RunTrains(player_id="Player 1", company_id="BY", route_values=[]).validate(state), Err
        )
        assert isinstance(
            LayTile(player_id="Player 1", tile_id=6, q=0, r=0).validate(state), Err
        )


# ---------------------------------------------------------------------------
# 4. FSM-Test: phase change on loco purchase; multiple locos → multiple phases
# ---------------------------------------------------------------------------


class TestPhaseChangeOnLokoPurchase:
    def _buy_train_state(self, game_phase: int, **company_trains: list[int]) -> GameState:
        base = _or_state(ORPhase.BUY_TRAIN)
        return dataclasses.replace(
            base,
            game_phase=game_phase,
            company_trains=dict(company_trains),
        )

    def test_buying_higher_tier_advances_phase(self) -> None:
        state = self._buy_train_state(game_phase=1)
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=2).apply(state)
        assert state.game_phase == 2

    def test_buying_same_tier_does_not_change_phase(self) -> None:
        state = self._buy_train_state(game_phase=2)
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=2).apply(state)
        assert state.game_phase == 2  # already in phase 2

    def test_phase4_purchase_scraps_tier2_trains(self) -> None:
        """Buying tier-4 (5-loco) scraps all tier-2 (3-locos) on the board."""
        state = self._buy_train_state(
            game_phase=3, BY=[2, 3], SA=[2, 2]  # companies own tier-2 and tier-3 trains
        )
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=4).apply(state)
        assert state.game_phase == 4
        # All tier-2 trains removed from every company.
        assert 2 not in state.company_trains.get("BY", [])
        assert 2 not in state.company_trains.get("SA", [])
        # Tier-3 trains are untouched.
        assert 3 in state.company_trains.get("BY", [])

    def test_phase5_purchase_scraps_tier3_trains(self) -> None:
        """Buying tier-5 (6-loco) scraps all tier-3 (4-locos)."""
        state = self._buy_train_state(game_phase=4, BY=[3, 4], SA=[3])
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=5).apply(state)
        assert state.game_phase == 5
        assert 3 not in state.company_trains.get("BY", [])
        assert 3 not in state.company_trains.get("SA", [])
        assert 4 in state.company_trains.get("BY", [])

    def test_multiple_purchases_trigger_multiple_phase_changes(self) -> None:
        """Successive purchases by different companies each advance the phase."""
        state = self._buy_train_state(game_phase=3, BY=[2, 3], SA=[3])

        # Company BY buys tier-4 → phase 4, tier-2 scrapped.
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", tier=4).apply(state)
        assert state.game_phase == 4
        assert 2 not in state.company_trains.get("BY", [])

        # Company SA buys tier-5 → phase 5, tier-3 scrapped.
        state = BuyTrainFromBank(player_id="Player 2", company_id="SA", tier=5).apply(state)
        assert state.game_phase == 5
        assert 3 not in state.company_trains.get("SA", [])
        assert 3 not in state.company_trains.get("BY", [])


# ---------------------------------------------------------------------------
# 5. AR end criterion: sales do not break the consecutive-pass chain (rule 2.3)
# ---------------------------------------------------------------------------


class TestAREndCondition:
    """Rule 2.3: AR ends when all players pass in turn without anyone buying.
    Selling counts as a non-buy; it does *not* reset the chain.
    """

    def test_pass_increments_chain(self) -> None:
        state = _ar_state(3)
        state = Pass(player_id="Player 1").apply(state)
        assert state.ar_consecutive_passes == 1

    def test_sell_increments_chain_like_pass(self) -> None:
        """Selling is a non-buy; the pass chain advances (doesn't reset)."""
        state = _ar_state(3)
        state = Pass(player_id="Player 1").apply(state)
        assert state.ar_consecutive_passes == 1
        state = SellShares(player_id="Player 2", company_id="BY", percent=10).apply(state)
        assert state.ar_consecutive_passes == 2  # NOT reset to 0

    def test_buy_resets_chain(self) -> None:
        state = _ar_state(3)
        state = Pass(player_id="Player 1").apply(state)
        assert state.ar_consecutive_passes == 1
        state = BuyShareFromBank(
            player_id="Player 2", company_id="BY", percent=10
        ).apply(state)
        assert state.ar_consecutive_passes == 0  # reset

    def test_ar_ends_after_all_players_pass(self) -> None:
        """Three passes in a row end the AR (transition to OR)."""
        state = _ar_state(3)
        for player in state.players:
            state = Pass(player_id=player).apply(state)
        assert state.game_loop_phase == GameLoopPhase.OR
        assert state.ar_consecutive_passes == 0

    def test_sell_does_not_prevent_ar_end(self) -> None:
        """Pass, Sell, Pass sequence still ends the AR for 3 players."""
        state = _ar_state(3)
        # P1 passes, P2 sells, P3 passes → all three have not bought → AR ends.
        state = Pass(player_id="Player 1").apply(state)      # chain = 1
        state = SellShares(player_id="Player 2", company_id="BY", percent=10).apply(state)
        # chain = 2
        state = Pass(player_id="Player 3").apply(state)      # chain = 3 → AR ends
        assert state.game_loop_phase == GameLoopPhase.OR

    def test_buy_in_middle_resets_and_requires_full_new_cycle(self) -> None:
        """If P2 buys mid-chain, a full new cycle without buying is required."""
        state = _ar_state(3)
        state = Pass(player_id="Player 1").apply(state)      # chain = 1
        state = BuyShareFromBank(
            player_id="Player 2", company_id="BY", percent=10
        ).apply(state)  # chain = 0
        state = Pass(player_id="Player 3").apply(state)      # chain = 1
        state = Pass(player_id="Player 1").apply(state)      # chain = 2
        # Still in AR: only 2 consecutive passes, need 3.
        assert state.game_loop_phase == GameLoopPhase.AR
        state = Pass(player_id="Player 2").apply(state)      # chain = 3 → ends
        assert state.game_loop_phase == GameLoopPhase.OR

    def test_buy_train_from_company_validates_ownership(self) -> None:
        """BuyTrainFromCompany rejects when the source company lacks the tier."""
        state = _or_state(ORPhase.BUY_TRAIN)
        action = BuyTrainFromCompany(
            player_id="Player 1",
            company_id="SA",
            from_company_id="BY",
            tier=3,
        )
        assert isinstance(action.validate(state), Err)

    def test_upgrade_tile_rejected_outside_build(self) -> None:
        state = _or_state(ORPhase.STATION)
        action = UpgradeTile(player_id="Player 1", tile_id=41, q=3, r=0)
        assert isinstance(action.validate(state), Err)
