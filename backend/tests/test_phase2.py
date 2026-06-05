"""Tests for Phase 2: Hex-Map & Tile-System."""
import pytest

from eg1835.domain.loader import GameDataLoader
from eg1835.domain.models import GameBoard, HexCoordinate, HexPosition


class TestHexCoordinates:
    """Test hexagonal coordinate system."""

    def test_hex_coordinate_creation(self) -> None:
        """Test creating HexCoordinate."""
        coord = HexCoordinate(q=3, r=0)
        assert coord.q == 3
        assert coord.r == 0

    def test_hex_coordinate_equality(self) -> None:
        """Test HexCoordinate equality."""
        coord1 = HexCoordinate(q=3, r=0)
        coord2 = HexCoordinate(q=3, r=0)
        coord3 = HexCoordinate(q=3, r=1)
        assert coord1 == coord2
        assert coord1 != coord3

    def test_hex_coordinate_hashable(self) -> None:
        """Test that HexCoordinate is hashable."""
        coord1 = HexCoordinate(q=3, r=0)
        coord2 = HexCoordinate(q=3, r=0)
        coord3 = HexCoordinate(q=3, r=1)
        coord_set = {coord1, coord2, coord3}
        assert len(coord_set) == 2  # coord1 and coord2 are equal


class TestHexPositions:
    """Test hexagonal positions on the board."""

    def test_hex_position_creation(self) -> None:
        """Test creating HexPosition."""
        coord = HexCoordinate(q=3, r=0)
        pos = HexPosition(coordinate=coord, tile_id=1, location_name="Hamburg")
        assert pos.coordinate == coord
        assert pos.tile_id == 1
        assert pos.location_name == "Hamburg"


class TestGameBoardLoading:
    """Test that board loads correctly from YAML."""

    @pytest.fixture
    def loader(self) -> GameDataLoader:
        """Create a game data loader instance."""
        return GameDataLoader()

    def test_board_loads(self, loader: GameDataLoader) -> None:
        """Test that board loads successfully."""
        board = loader.load_board()
        assert isinstance(board, GameBoard)
        assert board.width == 22
        assert board.height == 8

    def test_board_has_positions(self, loader: GameDataLoader) -> None:
        """Test that board has hex positions."""
        board = loader.load_board()
        assert len(board.positions) > 0
        assert len(board.positions) == 131  # reconstructed 1835 map

    def test_board_position_retrieval(self, loader: GameDataLoader) -> None:
        """Test retrieving position from board."""
        board = loader.load_board()
        # Hamburg at (10, 1) on the reconstructed map.
        pos = board.get_position(10, 1)
        assert pos is not None
        assert pos.location_name == "Hamburg"
        assert pos.terrain == "city"

    def test_board_position_not_found(self, loader: GameDataLoader) -> None:
        """Test retrieving non-existent position."""
        board = loader.load_board()
        pos = board.get_position(999, 999)
        assert pos is None

    def test_board_tile_lookup(self, loader: GameDataLoader) -> None:
        """Test tile lookup by coordinate."""
        board = loader.load_board()
        tile = board.get_tile_at(10, 1)
        assert tile is not None
        assert tile.id == 0  # base map carries no rail tile yet

    def test_board_all_positions_have_coordinates(
        self, loader: GameDataLoader
    ) -> None:
        """Test that all positions have valid coordinates."""
        board = loader.load_board()
        for pos in board.positions.values():
            assert pos.coordinate is not None
            assert isinstance(pos.coordinate.q, int)
            assert isinstance(pos.coordinate.r, int)

    def test_board_all_positions_have_names(self, loader: GameDataLoader) -> None:
        """Cities and company homes carry a printed name (plain land does not)."""
        board = loader.load_board()
        named_terrains = {"city", "home", "citybrown"}
        for pos in board.positions.values():
            if pos.terrain in named_terrains:
                assert pos.location_name, f"unnamed {pos.terrain} at {pos.coordinate}"

    def test_board_position_keys_match_coordinates(
        self, loader: GameDataLoader
    ) -> None:
        """Test that position keys match their coordinates."""
        board = loader.load_board()
        for key, pos in board.positions.items():
            expected_key = f"{pos.coordinate.q},{pos.coordinate.r}"
            assert key == expected_key

    def test_board_hamburg_properties(self, loader: GameDataLoader) -> None:
        """Test Hamburg position properties on the reconstructed map."""
        board = loader.load_board()
        hamburg = board.get_position(10, 1)
        assert hamburg is not None
        assert hamburg.location_name == "Hamburg"
        assert hamburg.terrain == "city"
        assert hamburg.coordinate.q == 10
        assert hamburg.coordinate.r == 1

    def test_board_berlin_properties(self, loader: GameDataLoader) -> None:
        """Test Berlin position properties on the reconstructed map."""
        board = loader.load_board()
        berlin = board.get_position(17, 2)
        assert berlin is not None
        assert berlin.location_name == "Berlin"
        assert berlin.marker == "B"

    def test_board_münchen_properties(self, loader: GameDataLoader) -> None:
        """Test München position properties on the reconstructed map."""
        board = loader.load_board()
        münchen = board.get_position(14, 7)
        assert münchen is not None
        assert münchen.location_name == "München"
        assert münchen.terrain == "home"


class TestGameDataLoaderWithBoard:
    """Test GameDataLoader includes board in all() method."""

    @pytest.fixture
    def loader(self) -> GameDataLoader:
        """Create a game data loader instance."""
        return GameDataLoader()

    def test_load_all_includes_board(self, loader: GameDataLoader) -> None:
        """Test that load_all() includes board data."""
        data = loader.load_all()
        assert "board" in data
        assert isinstance(data["board"], GameBoard)

    def test_load_all_board_complete(self, loader: GameDataLoader) -> None:
        """Test that board in load_all() is complete."""
        data = loader.load_all()
        board = data["board"]
        assert len(board.positions) == 131
