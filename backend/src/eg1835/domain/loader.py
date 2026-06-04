"""Data loading utilities for game configuration."""
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Aktiengesellschaft,
    GameBoard,
    HexCoordinate,
    HexPosition,
    Locomotive,
    PlayerBoard,
    PrivateRailroad,
    Share,
    Tile,
    VorpreussischeGesellschaft,
)


class GameDataLoader:
    """Load and parse game configuration from YAML files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize loader with data directory."""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = data_dir

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        """Load YAML file and return parsed content."""
        filepath = self.data_dir / filename
        with open(filepath, encoding="utf-8") as f:
            result = yaml.safe_load(f)
            return result if isinstance(result, dict) else {}

    def load_tiles(self) -> list[Tile]:
        """Load tiles from YAML."""
        data = self._load_yaml("tiles.yml")
        return [Tile(**tile) for tile in data.get("tiles", [])]

    def load_locomotives(self) -> list[Locomotive]:
        """Load locomotives from YAML."""
        data = self._load_yaml("locomotives.yml")
        return [Locomotive(**loco) for loco in data.get("locomotives", [])]

    def load_private_railways(self) -> list[PrivateRailroad]:
        """Load private railways from YAML."""
        data = self._load_yaml("private_railways.yml")
        return [
            PrivateRailroad(**railway) for railway in data.get("private_railways", [])
        ]

    def load_vorpreussische(self) -> list[VorpreussischeGesellschaft]:
        """Load Vorpreussische companies from YAML."""
        data = self._load_yaml("vorpreussische.yml")
        return [
            VorpreussischeGesellschaft(**company)
            for company in data.get("vorpreussische", [])
        ]

    def load_aktiengesellschaften(self) -> list[Aktiengesellschaft]:
        """Load Aktiengesellschaften from YAML."""
        data = self._load_yaml("aktiengesellschaften.yml")
        return [
            Aktiengesellschaft(**company)
            for company in data.get("aktiengesellschaften", [])
        ]

    def load_shares(self) -> list[Share]:
        """Load shares from YAML."""
        data = self._load_yaml("shares.yml")
        return [Share(**share) for share in data.get("shares", [])]

    def load_player_boards(self) -> list[PlayerBoard]:
        """Load player boards from YAML."""
        data = self._load_yaml("player_boards.yml")
        return [
            PlayerBoard(**board) for board in data.get("player_boards", [])
        ]

    def load_board(self) -> GameBoard:
        """Load game board with hex positions."""
        data = self._load_yaml("board.yml")
        board_data = data.get("board", {})
        width = board_data.get("width", 14)
        height = board_data.get("height", 10)

        positions: dict[str, HexPosition] = {}
        for pos_data in board_data.get("positions", []):
            q = pos_data.get("q", 0)
            r = pos_data.get("r", 0)
            coordinate = HexCoordinate(q=q, r=r)
            key = f"{q},{r}"
            positions[key] = HexPosition(
                coordinate=coordinate,
                tile_id=pos_data.get("tile_id", 0),
                location_name=pos_data.get("name", ""),
            )

        return GameBoard(width=width, height=height, positions=positions)

    def load_all(self) -> dict[str, Any]:
        """Load all game data."""
        return {
            "tiles": self.load_tiles(),
            "locomotives": self.load_locomotives(),
            "private_railways": self.load_private_railways(),
            "vorpreussische": self.load_vorpreussische(),
            "aktiengesellschaften": self.load_aktiengesellschaften(),
            "shares": self.load_shares(),
            "player_boards": self.load_player_boards(),
            "board": self.load_board(),
        }
