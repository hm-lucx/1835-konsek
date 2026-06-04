"""Tests for Phase 2: Tile placement and upgrade rules."""
import pytest

from eg1835.domain.loader import GameDataLoader
from eg1835.domain.tile_system import (
    TileColor,
    TileSystem,
    TileUpgradeError,
)


@pytest.fixture
def tile_system() -> TileSystem:
    """TileSystem loaded from promotions.yml."""
    return GameDataLoader().load_tile_system()


# ---------------------------------------------------------------------------
# Regel 5.5.1.1 – Tile color availability by game phase
# ---------------------------------------------------------------------------

class TestTileColorPhase:
    def test_yellow_allowed_phase_1(self, tile_system: TileSystem) -> None:
        assert tile_system.is_color_allowed_in_phase(TileColor.YELLOW, 1)

    def test_yellow_allowed_phase_3(self, tile_system: TileSystem) -> None:
        assert tile_system.is_color_allowed_in_phase(TileColor.YELLOW, 3)

    def test_green_not_allowed_phase_1(self, tile_system: TileSystem) -> None:
        assert not tile_system.is_color_allowed_in_phase(TileColor.GREEN, 1)

    def test_green_allowed_phase_2(self, tile_system: TileSystem) -> None:
        assert tile_system.is_color_allowed_in_phase(TileColor.GREEN, 2)

    def test_brown_not_allowed_phase_1(self, tile_system: TileSystem) -> None:
        assert not tile_system.is_color_allowed_in_phase(TileColor.BROWN, 1)

    def test_brown_not_allowed_phase_2(self, tile_system: TileSystem) -> None:
        assert not tile_system.is_color_allowed_in_phase(TileColor.BROWN, 2)

    def test_brown_allowed_phase_3(self, tile_system: TileSystem) -> None:
        assert tile_system.is_color_allowed_in_phase(TileColor.BROWN, 3)


# ---------------------------------------------------------------------------
# Regel 5.5.1.2 – Tile build limits per company per OR
# ---------------------------------------------------------------------------

class TestTileBuildLimits:
    def test_vorpreussische_max_1(self, tile_system: TileSystem) -> None:
        assert tile_system.validate_tile_build_limit(1, True, 1)

    def test_vorpreussische_cannot_place_2(self, tile_system: TileSystem) -> None:
        assert not tile_system.validate_tile_build_limit(2, True, 1)

    def test_ag_phase1_can_place_2_yellow(self, tile_system: TileSystem) -> None:
        assert tile_system.validate_tile_build_limit(2, False, 1)

    def test_ag_phase1_cannot_place_3(self, tile_system: TileSystem) -> None:
        assert not tile_system.validate_tile_build_limit(3, False, 1)

    def test_ag_phase2_max_1(self, tile_system: TileSystem) -> None:
        assert tile_system.validate_tile_build_limit(1, False, 2)

    def test_ag_phase2_cannot_place_2(self, tile_system: TileSystem) -> None:
        assert not tile_system.validate_tile_build_limit(2, False, 2)

    def test_ag_phase3_max_1(self, tile_system: TileSystem) -> None:
        assert tile_system.validate_tile_build_limit(1, False, 3)


# ---------------------------------------------------------------------------
# Promotion table – Yellow → Green (Regel 5.5.1.14, 5.5.1.17)
# One positive + one negative test per promotion table entry
# ---------------------------------------------------------------------------

