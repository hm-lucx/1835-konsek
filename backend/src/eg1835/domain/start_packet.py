"""Start packet items and row-selection logic (rules 2.4, 2.5)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartPacketItem:
    """One purchasable item in the opening auction round."""

    id: str
    name: str
    cost: int
    bonus_shares: tuple[str, ...]  # Vorpreußische company_ids delivered with purchase


# Canonical item definitions.  "BS" is reused as both private-railway id and
# Vorpreußische company id; context (start_packet_rows vs player_shares) disambiguates.
START_PACKET_ITEMS: dict[str, StartPacketItem] = {
    "NF": StartPacketItem("NF", "Nord-Flügel",       100, ("AK",)),
    "LD": StartPacketItem("LD", "Leipzig-Dresdner",  100, ("BM",)),
    "BS": StartPacketItem("BS", "Berlin-Stettiner",  120, ("BS",)),
    "HA": StartPacketItem("HA", "Hamburg-Altonaer",  120, ("MD",)),
    "OB": StartPacketItem("OB", "Oldenburg-Bremen",  140, ("KM",)),
    "PF": StartPacketItem("PF", "Pfalzbahn",         140, ("BP",)),
}

# Row 0 is the "top" (cheapest) row, row 2 is the last.
INITIAL_START_PACKET_ROWS: tuple[tuple[str, ...], ...] = (
    ("NF", "LD"),
    ("BS", "HA"),
    ("OB", "PF"),
)

# Certificate limit per player count (rule 2.6.2.6).
BASE_CERT_LIMIT: dict[int, int] = {3: 20, 4: 16, 5: 13, 6: 11, 7: 10}


def buyable_item_ids(rows: tuple[tuple[str, ...], ...]) -> frozenset[str]:
    """IDs of items that may be purchased given current row state (rule 2.5).

    Normally only items in the topmost non-empty row are available.
    Special case: when exactly one item remains in the top row the first item
    of the next non-empty row is also unlocked.
    """
    non_empty = [r for r in rows if r]
    if not non_empty:
        return frozenset()
    top = non_empty[0]
    result: set[str] = set(top)
    if len(top) == 1 and len(non_empty) > 1:
        result.add(non_empty[1][0])
    return frozenset(result)


def remove_item(
    rows: tuple[tuple[str, ...], ...], item_id: str
) -> tuple[tuple[str, ...], ...]:
    """Return new rows tuple with *item_id* removed."""
    return tuple(tuple(x for x in row if x != item_id) for row in rows)
