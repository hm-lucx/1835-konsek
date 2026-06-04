"""Tests for Phase 1: Game data and configuration."""
import pytest

from eg1835.domain.loader import GameDataLoader
from eg1835.domain.models import GameState


class TestGameDataLoading:
    """Test that all YAML files load correctly."""

    @pytest.fixture
    def loader(self) -> GameDataLoader:
        """Create a game data loader instance."""
        return GameDataLoader()

    def test_tiles_load(self, loader: GameDataLoader) -> None:
        """Test that tiles load successfully."""
        tiles = loader.load_tiles()
        assert len(tiles) == 147
        assert all(t.color in ["yellow", "green", "brown"] for t in tiles)
        assert all(t.id > 0 for t in tiles)

    def test_locomotives_load(self, loader: GameDataLoader) -> None:
        """Test that locomotives load successfully."""
        locomotives = loader.load_locomotives()
        assert len(locomotives) > 0
        total_count = sum(loco.count for loco in locomotives)
        assert total_count == 33
        assert all(loco.price > 0 for loco in locomotives)

    def test_private_railways_load(self, loader: GameDataLoader) -> None:
        """Test that private railways load successfully."""
        railways = loader.load_private_railways()
        assert len(railways) == 6
        railway_ids = {r.id for r in railways}
        expected_ids = {"NF", "LD", "BS", "HA", "OB", "PF"}
        assert railway_ids == expected_ids

    def test_vorpreussische_load(self, loader: GameDataLoader) -> None:
        """Test that Vorpreussische companies load successfully."""
        companies = loader.load_vorpreussische()
        assert len(companies) == 6
        company_ids = {c.id for c in companies}
        expected_ids = {"BM", "BP", "MD", "KM", "BS", "AK"}
        assert company_ids == expected_ids

    def test_aktiengesellschaften_load(self, loader: GameDataLoader) -> None:
        """Test that Aktiengesellschaften load successfully."""
        companies = loader.load_aktiengesellschaften()
        assert len(companies) == 8
        company_ids = {c.id for c in companies}
        expected_ids = {"BY", "SA", "BA", "WÜ", "HE", "MS", "OL", "PR"}
        assert company_ids == expected_ids

    def test_shares_load(self, loader: GameDataLoader) -> None:
        """Test that shares load successfully."""
        shares = loader.load_shares()
        assert len(shares) == 68

    def test_player_boards_load(self, loader: GameDataLoader) -> None:
        """Test that player boards load successfully."""
        boards = loader.load_player_boards()
        assert len(boards) == 14  # 8 large + 6 small
        large_boards = [b for b in boards if b.size == "large"]
        small_boards = [b for b in boards if b.size == "small"]
        assert len(large_boards) == 8
        assert len(small_boards) == 6

    def test_all_data_loads(self, loader: GameDataLoader) -> None:
        """Test that all data loads without errors."""
        data = loader.load_all()
        assert "tiles" in data
        assert "locomotives" in data
        assert "private_railways" in data
        assert "vorpreussische" in data
        assert "aktiengesellschaften" in data
        assert "shares" in data
        assert "player_boards" in data


