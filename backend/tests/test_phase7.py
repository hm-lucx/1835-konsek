"""Tests for Phase 7: special cases.

Each class maps to one acceptance criterion from issue #8 (Phase 7), plus one
test per private-railway ability.  Rule references point to the Hans-im-Glück
1835 rulebook (sections 3.1.3, 4, 5.5.2.10, 5.5.4.13).
"""
from __future__ import annotations

import dataclasses

from eg1835.domain.actions import (
    BuyMandatoryTrain,
    BuyTrainFromBank,
    ChooseBadenHomeStation,
    DeclareDividend,
    LayTile,
    OpenPreussen,
    UseNFAbility,
    UseOBAbility,
    UsePFBuildAbility,
    UsePFStationAbility,
    WithholdDividend,
    _successor_director,
)
from eg1835.domain.companies.privates.abilities import ML_FIELD, OB_FIELDS
from eg1835.domain.fsm import GameLoopPhase, ORPhase, train_limit_for_phase
from eg1835.domain.game_state import GameState
from eg1835.domain.result import Err, Ok

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _or(
    or_phase: ORPhase,
    *,
    active: str = "BY",
    colored_phase: int = 1,
    **extra: object,
) -> GameState:
    """GameState in an OR turn for ``active`` at the given sub-phase."""
    base = GameState.initial(3)
    defaults: dict[str, object] = {
        "game_loop_phase": GameLoopPhase.OR,
        "or_phase": or_phase,
        "active_company_id": active,
        "colored_phase": colored_phase,
    }
    defaults.update(extra)
    return dataclasses.replace(base, **defaults)  # type: ignore[arg-type]


# ===========================================================================
# Private-railway abilities (one test each) – rule 3.1.3
# ===========================================================================


class TestPrivateAbilities:
    def test_nf_places_free_station_and_closes(self) -> None:
        state = _or(
            ORPhase.STATION,
            company_directors={"BY": "Player 1"},
            private_owners={"NF": "Player 1"},
        )
        action = UseNFAbility(player_id="Player 1")
        assert isinstance(action.validate(state), Ok)
        state = action.apply(state)
        assert "NF" in state.closed_privates

    def test_nf_rejected_for_non_owner(self) -> None:
        state = _or(
            ORPhase.STATION,
            company_directors={"BY": "Player 1"},
            private_owners={"NF": "Player 1"},
        )
        assert isinstance(UseNFAbility(player_id="Player 2").validate(state), Err)

    def test_ob_closes_once_both_fields_built(self) -> None:
        state = _or(
            ORPhase.BUILD,
            company_directors={"BY": "Player 1"},
            private_owners={"OB": "Player 1"},
        )
        state = UseOBAbility(player_id="Player 1", field_id=OB_FIELDS[0]).apply(state)
        assert "OB" not in state.closed_privates  # one field only
        state = UseOBAbility(player_id="Player 1", field_id=OB_FIELDS[1]).apply(state)
        assert "OB" in state.closed_privates

    def test_pf_build_does_not_close(self) -> None:
        state = _or(
            ORPhase.BUILD,
            company_directors={"BY": "Player 1"},
            private_owners={"PF": "Player 1"},
        )
        state = UsePFBuildAbility(player_id="Player 1").apply(state)
        assert "PF" not in state.closed_privates
        assert ML_FIELD in state.built_fields


# ===========================================================================
# 1. Preußen opening scenario (chapter 4)
# ===========================================================================


class TestPreussenOpening:
    """Acceptance: 4-Lok → BP owner opens Preußen, Vorpreußische join, the
    locomotive limit is exceeded, and Preußen lands on price 154."""

    def _state(self, **extra: object) -> GameState:
        base = _or(
            ORPhase.BUILD,
            active="BP",
            colored_phase=2,
            preussen_can_open=True,
            player_shares={
                "Player 1": {"BP": 100},
                "Player 2": {"BM": 100},
                "Player 3": {"MD": 50},
            },
            company_cash={"BP": 200, "BM": 50, "MD": 30},
            company_trains={"BP": [1, 2], "BM": [1], "MD": [2]},
        )
        return dataclasses.replace(base, **extra)  # type: ignore[arg-type]

    def test_open_preussen_full_scenario(self) -> None:
        state = self._state()
        action = OpenPreussen(player_id="Player 1")
        assert isinstance(action.validate(state), Ok)
        state = action.apply(state)

        assert state.preussen_opened is True
        assert state.share_prices["PR"] == 154
        assert state.company_directors["PR"] == "Player 1"

        # Every held Vorpreußische converted into Preußen shares (rules 4.3).
        for cid in ("BP", "BM", "MD"):
            assert state.company_status[cid] == "converted"
        assert "BP" not in state.player_shares["Player 1"]
        assert state.player_shares["Player 2"]["PR"] == 100
        assert state.player_shares["Player 1"]["PR"] == 100

        # Annexed locomotives may exceed the limit (rule 5.5.4.9).
        assert len(state.company_trains["PR"]) == 4
        assert len(state.company_trains["PR"]) > train_limit_for_phase(2)
        assert state.company_trains["BP"] == []
        assert state.company_trains["BM"] == []

        # Capital = 154 × sold PR (0) + BP + annexed treasuries (rule 4.2/4.4).
        assert state.company_cash["PR"] == 200 + 50 + 30

    def test_open_requires_four_lok(self) -> None:
        state = self._state(preussen_can_open=False, preussen_must_open=False)
        assert isinstance(OpenPreussen(player_id="Player 1").validate(state), Err)

    def test_non_bp_owner_cannot_open(self) -> None:
        state = self._state()
        assert isinstance(OpenPreussen(player_id="Player 2").validate(state), Err)


