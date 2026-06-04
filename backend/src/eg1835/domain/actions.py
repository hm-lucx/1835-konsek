"""Action framework for 1835 Konsek (Phase 4).

Every state mutation goes through an Action: validate first, then apply.
Actions are immutable frozen dataclasses; GameState is never mutated in place.

Action Protocol
---------------
    player_id : str
    validate(state) -> Ok[None] | Err[RuleViolation]
    apply(state)    -> GameState          # only call after validate succeeds

Stock-Round (AR)
    BuyStartItem · BuyShareFromBank · BuyShareFromPool
    Nationalize · SellShares · Pass

OR – Build phase (rule 5.4 BUILD)
    LayTile · UpgradeTile
    UseNFAbility · UseOBAbility · UsePFBuildAbility

OR – Station phase (rule 5.4 STATION)
    PlaceStation · UsePFStationAbility

OR – Run phase (rule 5.4 RUN / DIVIDEND_DECISION)
    RunTrains · DeclareDividend · WithholdDividend

OR – Train-purchase phase (rule 5.4 BUY_TRAIN)
    BuyTrainFromBank · BuyTrainFromPool · BuyTrainFromCompany

Special
    OpenPreussen · ConvertToPreussenShare · ChooseBadenHomeStation
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from .fsm import (
    TRAIN_PRICES,
    GameLoopPhase,
    ORPhase,
    advance_or_phase,
    scrap_tier_on_purchase,
)
from .game_state import GameState
from .result import Err, Ok

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

PlayerId = str


@dataclass(frozen=True)
class RuleViolation:
    """Carries the rule reference and a human-readable explanation."""

    rule: str
    message: str


ValidateResult = Ok[None] | Err[RuleViolation]


# ---------------------------------------------------------------------------
# Protocol – structural type that every action satisfies
# ---------------------------------------------------------------------------


class Action(Protocol):
    """Structural interface shared by all action classes."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult: ...

    def apply(self, state: GameState) -> GameState: ...


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _require_loop_phase(
    state: GameState, *phases: GameLoopPhase, rule: str = "1.1"
) -> ValidateResult:
    if state.game_loop_phase not in phases:
        return Err(
            RuleViolation(
                rule=rule,
                message=f"Expected game loop in {phases}, got {state.game_loop_phase}",
            )
        )
    return Ok(None)


def _require_or_phase(
    state: GameState, *phases: ORPhase, rule: str = "5.4"
) -> ValidateResult:
    if state.or_phase not in phases:
        return Err(
            RuleViolation(
                rule=rule,
                message=f"Expected OR phase in {phases}, got {state.or_phase}",
            )
        )
    return Ok(None)


def _ar_phases() -> tuple[GameLoopPhase, ...]:
    return (GameLoopPhase.START_PACKET_AR, GameLoopPhase.AR)


def _advance_ar(state: GameState, *, reset_passes: bool) -> GameState:
    """Advance to the next AR player; optionally reset pass counter."""
    new_passes = 0 if reset_passes else state.ar_consecutive_passes + 1
    next_idx = (state.current_player_index + 1) % len(state.players)
    # AR ends when every player has consecutively not bought (rule 2.3).
    new_loop = state.game_loop_phase
    if new_passes >= len(state.players):
        new_loop = GameLoopPhase.OR
        new_passes = 0
    return dataclasses.replace(
        state,
        current_player_index=next_idx,
        ar_consecutive_passes=new_passes,
        game_loop_phase=new_loop,
    )


def _apply_phase_change(state: GameState, purchasing_tier: int) -> GameState:
    """Advance game phase and scrap obsolete trains if a new tier was bought."""
    if purchasing_tier <= state.game_phase:
        return state
    scrap_tier = scrap_tier_on_purchase(purchasing_tier)
    new_company_trains: dict[str, list[int]] = {}
    for cid, trains in state.company_trains.items():
        if scrap_tier is not None:
            new_company_trains[cid] = [t for t in trains if t != scrap_tier]
        else:
            new_company_trains[cid] = list(trains)
    return dataclasses.replace(
        state,
        game_phase=purchasing_tier,
        company_trains=new_company_trains,
    )


