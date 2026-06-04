"""Tests for Phase 6: Operating-round logic.

Each class maps to one acceptance criterion from issue #7 (Phase 6).
Rule references point to the Hans-im-Glück 1835 rulebook (sections 5.2, 5.4,
5.5.2, 5.5.3.12, 5.5.4).
"""
from __future__ import annotations

import dataclasses

from eg1835.domain.actions import (
    BuyTrainFromBank,
    BuyTrainFromCompany,
    DeclareDividend,
    LayTile,
    Pass,
    PlaceStation,
    RunTrains,
    WithholdDividend,
)
from eg1835.domain.fsm import GameLoopPhase, ORPhase
from eg1835.domain.game_state import GameState
from eg1835.domain.result import Err, Ok

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _or_state(
    or_phase: ORPhase = ORPhase.BUY_TRAIN,
    *,
    colored_phase: int = 1,
    **extra: object,
) -> GameState:
    """GameState in an OR turn for the AG "BY" at the given sub-phase."""
    base = GameState.initial(3)
    defaults: dict[str, object] = {
        "game_loop_phase": GameLoopPhase.OR,
        "or_phase": or_phase,
        "active_company_id": "BY",
        "colored_phase": colored_phase,
        "company_cash": {"BY": 10_000},
    }
    defaults.update(extra)
    return dataclasses.replace(base, **defaults)  # type: ignore[arg-type]


def _end_one_ar(state: GameState) -> GameState:
    """Drive *state* through a complete 3-player AR (all pass) back to OR."""
    ar = dataclasses.replace(
        state,
        game_loop_phase=GameLoopPhase.AR,
        or_phase=None,
        ar_consecutive_passes=0,
        current_player_index=0,
    )
    for player in ar.players:
        ar = Pass(player_id=player).apply(ar)
    return ar


# ---------------------------------------------------------------------------
# 1. A full OR turn for one AG runs through every sub-phase without crashing.
# ---------------------------------------------------------------------------


class TestFullORCycle:
    """Acceptance: complete OR cycle for an AG without crash (rule 5.4)."""

    def test_build_to_done_sequence(self) -> None:
        state = _or_state(
            ORPhase.BUILD,
            company_cash={"BY": 1_000},
            share_prices={"BY": 100},
            company_directors={"BY": "Player 1"},
            player_shares={"Player 1": {"BY": 60}, "Player 2": {}, "Player 3": {}},
        )

        # BUILD: a phase-1 AG may lay two yellow tiles (rule 5.4.1).
        state = LayTile(player_id="Player 1", tile_id=6, q=0, r=0).apply(state)
        state = LayTile(player_id="Player 1", tile_id=7, q=1, r=0).apply(state)
        assert state.tiles_laid_this_turn["BY"] == 2
        # A third tile is rejected.
        assert isinstance(
            LayTile(player_id="Player 1", tile_id=8, q=2, r=0).validate(state), Err
        )

        # BUILD → STATION.
        state = Pass(player_id="Player 1").apply(state)
        assert state.or_phase == ORPhase.STATION

        # Pöppeln: a second station two fields from home costs 2 × 20 M.
        state = PlaceStation(
            player_id="Player 1", company_id="BY", q=3, r=0, distance=2
        ).apply(state)
        assert state.or_phase == ORPhase.RUN
        assert state.company_cash["BY"] == 1_000 - 40

        # Fahren.
        state = RunTrains(
            player_id="Player 1", company_id="BY", route_values=[100]
        ).apply(state)
        assert state.or_phase == ORPhase.DIVIDEND_DECISION

        # Auszahlen: director (60 %) collects 60 M; price moves up.
        state = DeclareDividend(
            player_id="Player 1", company_id="BY", amount=100
        ).apply(state)
        assert state.or_phase == ORPhase.BUY_TRAIN
        assert state.cash_per_player["Player 1"] == 600 + 60
        assert state.share_prices["BY"] == 110

        # Kaufen: buy the mandatory 2-Lok, then end the turn.
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="2").apply(
            state
        )
        assert state.company_trains["BY"] == [1]  # tier 1 = "2"-Lok
        state = Pass(player_id="Player 1").apply(state)
        assert state.or_phase == ORPhase.DONE