# ===========================================================================
# 2. PF build + station in the same OR; only the station closes PF (3.1.3.3)
# ===========================================================================


class TestPFBuildAndStationSameOR:
    def test_only_station_closes_pf(self) -> None:
        build_state = _or(
            ORPhase.BUILD,
            company_directors={"BY": "Player 1"},
            private_owners={"PF": "Player 1"},
            company_status={"BA": "launched"},
            baden_home_chosen=True,
        )
        after_build = UsePFBuildAbility(player_id="Player 1").apply(build_state)
        assert "PF" not in after_build.closed_privates

        station_state = dataclasses.replace(after_build, or_phase=ORPhase.STATION)
        action = UsePFStationAbility(player_id="Player 1")
        assert isinstance(action.validate(station_state), Ok)
        after_station = action.apply(station_state)
        assert "PF" in after_station.closed_privates


# ===========================================================================
# 3. OB closes through a foreign company's build action (3.1.3.2)
# ===========================================================================


class TestOBForeignClose:
    def test_foreign_build_on_second_field_closes_ob(self) -> None:
        # Owner used the ability on one field; a foreign AG now builds the other.
        state = _or(
            ORPhase.BUILD,
            active="SA",  # a different company builds
            private_owners={"OB": "Player 1"},
            built_fields=frozenset({OB_FIELDS[0]}),
        )
        state = LayTile(
            player_id="Player 2", tile_id=7, q=1, r=1, field_id=OB_FIELDS[1]
        ).apply(state)
        assert "OB" in state.closed_privates


# ===========================================================================
# 4. Baden in operation: PF may not build M/L before Baden sets its home.
# ===========================================================================


class TestBadenReservation:
    def test_pf_station_rejected_before_baden_home(self) -> None:
        state = _or(
            ORPhase.STATION,
            company_directors={"BY": "Player 1"},
            private_owners={"PF": "Player 1"},
            company_status={"BA": "launched"},
            baden_home_chosen=False,
            built_fields=frozenset({ML_FIELD}),
        )
        assert isinstance(UsePFStationAbility(player_id="Player 1").validate(state), Err)

    def test_choose_baden_home_requires_built_field(self) -> None:
        not_built = _or(
            ORPhase.STATION,
            active="BA",
            company_directors={"BA": "Player 1"},
        )
        assert isinstance(
            ChooseBadenHomeStation(player_id="Player 1", q=0, r=0).validate(not_built), Err
        )
        built = dataclasses.replace(not_built, built_fields=frozenset({ML_FIELD}))
        action = ChooseBadenHomeStation(player_id="Player 1", q=0, r=0)
        assert isinstance(action.validate(built), Ok)
        assert action.apply(built).baden_home_chosen is True


# ===========================================================================
# 5. Double-use protection: BP already operated → Preußen pauses this OR (4.5)
# ===========================================================================


class TestDoubleUseProtection:
    def test_preussen_pauses_if_bp_already_operated(self) -> None:
        state = _or(
            ORPhase.BUILD,
            active="BP",
            preussen_can_open=True,
            player_shares={"Player 1": {"BP": 100}, "Player 2": {}, "Player 3": {}},
            company_cash={"BP": 100},
            company_trains={"BP": []},
            companies_operated_this_or=frozenset({"BP"}),
        )
        state = OpenPreussen(player_id="Player 1").apply(state)
        assert state.preussen_paused_this_or is True


# ===========================================================================
# 6. Bankruptcy ordering and aftermath (rules 5.5.4.11–13)
# ===========================================================================