# ===========================================================================
# Stock-Round (AR) actions
# ===========================================================================


@dataclass(frozen=True)
class BuyStartItem:
    """Buy a start-packet item in the opening AR (rule 2.1)."""

    player_id: PlayerId
    item_id: str

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, GameLoopPhase.START_PACKET_AR, rule="2.1")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class BuyShareFromBank:
    """Buy a share from the bank pool in an AR (rule 2.2)."""

    player_id: PlayerId
    company_id: str
    percent: int

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.2")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class BuyShareFromPool:
    """Buy a share from the market pool in an AR (rule 2.2)."""

    player_id: PlayerId
    company_id: str
    percent: int

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.2")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class Nationalize:
    """Nationalize a Vorpreußische company (rule 2.4)."""

    player_id: PlayerId
    company_id: str

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.4")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class SellShares:
    """Sell shares in an AR (rule 2.3).

    Selling does *not* break the consecutive-pass chain (rule 2.3):
    ar_consecutive_passes is incremented just like Pass, not reset.
    """

    player_id: PlayerId
    company_id: str
    percent: int

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.3")

    def apply(self, state: GameState) -> GameState:
        # Selling counts as a non-buy; the pass counter advances.
        return _advance_ar(state, reset_passes=False)


@dataclass(frozen=True)
class Pass:
    """Pass the current turn.

    In AR: increments consecutive-pass counter (may end the AR).
    In OR BUILD / STATION / BUY_TRAIN: advances to the next OR sub-phase.
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        in_ar = state.game_loop_phase in _ar_phases()
        in_or_passable = state.or_phase in (
            ORPhase.BUILD,
            ORPhase.STATION,
            ORPhase.BUY_TRAIN,
        )
        if not (in_ar or (state.game_loop_phase == GameLoopPhase.OR and in_or_passable)):
            return Err(
                RuleViolation(
                    rule="5.4",
                    message=f"Pass not allowed in {state.game_loop_phase}/{state.or_phase}",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        if state.game_loop_phase in _ar_phases():
            return _advance_ar(state, reset_passes=False)
        # OR: advance the sub-phase.
        assert state.or_phase is not None
        return dataclasses.replace(state, or_phase=advance_or_phase(state.or_phase))


# ===========================================================================
# OR – Build phase
# ===========================================================================


@dataclass(frozen=True)
class LayTile:
    """Lay a yellow tile in the build phase (rule 5.4 BUILD, 5.5.1)."""

    player_id: PlayerId
    tile_id: int
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD, rule="5.5.1")

    def apply(self, state: GameState) -> GameState:
        return state  # board mutation deferred to Phase 2/5 integration


@dataclass(frozen=True)
class UpgradeTile:
    """Upgrade an existing tile in the build phase (rule 5.5.1.14)."""

    player_id: PlayerId
    tile_id: int
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD, rule="5.5.1.14")

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UseNFAbility:
    """Use the Nord-Flügel private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UseOBAbility:
    """Use the Oldenburg-Bremen private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UsePFBuildAbility:
    """Use the Pfalzbahn private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


# ===========================================================================
# OR – Station phase
# ===========================================================================


@dataclass(frozen=True)
class PlaceStation:
    """Place a company station token (rule 5.4 STATION)."""

    player_id: PlayerId
    company_id: str
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION)

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))


