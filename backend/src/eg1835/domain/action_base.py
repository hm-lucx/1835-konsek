"""Shared primitives for the action layer.

Extracted so that both ``actions.py`` and the per-company ability modules
(``companies.privates.abilities``) can depend on the same validation helpers
without importing each other (which would be circular).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .fsm import GameLoopPhase, ORPhase
from .game_state import GameState
from .result import Err, Ok

PlayerId = str


@dataclass(frozen=True)
class RuleViolation:
    """Carries the rule reference and a human-readable explanation."""

    rule: str
    message: str


ValidateResult = Ok[None] | Err[RuleViolation]


class Action(Protocol):
    """Structural interface shared by all (frozen-dataclass) action classes."""

    @property
    def player_id(self) -> PlayerId: ...  # read-only: actions are frozen

    def validate(self, state: GameState) -> ValidateResult: ...

    def apply(self, state: GameState) -> GameState: ...


# ---------------------------------------------------------------------------
# Phase-guard helpers
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