# ---------------------------------------------------------------------------
# 2. Share price moves on the dividend decision (rule 5.5.3.12).
# ---------------------------------------------------------------------------


class TestDividendPriceMovement:
    """Acceptance: price rise on payout with correct arrow transition."""

    def test_payout_steps_price_up(self) -> None:
        state = _or_state(ORPhase.DIVIDEND_DECISION, share_prices={"BY": 100})
        state = DeclareDividend(player_id="Player 1", company_id="BY", amount=50).apply(
            state
        )
        assert state.share_prices["BY"] == 110  # one field right (rule 5.5.3.12)

    def test_withhold_steps_price_down(self) -> None:
        state = _or_state(ORPhase.DIVIDEND_DECISION, share_prices={"BY": 100})
        state = WithholdDividend(player_id="Player 1", company_id="BY", amount=50).apply(
            state
        )
        assert state.share_prices["BY"] == 90  # one field left
        assert state.company_cash["BY"] == 10_000 + 50  # revenue saved in treasury


# ---------------------------------------------------------------------------
# 3. First 3-Lok starts phase 2; the OR count rises from the next AR (5.2).
# ---------------------------------------------------------------------------


class TestThreeLokStartsPhase2:
    """Acceptance: 3er-Kauf startet Phase 2; OR-Zähler wechselt auf 2 ab der nächsten AR."""

    def test_three_lok_advances_coloured_phase(self) -> None:
        state = _or_state(colored_phase=1)
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="3").apply(
            state
        )
        assert state.colored_phase == 2
        # OR count is scheduled but not yet active during the running OR set.
        assert state.pending_ors_per_set == 2
        assert state.ors_per_set == 1

    def test_or_count_becomes_two_after_next_ar(self) -> None:
        state = _or_state(colored_phase=1)
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="3").apply(
            state
        )
        state = _end_one_ar(state)
        assert state.ors_per_set == 2


# ---------------------------------------------------------------------------
# 4. First 4-Lok scraps every 2-Lok immediately (rule 5.5.4.14).
# ---------------------------------------------------------------------------


class TestFourLokScrapsTwoLoks:
    """Acceptance: 4er-Kauf entfernt alle 2er-Loks sofort."""

    def test_four_lok_removes_all_two_loks(self) -> None:
        state = _or_state(company_trains={"BY": [1, 2], "SA": [1]})
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="4").apply(
            state
        )
        # tier 1 = "2"-Lok scrapped everywhere; tier 2 = "3"-Lok survives.
        assert 1 not in state.company_trains["BY"]
        assert 1 not in state.company_trains["SA"]
        assert 2 in state.company_trains["BY"]
        # The 4-Lok merely *enables* Preußen; it does not force it.
        assert state.preussen_can_open is True
        assert state.preussen_must_open is False


# ---------------------------------------------------------------------------
# 5. First 4+4-Lok forces Preußen; the 5-Lok does not (rules 4.6, 5.5.4.14).
# ---------------------------------------------------------------------------


class TestFourPlusFourForcesPreussen:
    """Acceptance: 4+4-Kauf erzwingt Preußen-Aktivierung – nicht der 5er."""

    def test_four_plus_four_forces_preussen(self) -> None:
        state = _or_state(company_trains={"BY": [7]})  # tier 7 = "2+2"-Lok
        state = BuyTrainFromBank(
            player_id="Player 1", company_id="BY", train="4+4"
        ).apply(state)
        assert state.preussen_must_open is True
        assert state.preussen_can_open is True
        # All 2+2-Loks are scrapped (rule 5.5.4.14).
        assert 7 not in state.company_trains["BY"]

    def test_five_lok_does_not_force_preussen(self) -> None:
        state = _or_state()
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="5").apply(
            state
        )
        assert state.preussen_must_open is False


# ---------------------------------------------------------------------------
# 6. First 5-Lok converts remaining pre-Prussians + BS + HA; OR count → 3.
# ---------------------------------------------------------------------------


