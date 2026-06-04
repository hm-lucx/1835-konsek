"""Domain models for 1835 Konsek game."""
from dataclasses import dataclass

from pydantic import BaseModel


class Tile(BaseModel):
    """Representation of a game tile."""

    id: int
    color: str
    name: str
    cities: int


class Locomotive(BaseModel):
    """Locomotive tier definition."""

    tier: int
    name: str
    price: int
    count: int
    scrap_trigger: int | None = None
    description: str


class PrivateRailroad(BaseModel):
    """Private railway company."""

    id: str
    name: str
    purchase_price: int
    income: int
    description: str


class VorpreussischeGesellschaft(BaseModel):
    """Pre-Prussian railway company."""

    id: str
    name: str
    abbreviation: str
    home_city: str
    par_price: int
    share_count: int
    description: str


class Aktiengesellschaft(BaseModel):
    """Major stock railway company."""

    id: str
    name: str
    abbreviation: str
    home_city: str
    par_price: int
    share_count: int
    token_color: str
    description: str


class Share(BaseModel):
    """Share certificate."""

    id: str
    company_id: str
    company_name: str
    percentage: int
    par_value: int


class PlayerBoard(BaseModel):
    """Player board for tracking shares and investment."""

    id: str
    size: str  # "large" or "small"
    max_shares: int
    certificate_slots: int
    description: str


class HexCoordinate(BaseModel):
    """Hexagonal coordinate using axial system (q, r)."""

    q: int
    r: int

    def __hash__(self) -> int:
        """Make HexCoordinate hashable for dict keys."""
        return hash((self.q, self.r))

    def __eq__(self, other: object) -> bool:
        """Check equality with another HexCoordinate."""
        if not isinstance(other, HexCoordinate):
            return NotImplemented
        return self.q == other.q and self.r == other.r


class HexPosition(BaseModel):
    """Position of a tile on the game board."""

    coordinate: HexCoordinate
    tile_id: int
    location_name: str


class GameBoard(BaseModel):
    """Game board with hex positions and tile placements."""

    width: int
    height: int
    positions: dict[str, HexPosition]

    def get_position(self, q: int, r: int) -> HexPosition | None:
        """Get hex position by coordinate."""
        key = f"{q},{r}"
        return self.positions.get(key)

    def get_tile_at(self, q: int, r: int) -> Tile | None:
        """Get tile at hex coordinate (requires tile data)."""
        pos = self.get_position(q, r)
        if pos:
            return Tile(id=pos.tile_id, color="", name=pos.location_name, cities=0)
        return None


@dataclass(frozen=True)
class GameState:
    """Immutable game state."""

    players: list[str]
    current_player_index: int
    round_number: int
    turn_number: int
    cash_per_player: dict[str, int]
    bank_balance: int
    available_trains: list[str]
    unavailable_trains: list[str]
    player_trains: dict[str, list[str]]
    company_status: dict[str, dict[str, object]]
    start_packet: dict[str, list[str]]
    unsold_shares: dict[str, list[str]]

    @staticmethod
    def initial(num_players: int) -> "GameState":
        """
        Create initial game state for given number of players.

        Args:
            num_players: Number of players (3-7)

        Returns:
            Initial GameState

        Raises:
            ValueError: If num_players is not between 3 and 7
        """
        if not (3 <= num_players <= 7):
            raise ValueError("Number of players must be between 3 and 7")

        # Starting capital per player
        starting_capital = {
            3: 600,
            4: 475,
            5: 390,
            6: 340,
            7: 310,
        }

        capital_per_player = starting_capital[num_players]
        player_names = [f"Player {i + 1}" for i in range(num_players)]

        # Calculate total cash in bank (12,000M total)
        total_cash = 12_000
        players_total = capital_per_player * num_players
        bank_balance = total_cash - players_total

        # Initialize cash per player
        cash_per_player = {name: capital_per_player for name in player_names}

        # Create start packet with bonus shares
        # Bayern and Sachsen start on "Nichtverkaufte Aktien" (unsold shares)
        start_packet_shares = {
            "Bayern": ["BY_1", "BY_2"],  # 2 bonus shares for start packet
            "Sachsen": ["SA_1", "SA_2"],  # 2 bonus shares for start packet
        }

        # Initialize available trains: 9 2-locomotives available initially
        available_trains = ["2-loco"] * 9

        # Rest of locomotives not available
        unavailable_trains = [
            "3-loco"] * 8 + ["4-loco"] * 6 + ["5-loco"] * 5 + ["6-loco"] * 3 + ["6+6-loco"] * 2

        # Player 1 gets wooden locomotive
        player_trains = {
            player_names[0]: ["wooden-loco"]
        }

        # Initialize other players without trains
        for player_name in player_names[1:]:
            player_trains[player_name] = []

        # Initialize company status for all companies
        company_status = {
            # AGs
            "Bayern": {"status": "inactive", "shares_issued": 0},
            "Sachsen": {"status": "inactive", "shares_issued": 0},
            "Baden": {"status": "inactive", "shares_issued": 0},
            "Württemberg": {"status": "inactive", "shares_issued": 0},
            "Hessen": {"status": "inactive", "shares_issued": 0},
            "Mecklenburg-Strelitz": {"status": "inactive", "shares_issued": 0},
            "Oldenburg": {"status": "inactive", "shares_issued": 0},
            "Preußen": {"status": "inactive", "shares_issued": 0},
            # Vorpreussische
            "Bergisch-Märkische": {"status": "inactive", "shares_issued": 0},
            "Berlin-Potsdam": {"status": "inactive", "shares_issued": 0},
            "Magdeburger": {"status": "inactive", "shares_issued": 0},
            "Köln-Minden": {"status": "inactive", "shares_issued": 0},
            "Berlin-Stettiner": {"status": "inactive", "shares_issued": 0},
            "Altona-Kiel": {"status": "inactive", "shares_issued": 0},
        }

        # Unsold shares: Bayern and Sachsen shares not in start packet
        unsold_shares = {
            "Bayern": ["BY_3", "BY_4", "BY_5", "BY_6", "BY_7", "BY_8"],
            "Sachsen": ["SA_3", "SA_4", "SA_5", "SA_6", "SA_7", "SA_8"],
        }

        return GameState(
            players=player_names,
            current_player_index=0,
            round_number=1,
            turn_number=1,
            cash_per_player=cash_per_player,
            bank_balance=bank_balance,
            available_trains=available_trains,
            unavailable_trains=unavailable_trains,
            player_trains=player_trains,
            company_status=company_status,
            start_packet=start_packet_shares,
            unsold_shares=unsold_shares,
        )
