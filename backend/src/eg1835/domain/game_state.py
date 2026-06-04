"""Phase 4 GameState for 1835 Konsek.

An immutable record of all state needed by the action / FSM layer.  Fields are
*never mutated in place* -- actions always call ``dataclasses.replace()`` to
produce a new instance.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .fsm import GameLoopPhase, ORPhase


@dataclass(frozen=True)
class GameState:
    """Snapshot of the full game state, consumed and produced by every Action."""

    # --- Players ---
    players: list[str]
    current_player_index: int
    cash_per_player: dict[str, int]  # player_id → cash

    # --- Bank ---
    bank_balance: int
    available_trains: dict[int, int]  # tier → remaining count in bank

    # --- Companies ---
    company_trains: dict[str, list[int]]  # company_id → list of tiers owned
    company_cash: dict[str, int]  # company_id → treasury

    # --- FSM ---
    game_phase: int  # 1–6, advances when a higher-tier loco is first bought
    game_loop_phase: GameLoopPhase
    or_phase: ORPhase | None  # None when not in OR
    active_company_id: str | None  # company currently running its OR turn

    # --- AR end-condition tracking (rule 2.3) ---
    # Increments on every non-buy action (Pass, SellShares).
    # Resets to 0 on any purchase.
    # When it reaches len(players) the AR ends.
    ar_consecutive_passes: int

    # ------------------------------------------------------------------ #
    # Factories                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def initial(num_players: int) -> GameState:
        """Create the starting state for a new game (rules 1.1, 2.1)."""
        if not (3 <= num_players <= 7):
            raise ValueError("num_players must be between 3 and 7")

        starting_capital: dict[int, int] = {
            3: 600, 4: 475, 5: 390, 6: 340, 7: 310
        }
        capital = starting_capital[num_players]
        player_names = [f"Player {i + 1}" for i in range(num_players)]
        bank = 12_000 - capital * num_players

        return GameState(
            players=player_names,
            current_player_index=0,
            cash_per_player={p: capital for p in player_names},
            bank_balance=bank,
            available_trains={1: 9, 2: 8, 3: 6, 4: 5, 5: 3, 6: 2},
            company_trains={},
            company_cash={},
            game_phase=1,
            game_loop_phase=GameLoopPhase.START_PACKET_AR,
            or_phase=None,
            active_company_id=None,
            ar_consecutive_passes=0,
        )

    # ------------------------------------------------------------------ #
    # Helpers used by actions (keep apply() methods readable)             #
    # ------------------------------------------------------------------ #

    @property
    def current_player(self) -> str:
        return self.players[self.current_player_index]

    def with_next_player(self) -> GameState:
        """Advance current_player_index to the next player (wraps around)."""
        return dataclasses.replace(
            self,
            current_player_index=(self.current_player_index + 1) % len(self.players),
        )