class TestFiveLokConversion:
    """Acceptance: 5er-Kauf erzwingt Umwandlung + OR-Zähler wechselt auf 3."""

    def test_five_lok_converts_and_starts_phase_three(self) -> None:
        state = _or_state(
            colored_phase=2,
            player_shares={
                "Player 1": {"BM": 30, "HA": 10},
                "Player 2": {"BP": 20},
                "Player 3": {},
            },
        )
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="5").apply(
            state
        )

        assert state.colored_phase == 3
        assert state.pending_ors_per_set == 3
        assert state.preussen_opened is True

        # Convertible companies are flagged converted...
        for company_id in ("BM", "BP", "HA"):
            assert state.company_status[company_id] == "converted"
        # ...and their holdings become Preußen shares.
        assert state.player_shares["Player 1"].get("BM") is None
        assert state.player_shares["Player 1"]["PR"] == 40
        assert state.player_shares["Player 2"]["PR"] == 20

    def test_or_count_becomes_three_after_next_ar(self) -> None:
        state = _or_state(colored_phase=2)
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="5").apply(
            state
        )
        state = _end_one_ar(state)
        assert state.ors_per_set == 3


# ---------------------------------------------------------------------------
# 7. The locomotive limit cannot be exceeded, even when a phase change would
#    scrap one of the company's trains (rule 5.5.4.7).
# ---------------------------------------------------------------------------


class TestLocomotiveLimit:
    """Acceptance: Loklimit-Überschreitung verboten, auch bei reduzierendem Phasenwechsel."""

    def test_buy_rejected_at_limit_even_if_purchase_would_scrap(self) -> None:
        # Phase 2 limit is 3; BY already owns three trains, two of them 2-Loks.
        state = _or_state(colored_phase=2, company_trains={"BY": [1, 1, 2]})
        # A 4-Lok would scrap the 2-Loks, but the limit check comes first.
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="4")
        assert isinstance(action.validate(state), Err)

    def test_buy_allowed_below_limit(self) -> None:
        state = _or_state(colored_phase=2, company_trains={"BY": [1, 2]})
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="4")
        assert isinstance(action.validate(state), Ok)


# ---------------------------------------------------------------------------
# 8. Buying a locomotive from another company is allowed from phase 2 (5.5.4.3).
# ---------------------------------------------------------------------------


class TestCrossCompanyPurchase:
    """Acceptance: Lok-Kauf von Mitspieler-Gesellschaft ab Phase 2."""

    def test_rejected_in_phase_one(self) -> None:
        state = _or_state(colored_phase=1, company_trains={"SA": [2]})
        action = BuyTrainFromCompany(
            player_id="Player 1", company_id="BY", from_company_id="SA", train="3"
        )
        assert isinstance(action.validate(state), Err)

    def test_allowed_from_phase_two_transfers_train_and_cash(self) -> None:
        state = _or_state(
            colored_phase=2,
            company_trains={"BY": [], "SA": [2]},
            company_cash={"BY": 500, "SA": 0},
        )
        action = BuyTrainFromCompany(
            player_id="Player 1",
            company_id="BY",
            from_company_id="SA",
            train="3",
            price=120,
        )
        assert isinstance(action.validate(state), Ok)
        state = action.apply(state)
        assert state.company_trains["BY"] == [2]
        assert state.company_trains["SA"] == []
        assert state.company_cash["BY"] == 380
        assert state.company_cash["SA"] == 120


# ---------------------------------------------------------------------------
# 9. The director finances a mandatory loco from private cash; the AG keeps 0 M
#    (rules 5.5.4.11–12).
# ---------------------------------------------------------------------------


class TestDirectorFinancing:
    """Acceptance: Direktor schießt Privatgeld zu, AG bleibt mit 0 M."""

    def test_director_covers_shortfall_company_ends_at_zero(self) -> None:
        state = _or_state(
            company_cash={"BY": 50},
            company_directors={"BY": "Player 1"},
        )
        director_cash_before = state.cash_per_player["Player 1"]
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="3")
        assert isinstance(action.validate(state), Ok)  # price 180, director covers 130
        state = action.apply(state)
        assert state.company_cash["BY"] == 0
        assert state.cash_per_player["Player 1"] == director_cash_before - 130

    def test_no_director_and_no_funds_is_rejected(self) -> None:
        state = _or_state(company_cash={"BY": 0}, company_directors={})
        action = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="3")
        assert isinstance(action.validate(state), Err)
