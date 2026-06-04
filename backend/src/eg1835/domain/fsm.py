"""Explicit state machines for the 1835 action layer (Phase 4).

All transitions are encoded in lookup tables -- zero if-cascades over
state.phase, as required by the Phase 4 agent prompt.

Game loop (rule 1.1):
    START_PACKET_AR → OR×N → AR → OR×N → AR → …

OR sub-phases per company (rule 5.4):
    BUILD → STATION → RUN → DIVIDEND_DECISION → BUY_TRAIN → DONE
"""
from __future__ import annotations

from enum import StrEnum


class GameLoopPhase(StrEnum):
    """Top-level game loop phase."""

    START_PACKET_AR = "start_packet_ar"  # initial auction round
    AR = "ar"  # Aktienrunde  (stock round)
    OR = "or"  # Betriebsrunde (operating round)


class ORPhase(StrEnum):
    """Sub-phases of a single company's operating-round turn (rule 5.4)."""

    BUILD = "build"
    STATION = "station"
    RUN = "run"
    DIVIDEND_DECISION = "dividend_decision"
    BUY_TRAIN = "buy_train"
    DONE = "done"


# ---------------------------------------------------------------------------
# Explicit OR transition table (rule 5.4) -- the single source of truth.
# ---------------------------------------------------------------------------

_OR_NEXT: dict[ORPhase, ORPhase] = {
    ORPhase.BUILD: ORPhase.STATION,
    ORPhase.STATION: ORPhase.RUN,
    ORPhase.RUN: ORPhase.DIVIDEND_DECISION,
    ORPhase.DIVIDEND_DECISION: ORPhase.BUY_TRAIN,
    ORPhase.BUY_TRAIN: ORPhase.DONE,
    ORPhase.DONE: ORPhase.DONE,
}


def advance_or_phase(current: ORPhase) -> ORPhase:
    """Return the next OR sub-phase according to the transition table."""
    return _OR_NEXT[current]


# ---------------------------------------------------------------------------
# Phase-change logic on locomotive purchases (rule 5.3)
# ---------------------------------------------------------------------------

# When the first locomotive of ``purchasing_tier`` is bought, the game phase
# advances to ``purchasing_tier`` and all trains of ``_SCRAP_ON_PURCHASE[tier]``
# are forced off the board.
#
# Derived from locomotives.yml scrap_trigger values:
#   tier-4 (5-loco) has scrap_trigger 3 → "3-locomotives" are tier 2
#   tier-5 (6-loco) has scrap_trigger 4 → "4-locomotives" are tier 3
#   tier-6 (6+6)    has scrap_trigger 5 → "5-locomotives" are tier 4
_SCRAP_ON_PURCHASE: dict[int, int] = {4: 2, 5: 3, 6: 4}


def scrap_tier_on_purchase(purchasing_tier: int) -> int | None:
    """Tier to scrap when ``purchasing_tier`` is bought for the first time."""
    return _SCRAP_ON_PURCHASE.get(purchasing_tier)


# Locomotive purchase prices (from locomotives.yml).
TRAIN_PRICES: dict[int, int] = {1: 120, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
