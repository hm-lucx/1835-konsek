"""Revenue distribution for 1835 (Phase 3), rule 5.5.3.11.

The route value itself is produced by :mod:`eg1835.domain.routing`. This module
turns a company's total run revenue into per-holder payouts:

* 5.5.3.11.2  The maximum must be run -- enforced by the route finder, which
              never returns a sub-optimal route set.
* 5.5.3.11.5  An Aktiengesellschaft pays *all* of the revenue out or retains
              *all* of it -- there is no partial split.
* 5.5.3.11.6  A shareholder's slice is rounded **up**.
* 5.5.3.11.7  The pool's slice on 5% Preußen shares is rounded **down**.
              The opposing rounding directions are the deliberate asymmetry of
              the rule.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum


class PayoutMode(StrEnum):
    """All-or-nothing dividend decision for an AG (rule 5.5.3.11.5)."""

    FULL_PAYOUT = "full_payout"
    FULL_RETAIN = "full_retain"


@dataclass(frozen=True)
class ShareHolding:
    """A block of shares scoring a dividend.

    ``is_pool`` marks shares held by the bank pool, whose slice is rounded down
    (rule 5.5.3.11.7). Everyone else rounds up (rule 5.5.3.11.6).
    """

    holder: str
    percent: int
    is_pool: bool = False


@dataclass
class PayoutResult:
    mode: PayoutMode
    to_shareholders: dict[str, int] = field(default_factory=dict)
    to_treasury: int = 0


def shareholder_payout(revenue: int, share_percent: int) -> int:
    """Dividend on a shareholder's stake, rounded up (rule 5.5.3.11.6)."""
    return math.ceil(revenue * share_percent / 100)


def pool_payout(revenue: int, share_percent: int) -> int:
    """Dividend on pool shares, rounded down (rule 5.5.3.11.7)."""
    return math.floor(revenue * share_percent / 100)


def distribute(
    revenue: int, mode: PayoutMode, holdings: list[ShareHolding]
) -> PayoutResult:
    """Split ``revenue`` among ``holdings`` according to the AG payout rules.

    With :data:`PayoutMode.FULL_RETAIN` the whole revenue goes to the company
    treasury (5.5.3.11.5). With :data:`PayoutMode.FULL_PAYOUT` each holding
    receives its rounded slice: up for shareholders, down for the pool.
    """
    if revenue < 0:
        raise ValueError("Revenue must not be negative")

    if mode == PayoutMode.FULL_RETAIN:
        return PayoutResult(mode=mode, to_shareholders={}, to_treasury=revenue)

    payouts: dict[str, int] = {}
    for holding in holdings:
        if holding.is_pool:
            payouts[holding.holder] = pool_payout(revenue, holding.percent)
        else:
            payouts[holding.holder] = shareholder_payout(revenue, holding.percent)
    return PayoutResult(mode=mode, to_shareholders=payouts, to_treasury=0)
