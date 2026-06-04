"""GameState for 1835 Konsek (Phase 4 + Phase 5).

An immutable record of all state needed by the action / FSM layer.  Fields are
*never mutated in place* -- actions always call ``dataclasses.replace()`` to
produce a new instance.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .fsm import GameLoopPhase, ORPhase
from .start_packet import BASE_CERT_LIMIT, INITIAL_START_PACKET_ROWS


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
    # Legacy "highest locomotive tier purchased" (1–10).  NOT the coloured
    # phase; kept for Phase-4 compatibility.  See ``colored_phase`` below.
    game_phase: int
    game_loop_phase: GameLoopPhase
    or_phase: ORPhase | None  # None when not in OR
    active_company_id: str | None  # company currently running its OR turn

    # --- AR end-condition tracking (rule 2.3) ---
    # Increments on every non-buy action (Pass, SellShares).
    # Resets to 0 on any purchase.
    # When it reaches len(players) the AR ends.
    ar_consecutive_passes: int

    # ------------------------------------------------------------------ #
    # Phase 5 – Share-round (AR) state (all defaulted for backward compat)#
    # ------------------------------------------------------------------ #

    # player_id → {company_id → percent held}
    player_shares: dict[str, dict[str, int]] = field(default_factory=dict)
    # company_id → player_id of current director (None = no director yet)
    company_directors: dict[str, str | None] = field(default_factory=dict)
    # company_id → % currently in the bank pool (sold back, max 50%)
    pool_shares: dict[str, int] = field(default_factory=dict)
    # company_id → current price on the Aktienkurstafel
    share_prices: dict[str, int] = field(default_factory=dict)
    # company_id → "inactive" | "launched"
    company_status: dict[str, str] = field(default_factory=dict)
    # company_id → % still sitting in "Nichtverkaufte Aktien"
    unsold_shares: dict[str, int] = field(default_factory=dict)
    # Remaining start-packet rows; outer tuple = rows, inner = item IDs
    start_packet_rows: tuple[tuple[str, ...], ...] = field(
        default_factory=lambda: ()
    )
    # player_id → tuple of company_ids sold from this AR (no re-buy rule 2.6.2)
    ar_sold_companies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Companies that launched *this* AR – their shares are unsellable until next AR
    companies_launched_this_ar: tuple[str, ...] = field(default_factory=lambda: ())
    # player_id → number of certificates held (for paper limit rule 2.6.2.6)
    player_certificates: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Phase 6 – Operating-round (OR) state (all defaulted for back compat)#
    # ------------------------------------------------------------------ #

    # Coloured phase: 1=gelb, 2=grün, 3=braun (rule 5.2).  Drives tile colours
    # and the number of ORs between two ARs.
    colored_phase: int = 1
    # Active number of ORs per OR-set (between two ARs) – rule 5.2.
    ors_per_set: int = 1
    # OR count that takes effect from the *next* AR onward ("ab der nächsten AR").
    pending_ors_per_set: int = 1
    # Canonical train ids whose first copy has been bought (phase-trigger memo).
    trains_first_bought: frozenset[str] = field(default_factory=frozenset)
    # Preußen state machine (rules 4, 5.5.4.14).
    preussen_can_open: bool = False  # set by first 4-Lok
    preussen_must_open: bool = False  # set by first 4+4-Lok (rule 4.6)
    preussen_opened: bool = False
    # Per-company counters for the *current* OR turn (rules 5.4.1, 5.5.2).
    tiles_laid_this_turn: dict[str, int] = field(default_factory=dict)
    stations_built_this_turn: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Phase 7 – Special cases (all defaulted for backward compat)         #
    # ------------------------------------------------------------------ #

    # Index of the wooden-locomotive holder / start player (rules 1, 5.5.4.13).
    start_player_index: int = 0
    # private-railway id → owner player_id (NF, LD, BS, HA, OB, PF) – rule 3.1.
    private_owners: dict[str, str] = field(default_factory=dict)
    # Private railways removed from play (rule 3.1.3 close triggers, 3rd phase).
    closed_privates: frozenset[str] = field(default_factory=frozenset)
    # Named special fields already built – OB's two fields + Mannheim/Ludwigshafen
    # (rules 3.1.3.2, 3.1.3.3, 5.5.2.10).  Board geometry is deferred; callers
    # pass the field id.
    built_fields: frozenset[str] = field(default_factory=frozenset)
    # Whether Baden has placed its home station in M/L (rule 5.5.2.10).
    baden_home_chosen: bool = False
    # Companies that have already operated in the *current* OR (rule 4.5 double-
    # use protection for Preußen).
    companies_operated_this_or: frozenset[str] = field(default_factory=frozenset)
    # True for the current OR if Preußen was opened *after* BP already operated
    # and must therefore pause this OR (rule 4.5).
    preussen_paused_this_or: bool = False
    # Players who went bankrupt and left the game (rule 5.5.4.13).
    bankrupt_players: frozenset[str] = field(default_factory=frozenset)
    # company_id → outstanding bank loan that forces saving until repaid (5.5.4.13).
    company_debt: dict[str, int] = field(default_factory=dict)

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
            # Full roster keyed by integer tier (rule Promotionstabellen):
            # 1:"2"=9, 2:"3"=4, 3:"4"=3, 4:"5"=2, 5:"6"=2, 6:"6+6"=4,
            # 7:"2+2"=4, 8:"3+3"=3, 9:"4+4"=1, 10:"5+5"=1.
            available_trains={
                1: 9, 2: 4, 3: 3, 4: 2, 5: 2, 6: 4, 7: 4, 8: 3, 9: 1, 10: 1
            },
            company_trains={},
            company_cash={},
            game_phase=1,
            game_loop_phase=GameLoopPhase.START_PACKET_AR,
            or_phase=None,
            active_company_id=None,
            ar_consecutive_passes=0,
            # Phase 5 fields
            player_shares={p: {} for p in player_names},
            company_directors={},
            pool_shares={},
            share_prices={},
            company_status={},
            unsold_shares={},
            start_packet_rows=INITIAL_START_PACKET_ROWS,
            ar_sold_companies={p: () for p in player_names},
            companies_launched_this_ar=(),
            player_certificates={p: 0 for p in player_names},
            # Phase 6 fields
            colored_phase=1,
            ors_per_set=1,
            pending_ors_per_set=1,
            trains_first_bought=frozenset(),
            preussen_can_open=False,
            preussen_must_open=False,
            preussen_opened=False,
            tiles_laid_this_turn={},
            stations_built_this_turn={},
            # Phase 7 fields
            start_player_index=0,
            private_owners={},
            closed_privates=frozenset(),
            built_fields=frozenset(),
            baden_home_chosen=False,
            companies_operated_this_or=frozenset(),
            preussen_paused_this_or=False,
            bankrupt_players=frozenset(),
            company_debt={},
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

    def certificate_limit(self, player_id: str) -> int:
        """Paper limit for *player_id*, including the ≥80% company bonus (2.6.2.6)."""
        base = BASE_CERT_LIMIT.get(len(self.players), 20)
        bonus = sum(
            1
            for pct in self.player_shares.get(player_id, {}).values()
            if pct >= 80
        )
        return base + bonus

    def total_sold(self, company_id: str) -> int:
        """Total % of *company_id* held by players + pool (used for launch check)."""
        player_total = sum(
            shares.get(company_id, 0) for shares in self.player_shares.values()
        )
        return player_total + self.pool_shares.get(company_id, 0)