@dataclass(frozen=True)
class UsePFStationAbility:
    """Use the Pfalzbahn private railway station ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION)

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))


# ===========================================================================
# OR – Run / Dividend-decision phase
# ===========================================================================


@dataclass(frozen=True)
class RunTrains:
    """Run the company's trains to collect revenue (rule 5.4 RUN, 5.5.3).

    Transitions RUN → DIVIDEND_DECISION upon application.
    """

    player_id: PlayerId
    company_id: str
    route_values: list[int]  # revenue per route

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.RUN, rule="5.5.3")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.RUN))


@dataclass(frozen=True)
class DeclareDividend:
    """Pay out the full revenue to shareholders (rule 5.5.3.11.5).

    Transitions DIVIDEND_DECISION → BUY_TRAIN upon application.
    """

    player_id: PlayerId
    company_id: str
    amount: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(
            state, or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION)
        )


@dataclass(frozen=True)
class WithholdDividend:
    """Retain all revenue in company treasury (rule 5.5.3.11.5).

    Transitions DIVIDEND_DECISION → BUY_TRAIN upon application.
    """

    player_id: PlayerId
    company_id: str

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(
            state, or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION)
        )


# ===========================================================================
# OR – Train-purchase phase
# ===========================================================================


@dataclass(frozen=True)
class BuyTrainFromBank:
    """Buy a locomotive from the bank (rule 5.4 BUY_TRAIN, 5.3).

    Triggers a game-phase advance when the first train of a new tier is
    purchased; scraps the obsolete tier as specified in rule 5.3.  Multiple
    purchases across different companies can each trigger a phase change.
    """

    player_id: PlayerId
    company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.3")
        if isinstance(result, Err):
            return result
        available = state.available_trains.get(self.tier, 0)
        if available <= 0:
            return Err(
                RuleViolation(
                    rule="5.3",
                    message=f"No tier-{self.tier} trains left in the bank",
                )
            )
        price = TRAIN_PRICES.get(self.tier, 0)
        company_balance = state.company_cash.get(self.company_id, 0)
        if company_balance < price:
            return Err(
                RuleViolation(
                    rule="5.3",
                    message=(
                        f"{self.company_id} cannot afford tier-{self.tier} train "
                        f"(needs {price}, has {company_balance})"
                    ),
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        price = TRAIN_PRICES[self.tier]
        # Update bank and company treasury.
        new_available = {**state.available_trains, self.tier: state.available_trains[self.tier] - 1}
        new_company_cash = {
            **state.company_cash,
            self.company_id: state.company_cash.get(self.company_id, 0) - price,
        }
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [self.tier],
        }
        new_state = dataclasses.replace(
            state,
            available_trains=new_available,
            company_cash=new_company_cash,
            company_trains=new_company_trains,
            bank_balance=state.bank_balance + price,
        )
        # Phase change: runs *after* train is placed, may scrap older trains.
        return _apply_phase_change(new_state, self.tier)


@dataclass(frozen=True)
class BuyTrainFromPool:
    """Buy a discarded locomotive from the market pool (rule 5.4 BUY_TRAIN)."""

    player_id: PlayerId
    company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUY_TRAIN)

    def apply(self, state: GameState) -> GameState:
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [self.tier],
        }
        new_state = dataclasses.replace(state, company_trains=new_company_trains)
        return _apply_phase_change(new_state, self.tier)


@dataclass(frozen=True)
class BuyTrainFromCompany:
    """Buy a locomotive directly from another company (rule 5.4 BUY_TRAIN)."""

    player_id: PlayerId
    company_id: str
    from_company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        if self.tier not in state.company_trains.get(self.from_company_id, []):
            return Err(
                RuleViolation(
                    rule="5.4",
                    message=f"{self.from_company_id} does not own a tier-{self.tier} train",
                )
            )
        return _require_or_phase(state, ORPhase.BUY_TRAIN)

    def apply(self, state: GameState) -> GameState:
        src_trains = list(state.company_trains.get(self.from_company_id, []))
        src_trains.remove(self.tier)
        dst_trains = state.company_trains.get(self.company_id, []) + [self.tier]
        new_company_trains = {
            **state.company_trains,
            self.from_company_id: src_trains,
            self.company_id: dst_trains,
        }
        return dataclasses.replace(state, company_trains=new_company_trains)


# ===========================================================================
# Special actions
# ===========================================================================


@dataclass(frozen=True)
class OpenPreussen:
    """Open Preußen as a fully nationalised company (special rule)."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.4")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class ConvertToPreussenShare:
    """Convert a Vorpreußische share to a 5% Preußen share (rule 2.4)."""

    player_id: PlayerId
    share_id: str

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.4")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class ChooseBadenHomeStation:
    """Choose the Baden home station (Mannheim or Ludwigshafen, rule 5.5.2.10)."""

    player_id: PlayerId
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.5.2.10")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION, rule="5.5.2.10")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))