class TestBankruptcy:
    def test_full_cascade_ends_in_bankruptcy(self) -> None:
        # Treasury 0, director broke, only an unsellable director cert → bankrupt.
        state = _or(
            ORPhase.BUY_TRAIN,
            company_directors={"BY": "Player 1"},
            company_cash={"BY": 0},
            cash_per_player={"Player 1": 0, "Player 2": 0, "Player 3": 0},
            player_shares={
                "Player 1": {"BY": 20},  # director cert, may not be sold
                "Player 2": {"BY": 10},
                "Player 3": {},
            },
            start_player_index=1,
        )
        state = BuyMandatoryTrain(player_id="Player 1", company_id="BY", train="3").apply(
            state
        )

        assert "Player 1" in state.bankrupt_players
        assert state.cash_per_player["Player 1"] == 0
        assert state.player_shares["Player 1"] == {}
        # Bank financed the locomotive as company debt; the loco is acquired.
        assert state.company_debt["BY"] == 180
        assert 2 in state.company_trains["BY"]  # tier 2 = "3"-Lok
        # The director certificate ends up in the bank pool (rule 5.5.4.13).
        assert state.pool_shares["BY"] >= 20
        # Successor = the only remaining holder.
        assert state.company_directors["BY"] == "Player 2"

    def test_director_private_cash_covers_without_bankruptcy(self) -> None:
        state = _or(
            ORPhase.BUY_TRAIN,
            company_directors={"BY": "Player 1"},
            company_cash={"BY": 50},
            cash_per_player={"Player 1": 1_000, "Player 2": 0, "Player 3": 0},
            player_shares={"Player 1": {"BY": 100}, "Player 2": {}, "Player 3": {}},
        )
        state = BuyMandatoryTrain(player_id="Player 1", company_id="BY", train="3").apply(
            state
        )
        assert "Player 1" not in state.bankrupt_players
        assert state.company_cash["BY"] == 0  # AG keeps no Mark (rule 5.5.4.12)
        assert state.cash_per_player["Player 1"] == 1_000 - 130
        assert "BY" not in state.company_debt or state.company_debt["BY"] == 0

    def test_indebted_company_must_save_until_repaid(self) -> None:
        state = _or(
            ORPhase.DIVIDEND_DECISION,
            company_debt={"BY": 100},
            company_cash={"BY": 0},
            share_prices={"BY": 100},
        )
        # Saving is forced: a dividend is rejected (rule 5.5.4.13).
        assert isinstance(
            DeclareDividend(player_id="Player 1", company_id="BY", amount=50).validate(state),
            Err,
        )
        # Withholding repays the debt first, the rest reaches the treasury.
        state = WithholdDividend(player_id="Player 1", company_id="BY", amount=120).apply(
            state
        )
        assert state.company_debt["BY"] == 0
        assert state.company_cash["BY"] == 20


# ===========================================================================
# 7. Successor determination (rule 5.5.4.13)
# ===========================================================================


class TestSuccessorDirector:
    def test_tie_resolved_clockwise_from_start_player(self) -> None:
        base = GameState.initial(4)
        state = dataclasses.replace(
            base,
            start_player_index=0,  # wooden loco at Player 1
            player_shares={
                "Player 1": {},
                "Player 2": {"X": 30},
                "Player 3": {"X": 30},
                "Player 4": {},
            },
        )
        # Player 1 is leaving; Player 2 and 3 tie → first clockwise from seat 0.
        assert _successor_director(state, "X", leaving="Player 1") == "Player 2"

    def test_nobody_holds_falls_to_start_player(self) -> None:
        base = GameState.initial(3)
        state = dataclasses.replace(base, start_player_index=2)
        assert _successor_director(state, "X", leaving="Player 1") == "Player 3"


# ===========================================================================
# 8. Phase 3 forces conversion of all Vorpreußische + BS + HA (3.1.3.5, 5.5.4.14)
# ===========================================================================


class TestPhase3ForcedConversion:
    def test_first_five_lok_converts_everything(self) -> None:
        state = _or(
            ORPhase.BUY_TRAIN,
            colored_phase=2,
            company_cash={"BY": 10_000},
            player_shares={
                "Player 1": {"BM": 100, "HA": 10},
                "Player 2": {"BS": 50},
                "Player 3": {},
            },
        )
        state = BuyTrainFromBank(player_id="Player 1", company_id="BY", train="5").apply(
            state
        )
        assert state.colored_phase == 3
        for cid in ("BM", "HA", "BS"):
            assert state.company_status[cid] == "converted"
        assert state.player_shares["Player 1"]["PR"] == 110
        assert state.player_shares["Player 2"]["PR"] == 50
