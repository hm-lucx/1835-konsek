"""Share price track and step functions (rule 2.6.3)."""
from __future__ import annotations

# Ascending list of valid share price steps on the Aktienkurstafel.
SHARE_PRICE_TRACK: tuple[int, ...] = (
    50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120,
    135, 150, 165, 180, 200, 220, 245, 270, 300, 330, 365, 400,
)

_IDX: dict[int, int] = {p: i for i, p in enumerate(SHARE_PRICE_TRACK)}


def step_down(price: int) -> int:
    """One step down the price track (rule 2.6.3.3). Clamps at minimum."""
    idx = _IDX.get(price, 0)
    return SHARE_PRICE_TRACK[max(0, idx - 1)]


def step_up(price: int) -> int:
    """One step up the price track (rule 2.6.3.4). Clamps at maximum."""
    idx = _IDX.get(price, len(SHARE_PRICE_TRACK) - 1)
    return SHARE_PRICE_TRACK[min(len(SHARE_PRICE_TRACK) - 1, idx + 1)]
