"""Private-railway special abilities (rule 3.1.3).

Each of the four buildable abilities is its own frozen-dataclass action with a
``validate`` / ``apply`` pair, mirroring the main action layer.  They operate on
``GameState`` and depend only on ``action_base`` (shared phase guards), so the
main ``actions`` module can import and re-export them without a cycle.

Modelling notes
---------------
* Board geometry is deferred (as in Phases 3/6): "free tile" / "free station"
  abilities toggle the relevant ``GameState`` flags (``closed_privates``,
  ``built_fields``) and take field ids from the caller rather than computing
  hex adjacency.
* An ability is only usable by the private's owner while that owner is acting
  as the director of the company currently operating (rule 3.1.3: "wenn er als
  Direktor einer AG in einer OR agiert").

Close triggers (rule 3.1.3)
---------------------------
* NF – closes on use (free station in the Nürnberg-Fürth field).
* OB – closes once *both* its fields are built, by anyone (even a foreign AG).
* PF build – never closes.
* PF station – closes on use.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from ...action_base import (
    PlayerId,
    RuleViolation,
    ValidateResult,
    _require_loop_phase,
    _require_or_phase,
)
from ...fsm import GameLoopPhase, ORPhase
from ...game_state import GameState
from ...result import Err, Ok

# Named special fields (board geometry deferred -- callers pass these ids).
NF_FIELD = "NF"  # Nürnberg-Fürth
OB_FIELDS = ("OB-A", "OB-B")  # the two fields south-east of NF (rule 3.1.3.2)
ML_FIELD = "M-L"  # Mannheim/Ludwigshafen doppelstadt (rules 3.1.3.3, 5.5.2.10)

BADEN = "BA"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _acting_director(state: GameState, player_id: PlayerId) -> str | None:
    """The company *player_id* is currently operating as director, or None."""
    active = state.active_company_id
    if active is not None and state.company_directors.get(active) == player_id:
        return active
    return None


def _require_owns_open_private(
    state: GameState, player_id: PlayerId, private_id: str
) -> ValidateResult:
    """Owner-of-an-open-private guard shared by every private ability."""
    if private_id in state.closed_privates:
        return Err(RuleViolation("3.1.3", f"{private_id} is already closed"))
    if state.private_owners.get(private_id) != player_id:
        return Err(RuleViolation("3.1.3", f"{player_id} does not own {private_id}"))
    if _acting_director(state, player_id) is None:
        return Err(
            RuleViolation("3.1.3", f"{player_id} is not acting as a director this turn")
        )
    return Ok(None)


def register_built_field(state: GameState, field_id: str) -> GameState:
    """Record that ``field_id`` was built and close OB if both its fields are.

    Called by ``LayTile`` and by ``UseOBAbility`` so that a foreign build on the
    second OB field also closes the Ostbayern (rule 3.1.3.2).
    """
    new_built = state.built_fields | {field_id}
    new_state = state
    if field_id and new_built != state.built_fields:
        new_state = dataclasses.replace(state, built_fields=new_built)
    if "OB" not in new_state.closed_privates and all(f in new_built for f in OB_FIELDS):
        new_state = _close_private(new_state, "OB")
    return new_state


def _close_private(state: GameState, private_id: str) -> GameState:
    return dataclasses.replace(
        state, closed_privates=state.closed_privates | {private_id}
    )


# ---------------------------------------------------------------------------
# Nürnberg-Fürth (3.1.3.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UseNFAbility:
    """Free station marker in the Nürnberg-Fürth field; closes NF (rule 3.1.3.1).

    Placed without a connection requirement and in addition to the regular
    station, so it does not consume the one-station-per-turn allowance.
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="3.1.3.1")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.STATION, rule="3.1.3.1")
        if isinstance(result, Err):
            return result
        return _require_owns_open_private(state, self.player_id, "NF")

    def apply(self, state: GameState) -> GameState:
        # Free, additional marker -> stays in the STATION sub-phase; closes NF.
        return register_built_field(_close_private(state, "NF"), NF_FIELD)


# ---------------------------------------------------------------------------
# Ostbayern (3.1.3.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UseOBAbility:
    """Free tile in one of OB's two fields; closes OB once both are built.

    The ``field_id`` must be one of :data:`OB_FIELDS` and not already built.
    """

    player_id: PlayerId
    field_id: str

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="3.1.3.2")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUILD, rule="3.1.3.2")
        if isinstance(result, Err):
            return result
        result = _require_owns_open_private(state, self.player_id, "OB")
        if isinstance(result, Err):
            return result
        if self.field_id not in OB_FIELDS:
            return Err(RuleViolation("3.1.3.2", f"{self.field_id} is not an OB field"))
        if self.field_id in state.built_fields:
            return Err(RuleViolation("3.1.3.2", f"{self.field_id} is already built"))
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        # Free, additional tile -> stays in BUILD; OB closes when both fields built.
        return register_built_field(state, self.field_id)


# ---------------------------------------------------------------------------
# Pfalzbahn build ability (3.1.3.3 #1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsePFBuildAbility:
    """Free tile in Mannheim/Ludwigshafen, additional and connection-free.

    Does **not** close the Pfalzbahn (rule 3.1.3.3).  Forbidden once Baden is in
    operation but has not yet placed its home station, unless Baden itself is
    operating (rule 5.5.2.10: the field is reserved for Baden's home).
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="3.1.3.3")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUILD, rule="3.1.3.3")
        if isinstance(result, Err):
            return result
        result = _require_owns_open_private(state, self.player_id, "PF")
        if isinstance(result, Err):
            return result
        if _baden_field_reserved(state):
            return Err(
                RuleViolation(
                    "5.5.2.10",
                    "M/L is reserved until Baden has placed its home station",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        return register_built_field(state, ML_FIELD)  # PF stays open


# ---------------------------------------------------------------------------
# Pfalzbahn station ability (3.1.3.3 #2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsePFStationAbility:
    """Free station marker in M/L; closes PF (rule 3.1.3.3 #2).

    Requires Baden to be in operation and the M/L field to be built.  May not be
    used before Baden has placed its home station (would block Baden).
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="3.1.3.3")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.STATION, rule="3.1.3.3")
        if isinstance(result, Err):
            return result
        result = _require_owns_open_private(state, self.player_id, "PF")
        if isinstance(result, Err):
            return result
        if state.company_status.get(BADEN) != "launched":
            return Err(RuleViolation("3.1.3.3", "Baden is not yet in operation"))
        if ML_FIELD not in state.built_fields:
            return Err(RuleViolation("3.1.3.3", "M/L is not built yet"))
        if _baden_field_reserved(state):
            return Err(
                RuleViolation(
                    "5.5.2.10",
                    "Baden has not placed its home station yet – field is reserved",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        return _close_private(state, "PF")


def _baden_field_reserved(state: GameState) -> bool:
    """True if the M/L field is reserved for Baden's not-yet-placed home (5.5.2.10).

    The reservation applies once Baden is in operation and lifts only when Baden
    has chosen its home city; it never applies to Baden itself.
    """
    if state.active_company_id == BADEN:
        return False
    return state.company_status.get(BADEN) == "launched" and not state.baden_home_chosen