class TestYellowToGreenPromotions:
    # Tile 1 → 88
    def test_tile_1_to_88_allowed(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(1, 88, TileColor.YELLOW)

    def test_tile_1_to_87_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(1, 87, TileColor.YELLOW)

    # Tile 2 → 87
    def test_tile_2_to_87_allowed(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(2, 87, TileColor.YELLOW)

    def test_tile_2_to_88_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(2, 88, TileColor.YELLOW)

    # Tile 3 → 87, 88, 204
    def test_tile_3_to_87(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(3, 87, TileColor.YELLOW)

    def test_tile_3_to_88(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(3, 88, TileColor.YELLOW)

    def test_tile_3_to_204(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(3, 204, TileColor.YELLOW)

    def test_tile_3_to_13_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(3, 13, TileColor.YELLOW)

    # Tile 4 → 87, 88, 204
    def test_tile_4_to_87(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(4, 87, TileColor.YELLOW)

    def test_tile_4_to_88(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(4, 88, TileColor.YELLOW)

    def test_tile_4_to_204(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(4, 204, TileColor.YELLOW)

    def test_tile_4_to_12_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(4, 12, TileColor.YELLOW)

    # Tile 5 → 12, 14, 15, 205, 206
    def test_tile_5_to_12(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(5, 12, TileColor.YELLOW)

    def test_tile_5_to_14(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(5, 14, TileColor.YELLOW)

    def test_tile_5_to_15(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(5, 15, TileColor.YELLOW)

    def test_tile_5_to_205(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(5, 205, TileColor.YELLOW)

    def test_tile_5_to_206(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(5, 206, TileColor.YELLOW)

    def test_tile_5_to_88_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(5, 88, TileColor.YELLOW)

    # Tile 6 → 12, 13, 14, 15, 205
    def test_tile_6_to_12(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(6, 12, TileColor.YELLOW)

    def test_tile_6_to_13(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(6, 13, TileColor.YELLOW)

    def test_tile_6_to_14(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(6, 14, TileColor.YELLOW)

    def test_tile_6_to_15(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(6, 15, TileColor.YELLOW)

    def test_tile_6_to_205(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(6, 205, TileColor.YELLOW)

    def test_tile_6_to_206_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(6, 206, TileColor.YELLOW)

    # Tile 7 → 18, 26, 27, 28, 29
    def test_tile_7_to_18(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(7, 18, TileColor.YELLOW)

    def test_tile_7_to_26(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(7, 26, TileColor.YELLOW)

    def test_tile_7_to_27(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(7, 27, TileColor.YELLOW)

    def test_tile_7_to_28(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(7, 28, TileColor.YELLOW)

    def test_tile_7_to_29(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(7, 29, TileColor.YELLOW)

    def test_tile_7_to_43_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(7, 43, TileColor.YELLOW)

    # Tile 8 → 16, 19, 23, 24, 25, 28, 29
    def test_tile_8_to_16(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 16, TileColor.YELLOW)

    def test_tile_8_to_19(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 19, TileColor.YELLOW)

    def test_tile_8_to_23(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 23, TileColor.YELLOW)

    def test_tile_8_to_24(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 24, TileColor.YELLOW)

    def test_tile_8_to_25(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 25, TileColor.YELLOW)

    def test_tile_8_to_28(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 28, TileColor.YELLOW)

    def test_tile_8_to_29(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(8, 29, TileColor.YELLOW)

    def test_tile_8_to_18_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(8, 18, TileColor.YELLOW)

    # Tile 9 → 18, 19, 20, 23, 24, 26, 27
    def test_tile_9_to_18(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 18, TileColor.YELLOW)

    def test_tile_9_to_19(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 19, TileColor.YELLOW)

    def test_tile_9_to_20(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 20, TileColor.YELLOW)

    def test_tile_9_to_23(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 23, TileColor.YELLOW)

    def test_tile_9_to_24(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 24, TileColor.YELLOW)

    def test_tile_9_to_26(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 26, TileColor.YELLOW)

    def test_tile_9_to_27(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(9, 27, TileColor.YELLOW)

    def test_tile_9_to_88_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(9, 88, TileColor.YELLOW)


# ---------------------------------------------------------------------------
# Promotion table – Green → Brown (Regel 5.5.1.14, 5.5.1.17)
# ---------------------------------------------------------------------------

class TestGreenToBrownPromotions:
    # Tile 16 → 43, 70
    def test_tile_16_to_43(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(16, 43, TileColor.GREEN)

    def test_tile_16_to_70(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(16, 70, TileColor.GREEN)

    def test_tile_16_to_41_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(16, 41, TileColor.GREEN)

    # Tile 23 → 41, 43, 45, 47
    def test_tile_23_to_41(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(23, 41, TileColor.GREEN)

    def test_tile_23_to_43(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(23, 43, TileColor.GREEN)

    def test_tile_23_to_45(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(23, 45, TileColor.GREEN)

    def test_tile_23_to_47(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(23, 47, TileColor.GREEN)

    def test_tile_23_to_70_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(23, 70, TileColor.GREEN)

    # Tile 207 → 216
    def test_tile_207_to_216(self, tile_system: TileSystem) -> None:
        assert tile_system.can_upgrade(207, 216, TileColor.GREEN)

    def test_tile_207_to_43_not_allowed(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(207, 43, TileColor.GREEN)


# ---------------------------------------------------------------------------
# Not-upgradeable tiles (Regel 5.5.1.17)
# ---------------------------------------------------------------------------

class TestNotUpgradeableTiles:
    def test_tile_14_not_upgradeable(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(14, 100, TileColor.GREEN)

    def test_tile_15_not_upgradeable(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(15, 100, TileColor.GREEN)

    def test_tile_87_not_upgradeable(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(87, 100, TileColor.GREEN)

    def test_tile_88_not_upgradeable(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(88, 100, TileColor.GREEN)

    def test_validate_raises_for_not_upgradeable(self, tile_system: TileSystem) -> None:
        with pytest.raises(TileUpgradeError, match="not in the promotion table"):
            tile_system.validate_upgrade(87, 100, TileColor.GREEN)

    def test_brown_never_upgradeable(self, tile_system: TileSystem) -> None:
        assert not tile_system.can_upgrade(41, 100, TileColor.BROWN)

    def test_validate_raises_for_brown(self, tile_system: TileSystem) -> None:
        with pytest.raises(TileUpgradeError, match="Brown tiles cannot be upgraded"):
            tile_system.validate_upgrade(41, 100, TileColor.BROWN)

    def test_yellow_cannot_skip_to_brown(self, tile_system: TileSystem) -> None:
        # Yellow tile 8 cannot jump directly to brown tile 41
        assert not tile_system.can_upgrade(8, 41, TileColor.YELLOW)

    def test_validate_raises_for_invalid_upgrade(self, tile_system: TileSystem) -> None:
        with pytest.raises(TileUpgradeError):
            tile_system.validate_upgrade(1, 87, TileColor.YELLOW)


# ---------------------------------------------------------------------------
# Regel 5.5.1.16 – Stadt-Typ-Erhalt (City type preservation)
# ---------------------------------------------------------------------------

class TestCityTypePreservation:
    def test_none_to_none_ok(self, tile_system: TileSystem) -> None:
        # Tile 1 (none) → Tile 88 (none)
        assert tile_system.city_type_preserved(1, 88)

    def test_small_to_small_ok(self, tile_system: TileSystem) -> None:
        # Tile 8 (small) → Tile 23 (small)
        assert tile_system.city_type_preserved(8, 23)

    def test_normal_to_normal_ok(self, tile_system: TileSystem) -> None:
        # Tile 207 (normal) → Tile 216 (normal)
        assert tile_system.city_type_preserved(207, 216)

    def test_none_to_small_not_ok(self, tile_system: TileSystem) -> None:
        # Tile 1 (none) → Tile 12 (small) – city type change forbidden
        assert not tile_system.city_type_preserved(1, 12)

    def test_small_to_none_not_ok(self, tile_system: TileSystem) -> None:
        # Tile 9 (small) → Tile 18 (none) – city type change forbidden
        assert not tile_system.city_type_preserved(9, 18)

    def test_validate_raises_on_type_change(self, tile_system: TileSystem) -> None:
        with pytest.raises(TileUpgradeError, match="City type not preserved"):
            tile_system.validate_city_type_preserved(1, 12)


# ---------------------------------------------------------------------------
# Regel 5.5.2.10 – Mannheim/Ludwigshafen preparation
# ---------------------------------------------------------------------------

class TestMannheimLudwigshafenPreparation:
    def test_mannheim_is_prepared(self, tile_system: TileSystem) -> None:
        """Map-side preparation for Baden home station deferral must be active."""
        assert tile_system.is_mannheim_ludwigshafen_prepared()


# ---------------------------------------------------------------------------
# Snapshot test: fixed tile sequence → expected board state
# ---------------------------------------------------------------------------

class TestBoardSnapshot:
    @pytest.fixture
    def loader(self) -> GameDataLoader:
        return GameDataLoader()

    def test_snapshot_key_cities(self, loader: GameDataLoader) -> None:
        """Board positions match known coordinates from the 1835 map."""
        board = loader.load_board()
        snapshot = {
            (3, 0): "Hamburg",
            (11, 0): "Berlin",
            (9, 8): "München",
            (11, 3): "Leipzig",
            (7, 4): "Frankfurt am Main",
            (4, 6): "Mannheim",
        }
        for (q, r), expected in snapshot.items():
            pos = board.get_position(q, r)
            assert pos is not None, f"No city at ({q},{r})"
            assert pos.location_name == expected, (
                f"Expected {expected} at ({q},{r}), got {pos.location_name}"
            )

    def test_snapshot_total_positions(self, loader: GameDataLoader) -> None:
        board = loader.load_board()
        assert len(board.positions) == 42