class TestGameState:
    """Test GameState initialization and mechanics."""

    def test_initial_3_players(self) -> None:
        """Test GameState.initial with 3 players."""
        state = GameState.initial(3)
        assert len(state.players) == 3
        assert state.current_player_index == 0
        assert state.round_number == 1
        assert state.turn_number == 1
        # Check starting capital
        for cash in state.cash_per_player.values():
            assert cash == 600

    def test_initial_4_players(self) -> None:
        """Test GameState.initial with 4 players."""
        state = GameState.initial(4)
        assert len(state.players) == 4
        for cash in state.cash_per_player.values():
            assert cash == 475

    def test_initial_5_players(self) -> None:
        """Test GameState.initial with 5 players."""
        state = GameState.initial(5)
        assert len(state.players) == 5
        for cash in state.cash_per_player.values():
            assert cash == 390

    def test_initial_6_players(self) -> None:
        """Test GameState.initial with 6 players."""
        state = GameState.initial(6)
        assert len(state.players) == 6
        for cash in state.cash_per_player.values():
            assert cash == 340

    def test_initial_7_players(self) -> None:
        """Test GameState.initial with 7 players."""
        state = GameState.initial(7)
        assert len(state.players) == 7
        for cash in state.cash_per_player.values():
            assert cash == 310

    def test_initial_invalid_players(self) -> None:
        """Test that invalid player counts raise errors."""
        with pytest.raises(ValueError):
            GameState.initial(2)
        with pytest.raises(ValueError):
            GameState.initial(8)

    def test_bank_total_for_3_players(self) -> None:
        """Test that bank balance is correct for 3 players."""
        state = GameState.initial(3)
        total = state.bank_balance + sum(state.cash_per_player.values())
        assert total == 12_000

    def test_bank_total_for_4_players(self) -> None:
        """Test that bank balance is correct for 4 players."""
        state = GameState.initial(4)
        total = state.bank_balance + sum(state.cash_per_player.values())
        assert total == 12_000

    def test_bank_total_for_7_players(self) -> None:
        """Test that bank balance is correct for 7 players."""
        state = GameState.initial(7)
        total = state.bank_balance + sum(state.cash_per_player.values())
        assert total == 12_000

    def test_available_trains(self) -> None:
        """Test that 9 2-locomotives are available initially."""
        state = GameState.initial(4)
        available_2_locos = [t for t in state.available_trains if t == "2-loco"]
        assert len(available_2_locos) == 9

    def test_unavailable_trains_sum(self) -> None:
        """Test that unavailable trains sum correctly."""
        state = GameState.initial(4)
        total_trains = len(state.available_trains) + len(state.unavailable_trains)
        # 33 total locomotives + wooden locomotive
        # 9 available 2-locos + rest unavailable
        assert total_trains == 33

    def test_player_1_has_wooden_locomotive(self) -> None:
        """Test that Player 1 receives wooden locomotive."""
        state = GameState.initial(4)
        player1_trains = state.player_trains[state.players[0]]
        assert "wooden-loco" in player1_trains

    def test_other_players_no_trains(self) -> None:
        """Test that other players start with no trains."""
        state = GameState.initial(4)
        for i, player in enumerate(state.players):
            if i == 0:
                continue
            assert len(state.player_trains[player]) == 0

    def test_start_packet(self) -> None:
        """Test that start packet is initialized correctly."""
        state = GameState.initial(4)
        assert "Bayern" in state.start_packet
        assert "Sachsen" in state.start_packet
        assert len(state.start_packet["Bayern"]) == 2
        assert len(state.start_packet["Sachsen"]) == 2

    def test_unsold_shares(self) -> None:
        """Test that Bayern and Sachsen have unsold shares."""
        state = GameState.initial(4)
        assert "Bayern" in state.unsold_shares
        assert "Sachsen" in state.unsold_shares
        assert len(state.unsold_shares["Bayern"]) == 6
        assert len(state.unsold_shares["Sachsen"]) == 6

    def test_company_status_all_inactive(self) -> None:
        """Test that all companies start as inactive."""
        state = GameState.initial(4)
        for company_name, status in state.company_status.items():
            assert status["status"] == "inactive"
            assert status["shares_issued"] == 0

    def test_game_state_frozen(self) -> None:
        """Test that GameState is frozen (immutable)."""
        state = GameState.initial(4)
        with pytest.raises(Exception):  # FrozenInstanceError
            state.round_number = 2  # type: ignore

    def test_cash_per_player_consistency(self) -> None:
        """Test that all players have equal starting cash."""
        state = GameState.initial(4)
        cash_values = list(state.cash_per_player.values())
        assert all(c == cash_values[0] for c in cash_values)

    def test_player_count_matches_cash_dict(self) -> None:
        """Test that player count matches cash_per_player dict."""
        state = GameState.initial(5)
        assert len(state.players) == len(state.cash_per_player)
        assert set(state.players) == set(state.cash_per_player.keys())
