"""Explicit state machines for the 1835 action layer (Phase 4 + Phase 6).

All transitions are encoded in lookup tables -- zero if-cascades over
state.phase, as required by the Phase 4 agent prompt.

Game loop (rule 1.1):
    START_PACKET_AR → OR×N → AR → OR×N → AR → …

OR sub-phases per company (rule 5.4):
    BUILD → STATION → RUN → DIVIDEND_DECISION → BUY_TRAIN → DONE
"""
from __future__ import annotations

from dataclasses import dataclass
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
# Locomotive roster (Phase 6) -- rule Promotionstabellen + 5.5.4.14
# ---------------------------------------------------------------------------
#
# 1835 has ten distinct locomotive cards.  Phase 4 modelled only the six
# "plain" ones as integer *tiers*; the four "+"-variants were left as a
# follow-up (this issue, #7).  We keep a string ``train id`` as the canonical
# identity and a stable integer-``tier`` mapping so that ``company_trains`` /
# ``available_trains`` (both int-keyed since Phase 4) keep working unchanged.


@dataclass(frozen=True)
class TrainSpec:
    """A locomotive card type (rule Promotionstabellen)."""

    train_id: str  # "2", "2+2", "3", … "6+6"
    price: int
    count: int  # number of cards in the game


# Ordered ascending in the sequence trains must be bought (rule 5.5.4):
# all plain locos of a size, then the "+"-variant, then the next size.
TRAIN_ROSTER: tuple[TrainSpec, ...] = (
    TrainSpec("2", 80, 9),
    TrainSpec("2+2", 120, 4),
    TrainSpec("3", 180, 4),
    TrainSpec("3+3", 270, 3),
    TrainSpec("4", 360, 3),
    TrainSpec("4+4", 440, 1),
    TrainSpec("5", 500, 2),
    TrainSpec("5+5", 600, 1),
    TrainSpec("6", 600, 2),
    TrainSpec("6+6", 720, 4),
)

TRAIN_SPECS: dict[str, TrainSpec] = {spec.train_id: spec for spec in TRAIN_ROSTER}

# Canonical train id ↔ integer tier.  The first six tiers are the legacy
# Phase-4 numbering (kept stable so Phase-4 tests pass unchanged); the four
# "+"-variants are appended as tiers 7–10.  Tier numbers are *identities*, not
# a purchase-order ranking (use TRAIN_ROSTER for ordering).
TRAIN_TIER: dict[str, int] = {
    "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "6+6": 6,  # legacy Phase-4 tiers
    "2+2": 7, "3+3": 8, "4+4": 9, "5+5": 10,           # Phase-6 additions
}
TIER_TRAIN: dict[int, str] = {tier: tid for tid, tier in TRAIN_TIER.items()}

# Legacy int-keyed price/scrap tables (kept for backward compatibility).
TRAIN_PRICES: dict[int, int] = {
    TRAIN_TIER[spec.train_id]: spec.price for spec in TRAIN_ROSTER
}


def train_id_to_tier(train_id: str) -> int | None:
    """Integer tier for a canonical train id, or None if unknown."""
    return TRAIN_TIER.get(train_id)


def tier_to_train_id(tier: int) -> str | None:
    """Canonical train id for an integer tier, or None if unknown."""
    return TIER_TRAIN.get(tier)


def train_reaches(train_id: str) -> list[int]:
    """Locomotive reach(es) for routing (rule 5.5.3.4).

    A "+"-variant is two engines, each with the base reach: "2+2" → [2, 2],
    "6+6" → [6, 6]; a plain train is a single engine: "3" → [3].
    """
    return [int(part) for part in train_id.split("+")]


def tier_reaches(tier: int) -> list[int]:
    """Reach(es) for an integer-tier locomotive (see :func:`train_reaches`)."""
    train_id = tier_to_train_id(tier)
    return train_reaches(train_id) if train_id is not None else []


# ---------------------------------------------------------------------------
# Phase-change logic on locomotive purchases (rules 5.2, 5.5.4.14)
# ---------------------------------------------------------------------------
#
# Two independent notions of "phase":
#   * coloured phase (1=gelb, 2=grün, 3=braun) -- drives tile colours and the
#     number of ORs between two ARs.  Advanced by the first 3-Lok / 5-Lok.
#   * ``game_state.game_phase`` -- legacy "highest locomotive tier purchased",
#     tracked for Phase-4 compatibility.  NOT the coloured phase.

# First purchase of this train id advances the coloured phase (rule 5.2).
_COLOURED_PHASE_TRIGGER: dict[str, int] = {"3": 2, "5": 3}

# Number of ORs between two ARs, per coloured phase (rule 5.2 table).
ORS_PER_COLOURED_PHASE: dict[int, int] = {1: 1, 2: 2, 3: 3}

# First purchase of <key> scraps every <value> locomotive on the board
# (rule 5.5.4.14):  4→2, 4+4→2+2, 6→3, 6+6→3+3.
_SCRAP_ON_FIRST_PURCHASE: dict[str, str] = {
    "4": "2", "4+4": "2+2", "6": "3", "6+6": "3+3",
}


def coloured_phase_trigger(train_id: str) -> int | None:
    """Coloured phase that the first purchase of ``train_id`` starts, if any."""
    return _COLOURED_PHASE_TRIGGER.get(train_id)


def ors_for_coloured_phase(phase: int) -> int:
    """Number of ORs between two ARs for the given coloured phase."""
    return ORS_PER_COLOURED_PHASE.get(phase, 1)


def scrap_train_on_first_purchase(train_id: str) -> str | None:
    """Train id scrapped when ``train_id`` is bought for the first time."""
    return _SCRAP_ON_FIRST_PURCHASE.get(train_id)


# --- Legacy int-tier helpers (Phase 4) -------------------------------------

_SCRAP_ON_PURCHASE: dict[int, int] = {3: 1, 5: 2}


def scrap_tier_on_purchase(purchasing_tier: int) -> int | None:
    """Tier to scrap when ``purchasing_tier`` is bought (legacy Phase-4 API)."""
    return _SCRAP_ON_PURCHASE.get(purchasing_tier)


# ---------------------------------------------------------------------------
# Locomotive limit per coloured phase (rule 5.5.4.7, Übersichtsbogen)
# ---------------------------------------------------------------------------
# A company that has reached its limit may buy no further locomotive -- even if
# the purchase would trigger a phase change that scraps one of its trains.
TRAIN_LIMIT_PER_COLOURED_PHASE: dict[int, int] = {1: 4, 2: 3, 3: 2}


def train_limit_for_phase(coloured_phase: int) -> int:
    """Maximum locomotives a company may hold in the given coloured phase."""
    return TRAIN_LIMIT_PER_COLOURED_PHASE.get(coloured_phase, 2)
