"""Tile placement and upgrade system for 1835.

Implements Rules 5.5.1.1 - 5.5.1.23 from the 1835 rulebook.
"""
from enum import Enum
from typing import Any


class TileColor(str, Enum):
    YELLOW = "yellow"
    GREEN = "green"
    BROWN = "brown"


class CityType(str, Enum):
    NONE = "none"           # plain track, no city
    SMALL = "small"         # Kleinstadt, 10er, Regel 5.5.1.6
    NORMAL = "normal"       # Normal city, 20er, Regel 5.5.1.8
    LARGE_Y = "large_y"     # Großstadt Y-tile, 30er, Regel 5.5.1.9
    DOUBLE_XX = "double_xx" # Doppelstadt XX-tile, Regel 5.5.1.10
    BERLIN = "berlin"       # Regel 5.5.1.11
    HAMBURG = "hamburg"     # Regel 5.5.1.11


class TileUpgradeError(Exception):
    """Raised when a tile upgrade violates the promotion table or placement rules."""


class TileSystem:
    """
    Manages tile placement and upgrade validation.

    All rule references point to the Hans-im-Glück 1835 rulebook
    (Ausgabe mit Überarbeitung Röllig/Schröpl/Misch).
    """

    def __init__(self, promotions_data: dict[str, Any]) -> None:
        self._yellow_to_green: dict[int, frozenset[int]] = {}
        self._green_to_brown: dict[int, frozenset[int]] = {}
        self._not_upgradeable: frozenset[int] = frozenset()
        self._city_types: dict[int, CityType] = {}
        self._mannheim_prepared: bool = False
        self._load(promotions_data)

    def _load(self, data: dict[str, Any]) -> None:
        promotions = data.get("promotions", {})

        for rule in promotions.get("yellow_to_green", []):
            self._yellow_to_green[rule["from"]] = frozenset(rule["to"])

        for rule in promotions.get("green_to_brown", []):
            self._green_to_brown[rule["from"]] = frozenset(rule["to"])

        self._not_upgradeable = frozenset(promotions.get("not_upgradeable", []))

        for entry in data.get("city_types", []):
            self._city_types[entry["tile_id"]] = CityType(entry["type"])

        self._mannheim_prepared = bool(data.get("mannheim_ludwigshafen_prepared", False))

    # --- Promotion table (Regel 5.5.1.17) ---

    def get_valid_upgrades(self, from_tile_id: int, from_color: TileColor) -> frozenset[int]:
        """Return all valid upgrade targets per promotion table."""
        if from_tile_id in self._not_upgradeable or from_color == TileColor.BROWN:
            return frozenset()
        if from_color == TileColor.YELLOW:
            return self._yellow_to_green.get(from_tile_id, frozenset())
        return self._green_to_brown.get(from_tile_id, frozenset())

    def can_upgrade(self, from_tile_id: int, to_tile_id: int, from_color: TileColor) -> bool:
        """Check if tile upgrade is allowed by promotion table (Regel 5.5.1.14, 5.5.1.17)."""
        return to_tile_id in self.get_valid_upgrades(from_tile_id, from_color)

    def validate_upgrade(
        self, from_tile_id: int, to_tile_id: int, from_color: TileColor
    ) -> None:
        """Validate upgrade, raising TileUpgradeError if not allowed."""
        if from_color == TileColor.BROWN:
            raise TileUpgradeError(
                f"Brown tiles cannot be upgraded (Regel 5.5.1.14). Tile {from_tile_id} is brown."
            )
        if from_tile_id in self._not_upgradeable:
            raise TileUpgradeError(
                f"Tile {from_tile_id} is not in the promotion table (Regel 5.5.1.17)."
            )
        valid = self.get_valid_upgrades(from_tile_id, from_color)
        if to_tile_id not in valid:
            raise TileUpgradeError(
                f"Tile {from_tile_id} → {to_tile_id} not allowed. "
                f"Valid targets: {sorted(valid)} (Regel 5.5.1.17)."
            )

    # --- City type preservation (Regel 5.5.1.16) ---

    def city_type_preserved(self, from_tile_id: int, to_tile_id: int) -> bool:
        """Check city type is preserved: ohne↔ohne, klein↔klein, normal↔normal, Y↔Y, XX↔XX."""
        from_type = self._city_types.get(from_tile_id)
        to_type = self._city_types.get(to_tile_id)
        if from_type is None or to_type is None:
            return True  # permissive for tiles not in the table
        return from_type == to_type

    def validate_city_type_preserved(self, from_tile_id: int, to_tile_id: int) -> None:
        """Validate city type preservation, raising TileUpgradeError if violated."""
        if not self.city_type_preserved(from_tile_id, to_tile_id):
            from_type = self._city_types.get(from_tile_id)
            to_type = self._city_types.get(to_tile_id)
            raise TileUpgradeError(
                f"City type not preserved: tile {from_tile_id} ({from_type}) "
                f"→ {to_tile_id} ({to_type}) (Regel 5.5.1.16)."
            )

    # --- Phase-based color rules (Regel 5.5.1.1) ---

    def is_color_allowed_in_phase(self, tile_color: TileColor, game_phase: int) -> bool:
        """Yellow always; green from phase 2; brown from phase 3."""
        if tile_color == TileColor.YELLOW:
            return True
        if tile_color == TileColor.GREEN:
            return game_phase >= 2
        return game_phase >= 3  # BROWN

    # --- Build limits (Regel 5.5.1.2) ---

    def validate_tile_build_limit(
        self,
        tiles_placed: int,
        is_vorpreussische: bool,
        game_phase: int,
    ) -> bool:
        """Vorpreußische: max 1. AGs phase 1: max 2 yellow. AGs phase 2+: max 1."""
        if is_vorpreussische:
            return tiles_placed <= 1
        if game_phase == 1:
            return tiles_placed <= 2
        return tiles_placed <= 1

    # --- Mannheim/Ludwigshafen (Regel 5.5.2.10) ---

    def is_mannheim_ludwigshafen_prepared(self) -> bool:
        """Baden home station choice deferred until hex is built (Phase 7 uses this)."""
        return self._mannheim_prepared
