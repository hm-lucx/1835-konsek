"""Action framework for 1835 Konsek (Phase 4).

Every state mutation goes through an Action: validate first, then apply.
Actions are immutable frozen dataclasses; GameState is never mutated in place.

Action Protocol
---------------
    player_id : str
    validate(state) -> Ok[None] | Err[RuleViolation]
    apply(state)    -> GameState          # only call after validate succeeds

Stock-Round (AR)
    BuyStartItem · BuyShareFromBank · BuyShareFromPool
    Nationalize · SellShares · Pass

OR – Build phase (rule 5.4 BUILD)
    LayTile · UpgradeTile
    UseNFAbility · UseOBAbility · UsePFBuildAbility

OR – Station phase (rule 5.4 STATION)
    PlaceStation · UsePFStationAbility

OR – Run phase (rule 5.4 RUN / DIVIDEND_DECISION)
    RunTrains · DeclareDividend · WithholdDividend

OR – Train-purchase phase (rule 5.4 BUY_TRAIN)
    BuyTrainFromBank · BuyTrainFromPool · BuyTrainFromCompany

Special
    OpenPreussen · ConvertToPreussenShare · ChooseBadenHomeStation
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from .fsm import (
    TRAIN_PRICES,
    GameLoopPhase,
    ORPhase,
    advance_or_phase,
    scrap_tier_on_purchase,
)
from .game_state import GameState
from .result import Err, Ok
from .share_price import step_down, step_up
from .start_packet import (
    START_PACKET_ITEMS,
    buyable_item_ids,
    remove_item,
)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

PlayerId = str


@dataclass(frozen=True)
class RuleViolation:
    """Carries the rule reference and a human-readable explanation."""

    rule: str
    message: str


ValidateResult = Ok[None] | Err[RuleViolation]


# ---------------------------------------------------------------------------
# Protocol – structural type that every action satisfies
# ---------------------------------------------------------------------------


class Action(Protocol):
    """Structural interface shared by all action classes."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult: ...

    def apply(self, state: GameState) -> GameState: ...


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _require_loop_phase(
    state: GameState, *phases: GameLoopPhase, rule: str = "1.1"
) -> ValidateResult:
    if state.game_loop_phase not in phases:
        return Err(
            RuleViolation(
                rule=rule,
                message=f"Expected game loop in {phases}, got {state.game_loop_phase}",
            )
        )
    return Ok(None)


def _require_or_phase(
    state: GameState, *phases: ORPhase, rule: str = "5.4"
) -> ValidateResult:
    if state.or_phase not in phases:
        return Err(
            RuleViolation(
                rule=rule,
                message=f"Expected OR phase in {phases}, got {state.or_phase}",
            )
        )
    return Ok(None)


def _ar_phases() -> tuple[GameLoopPhase, ...]:
    return (GameLoopPhase.START_PACKET_AR, GameLoopPhase.AR)


def _advance_ar(state: GameState, *, reset_passes: bool) -> GameState:
    """Advance to the next AR player; optionally reset pass counter."""
    new_passes = 0 if reset_passes else state.ar_consecutive_passes + 1
    next_idx = (state.current_player_index + 1) % len(state.players)
    # AR ends when every player has consecutively not bought (rule 2.3).
    ar_ending = new_passes >= len(state.players)
    new_loop = GameLoopPhase.OR if ar_ending else state.game_loop_phase
    if ar_ending:
        new_passes = 0
    new_state = dataclasses.replace(
        state,
        current_player_index=next_idx,
        ar_consecutive_passes=new_passes,
        game_loop_phase=new_loop,
    )
    if ar_ending:
        new_state = _apply_round_end_price_rises(new_state)
        new_state = _reset_ar_tracking(new_state)
    return new_state


def _apply_phase_change(state: GameState, purchasing_tier: int) -> GameState:
    """Advance game phase and scrap obsolete trains if a new tier was bought."""
    if purchasing_tier <= state.game_phase:
        return state
    scrap_tier = scrap_tier_on_purchase(purchasing_tier)
    new_company_trains: dict[str, list[int]] = {}
    for cid, trains in state.company_trains.items():
        if scrap_tier is not None:
            new_company_trains[cid] = [t for t in trains if t != scrap_tier]
        else:
            new_company_trains[cid] = list(trains)
    return dataclasses.replace(
        state,
        game_phase=purchasing_tier,
        company_trains=new_company_trains,
    )


# ---------------------------------------------------------------------------
# Phase 5 private helpers
# ---------------------------------------------------------------------------

_PREUSSISCHE_COMPANIES = frozenset({"BM", "BP", "MD", "KM", "BS", "AK"})
_DIRECTOR_THRESHOLD = 20  # % needed to hold director's certificate
_PREUSSEN_DIRECTOR_MIN = 10  # Preußen director min-holding rule
_MAX_POOL_PCT = 50  # bank pool cap per company
_LAUNCH_THRESHOLD = 50  # % sold triggers company launch (rule 2.7)
_NATIONALIZE_THRESHOLD = 55  # % that forces nationalization (rule 2.6.2.4)
_NATIONALIZE_FACTOR = 1.5  # payout multiplier for other holders


def _player_order_left_of(state: GameState, player_id: str) -> list[str]:
    """Players in circular order starting one seat LEFT of *player_id*."""
    idx = state.players.index(player_id)
    n = len(state.players)
    return [state.players[(idx - i) % n] for i in range(1, n)]


def _check_director_change(state: GameState, company_id: str) -> GameState:
    """Re-evaluate director of *company_id* and update state if needed (3.3.5-3.3.9)."""
    director = state.company_directors.get(company_id)
    if director is None:
        return state

    director_pct = state.player_shares.get(director, {}).get(company_id, 0)
    candidates = [
        p
        for p in state.players
        if p != director
        and state.player_shares.get(p, {}).get(company_id, 0) > director_pct
    ]
    if not candidates:
        return state  # director still has most (or tied): no change

    max_pct = max(state.player_shares.get(p, {}).get(company_id, 0) for p in candidates)
    tied = [
        p for p in candidates
        if state.player_shares.get(p, {}).get(company_id, 0) == max_pct
    ]
    if len(tied) > 1:
        # Multiple tied above director → leftmost from old director's seat (3.3.9)
        for candidate in _player_order_left_of(state, director):
            if candidate in tied:
                new_director = candidate
                break
        else:
            return state
    else:
        new_director = tied[0]

    # Certificate count adjustment: new_director loses 1 cert (net), director gains 1.
    new_certs = dict(state.player_certificates)
    new_certs[director] = new_certs.get(director, 0) + 1
    new_certs[new_director] = max(0, new_certs.get(new_director, 0) - 1)

    return dataclasses.replace(
        state,
        company_directors={**state.company_directors, company_id: new_director},
        player_certificates=new_certs,
    )


def _check_company_launch(state: GameState, company_id: str) -> GameState:
    """Launch *company_id* if ≥50% sold and it was inactive (rule 2.7)."""
    if state.company_status.get(company_id, "inactive") != "inactive":
        return state
    if state.total_sold(company_id) < _LAUNCH_THRESHOLD:
        return state

    # Capital = par price × shares already in player hands (2.7.6)
    par = state.share_prices.get(company_id, 100)
    shares_in_hands = sum(
        sh.get(company_id, 0) for sh in state.player_shares.values()
    )
    capital = par * shares_in_hands // 10  # each 10% cert = par value

    new_company_cash = {**state.company_cash, company_id: capital}
    new_status = {**state.company_status, company_id: "launched"}
    new_launched = state.companies_launched_this_ar + (company_id,)

    return dataclasses.replace(
        state,
        company_cash=new_company_cash,
        company_status=new_status,
        companies_launched_this_ar=new_launched,
    )


def _apply_round_end_price_rises(state: GameState) -> GameState:
    """Step up share price for companies with no pool AND no unsold shares (2.6.3.4)."""
    new_prices = dict(state.share_prices)
    for company_id, price in state.share_prices.items():
        if (
            state.pool_shares.get(company_id, 0) == 0
            and state.unsold_shares.get(company_id, 0) == 0
        ):
            new_prices[company_id] = step_up(price)
    return dataclasses.replace(state, share_prices=new_prices)


def _reset_ar_tracking(state: GameState) -> GameState:
    """Clear per-AR tracking fields at the start of a new AR or transition to OR."""
    return dataclasses.replace(
        state,
        ar_sold_companies={p: () for p in state.players},
        companies_launched_this_ar=(),
    )


# ===========================================================================
# Stock-Round (AR) actions
# ===========================================================================


@dataclass(frozen=True)
class BuyStartItem:
    """Buy a start-packet item in the opening AR (rules 2.4, 2.5).

    One purchase per turn; bonus Vorpreußische shares are automatically added.
    Row logic: only top non-empty row buyable; when exactly 1 item remains in
    the top row the first item of the next row is also available (rule 2.5).
    After the last item is bought BY and SA stacks go to the Aktienkurstafel.
    """

    player_id: PlayerId
    item_id: str

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.START_PACKET_AR, rule="2.4")
        if isinstance(result, Err):
            return result
        item = START_PACKET_ITEMS.get(self.item_id)
        if item is None:
            return Err(RuleViolation("2.4", f"Unknown start-packet item: {self.item_id}"))
        if self.item_id not in buyable_item_ids(state.start_packet_rows):
            return Err(
                RuleViolation("2.5", f"{self.item_id} is not available in the current row")
            )
        if state.cash_per_player.get(self.player_id, 0) < item.cost:
            return Err(
                RuleViolation(
                    "2.4",
                    f"Insufficient funds: need {item.cost}M, "
                    f"have {state.cash_per_player.get(self.player_id, 0)}M",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        item = START_PACKET_ITEMS[self.item_id]

        # Remove item from packet and deduct cost.
        new_rows = remove_item(state.start_packet_rows, self.item_id)
        new_cash = {
            **state.cash_per_player,
            self.player_id: state.cash_per_player[self.player_id] - item.cost,
        }

        # Add bonus Vorpreußische shares to player.
        player_sh = dict(state.player_shares.get(self.player_id, {}))
        for cid in item.bonus_shares:
            player_sh[cid] = player_sh.get(cid, 0) + 10
        new_player_shares = {**state.player_shares, self.player_id: player_sh}

        # Certificate count: 1 for private + 1 per bonus share.
        new_certs = dict(state.player_certificates)
        new_certs[self.player_id] = (
            new_certs.get(self.player_id, 0) + 1 + len(item.bonus_shares)
        )

        # When the packet empties BY and SA go to the Aktienkurstafel (rule 2.5).
        packet_empty = all(len(row) == 0 for row in new_rows)
        new_unsold = dict(state.unsold_shares)
        new_prices = dict(state.share_prices)
        new_status = dict(state.company_status)
        if packet_empty:
            for ag in ("BY", "SA"):
                new_unsold[ag] = 100  # all 100% sitting in Nichtverkaufte Aktien
                new_prices[ag] = 100  # par price on price board
                new_status[ag] = "inactive"

        new_state = dataclasses.replace(
            state,
            cash_per_player=new_cash,
            bank_balance=state.bank_balance + item.cost,
            start_packet_rows=new_rows,
            player_shares=new_player_shares,
            player_certificates=new_certs,
            unsold_shares=new_unsold,
            share_prices=new_prices,
            company_status=new_status,
        )

        # Packet empty → transition to OR; otherwise just advance to next player.
        if packet_empty:
            return dataclasses.replace(
                new_state,
                current_player_index=(
                    (new_state.current_player_index + 1) % len(new_state.players)
                ),
                game_loop_phase=GameLoopPhase.OR,
            )
        return dataclasses.replace(
            new_state,
            current_player_index=(
                (new_state.current_player_index + 1) % len(new_state.players)
            ),
        )


@dataclass(frozen=True)
class BuyShareFromBank:
    """Buy a share from the bank's unsold pile (Nichtverkaufte Aktien) in an AR.

    Enforces: no-resell rule (2.6.2), paper limit (2.6.2.6), sufficient funds.
    Triggers: director change (3.3.5), company launch at 50% (2.7).
    """

    player_id: PlayerId
    company_id: str
    percent: int  # 10 for a regular cert, 20 for a director's cert

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, *_ar_phases(), rule="2.6.2")
        if isinstance(result, Err):
            return result
        # Can't buy from a company you already sold this AR (rule 2.6.2).
        if self.company_id in state.ar_sold_companies.get(self.player_id, ()):
            return Err(
                RuleViolation(
                    "2.6.2",
                    f"Cannot buy {self.company_id}: already sold shares in this AR",
                )
            )
        # Must be available in unsold pile.
        available = state.unsold_shares.get(self.company_id, 0)
        if available < self.percent:
            return Err(
                RuleViolation(
                    "2.6.2",
                    f"Only {available}% of {self.company_id} available, need {self.percent}%",
                )
            )
        # Paper limit check (2.6.2.6).
        current_certs = state.player_certificates.get(self.player_id, 0)
        if current_certs >= state.certificate_limit(self.player_id):
            return Err(
                RuleViolation(
                    "2.6.2.6",
                    f"Paper limit reached ({current_certs} certs)",
                )
            )
        # Funds check: price = share_prices[company] * percent / 10.
        price_per_10 = state.share_prices.get(self.company_id, 100)
        cost = price_per_10 * self.percent // 10
        if state.cash_per_player.get(self.player_id, 0) < cost:
            return Err(
                RuleViolation(
                    "2.6.2",
                    f"Insufficient funds: need {cost}M",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        price_per_10 = state.share_prices.get(self.company_id, 100)
        cost = price_per_10 * self.percent // 10

        # Update cash and unsold.
        new_cash = {
            **state.cash_per_player,
            self.player_id: state.cash_per_player[self.player_id] - cost,
        }
        new_unsold = {
            **state.unsold_shares,
            self.company_id: state.unsold_shares.get(self.company_id, 0) - self.percent,
        }

        # Add shares to player.
        player_sh = dict(state.player_shares.get(self.player_id, {}))
        player_sh[self.company_id] = player_sh.get(self.company_id, 0) + self.percent
        new_player_shares = {**state.player_shares, self.player_id: player_sh}

        # First buyer of a company becomes director when they hold ≥ director threshold.
        new_directors = dict(state.company_directors)
        if new_directors.get(self.company_id) is None and self.percent >= _DIRECTOR_THRESHOLD:
            new_directors[self.company_id] = self.player_id

        # Certificate count: 1 cert per purchase regardless of percent.
        new_certs = dict(state.player_certificates)
        new_certs[self.player_id] = new_certs.get(self.player_id, 0) + 1

        new_state = dataclasses.replace(
            state,
            cash_per_player=new_cash,
            bank_balance=state.bank_balance + cost,
            unsold_shares=new_unsold,
            player_shares=new_player_shares,
            company_directors=new_directors,
            player_certificates=new_certs,
        )

        # Director change check (3.3.5).
        new_state = _check_director_change(new_state, self.company_id)
        # Company launch check (2.7).
        new_state = _check_company_launch(new_state, self.company_id)

        return _advance_ar(new_state, reset_passes=True)


@dataclass(frozen=True)
class BuyShareFromPool:
    """Buy a share from the bank pool (sold-back shares) in an AR (rule 2.6.2)."""

    player_id: PlayerId
    company_id: str
    percent: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, *_ar_phases(), rule="2.6.2")
        if isinstance(result, Err):
            return result
        if self.company_id in state.ar_sold_companies.get(self.player_id, ()):
            return Err(
                RuleViolation(
                    "2.6.2",
                    f"Cannot buy {self.company_id}: already sold shares in this AR",
                )
            )
        available = state.pool_shares.get(self.company_id, 0)
        if available < self.percent:
            return Err(
                RuleViolation(
                    "2.6.2",
                    f"Pool has only {available}% of {self.company_id}",
                )
            )
        current_certs = state.player_certificates.get(self.player_id, 0)
        if current_certs >= state.certificate_limit(self.player_id):
            return Err(RuleViolation("2.6.2.6", "Paper limit reached"))
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        price_per_10 = state.share_prices.get(self.company_id, 100)
        cost = price_per_10 * self.percent // 10
        new_cash = {
            **state.cash_per_player,
            self.player_id: state.cash_per_player[self.player_id] - cost,
        }
        new_pool = {
            **state.pool_shares,
            self.company_id: state.pool_shares.get(self.company_id, 0) - self.percent,
        }
        player_sh = dict(state.player_shares.get(self.player_id, {}))
        player_sh[self.company_id] = player_sh.get(self.company_id, 0) + self.percent
        new_player_shares = {**state.player_shares, self.player_id: player_sh}
        new_certs = dict(state.player_certificates)
        new_certs[self.player_id] = new_certs.get(self.player_id, 0) + 1
        new_state = dataclasses.replace(
            state,
            cash_per_player=new_cash,
            bank_balance=state.bank_balance + cost,
            pool_shares=new_pool,
            player_shares=new_player_shares,
            player_certificates=new_certs,
        )
        new_state = _check_director_change(new_state, self.company_id)
        new_state = _check_company_launch(new_state, self.company_id)
        return _advance_ar(new_state, reset_passes=True)


@dataclass(frozen=True)
class Nationalize:
    """Nationalize a Vorpreußische company (rule 2.6.2.4).

    Triggered when a player holds ≥55% of a Vorpreußische.  Other shareholders
    are paid 1.5 × current share price per 10% cert they hold.  The company is
    removed from play (status → "nationalized").  The nationalizing player
    retains their shares; they will later be converted to Preußen shares.
    """

    player_id: PlayerId
    company_id: str

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, *_ar_phases(), rule="2.6.2.4")
        if isinstance(result, Err):
            return result
        if self.company_id not in _PREUSSISCHE_COMPANIES:
            return Err(
                RuleViolation(
                    "2.6.2.4",
                    f"{self.company_id} is not a Vorpreußische company",
                )
            )
        held = state.player_shares.get(self.player_id, {}).get(self.company_id, 0)
        if held < _NATIONALIZE_THRESHOLD:
            return Err(
                RuleViolation(
                    "2.6.2.4",
                    f"Player holds {held}% of {self.company_id}; "
                    f"need ≥{_NATIONALIZE_THRESHOLD}% to nationalize",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        price = state.share_prices.get(self.company_id, 100)
        payout_per_10 = int(price * _NATIONALIZE_FACTOR)

        # Pay other holders 1.5× price per 10% cert.
        new_cash = dict(state.cash_per_player)
        for player, shares in state.player_shares.items():
            pct = shares.get(self.company_id, 0)
            if pct > 0 and player != self.player_id:
                new_cash[player] = new_cash.get(player, 0) + payout_per_10 * (pct // 10)

        # Remove company from all holdings (except the nationalizer keeps theirs for
        # conversion, represented by leaving the shares intact here).
        new_status = {**state.company_status, self.company_id: "nationalized"}

        new_state = dataclasses.replace(
            state,
            cash_per_player=new_cash,
            company_status=new_status,
        )
        return _advance_ar(new_state, reset_passes=True)


@dataclass(frozen=True)
class SellShares:
    """Sell shares back to the bank pool in an AR (rules 2.3, 2.6.3).

    Selling does *not* break the consecutive-pass chain (rule 2.3).
    Share price steps down immediately on each sale action (2.6.3.3).
    Max 50% may sit in the pool (2.6.3); director's share requires another
    player to hold ≥20% (10% for Preußen) (2.6.3.6).
    Companies launched this AR may not be sold back (2.7 implication).
    """

    player_id: PlayerId
    company_id: str
    percent: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, *_ar_phases(), rule="2.6.3")
        if isinstance(result, Err):
            return result
        # Shares of companies launched this AR are unsellable (rule 2.7).
        if self.company_id in state.companies_launched_this_ar:
            return Err(
                RuleViolation(
                    "2.7",
                    f"{self.company_id} launched this AR – shares unsellable until next AR",
                )
            )
        # Player must actually hold the shares.
        held = state.player_shares.get(self.player_id, {}).get(self.company_id, 0)
        if held < self.percent:
            return Err(
                RuleViolation(
                    "2.6.3",
                    f"Player holds only {held}% of {self.company_id}, cannot sell {self.percent}%",
                )
            )
        # Pool cap: can't push pool above 50% (2.6.3).
        current_pool = state.pool_shares.get(self.company_id, 0)
        if current_pool + self.percent > _MAX_POOL_PCT:
            return Err(
                RuleViolation(
                    "2.6.3",
                    f"Pool would exceed {_MAX_POOL_PCT}% "
                    f"(current {current_pool}% + {self.percent}%)",
                )
            )
        # Director's certificate may only be sold if another player holds ≥20% (2.6.3.6).
        is_director = state.company_directors.get(self.company_id) == self.player_id
        if is_director:
            min_threshold = (
                _PREUSSEN_DIRECTOR_MIN if self.company_id == "PR" else _DIRECTOR_THRESHOLD
            )
            others_max = max(
                (
                    state.player_shares.get(p, {}).get(self.company_id, 0)
                    for p in state.players
                    if p != self.player_id
                ),
                default=0,
            )
            if others_max < min_threshold:
                return Err(
                    RuleViolation(
                        "2.6.3.6",
                        f"No other player holds ≥{min_threshold}% of {self.company_id}; "
                        "director's share cannot be sold",
                    )
                )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        # Move shares from player to pool.
        player_sh = dict(state.player_shares.get(self.player_id, {}))
        player_sh[self.company_id] = player_sh.get(self.company_id, 0) - self.percent
        new_player_shares = {**state.player_shares, self.player_id: player_sh}
        new_pool = {
            **state.pool_shares,
            self.company_id: state.pool_shares.get(self.company_id, 0) + self.percent,
        }

        # Share price steps down immediately (2.6.3.3).
        old_price = state.share_prices.get(self.company_id, 100)
        new_prices = {**state.share_prices, self.company_id: step_down(old_price)}

        # Record the sale to enforce no-rebuy rule.
        sold = state.ar_sold_companies.get(self.player_id, ())
        if self.company_id not in sold:
            sold = sold + (self.company_id,)
        new_ar_sold = {**state.ar_sold_companies, self.player_id: sold}

        # Certificate count: player loses 1 cert.
        new_certs = dict(state.player_certificates)
        new_certs[self.player_id] = max(0, new_certs.get(self.player_id, 0) - 1)

        new_state = dataclasses.replace(
            state,
            player_shares=new_player_shares,
            pool_shares=new_pool,
            share_prices=new_prices,
            ar_sold_companies=new_ar_sold,
            player_certificates=new_certs,
        )
        # Director change: seller may no longer be biggest holder.
        new_state = _check_director_change(new_state, self.company_id)

        # Selling counts as a non-buy; pass counter advances.
        return _advance_ar(new_state, reset_passes=False)


@dataclass(frozen=True)
class Pass:
    """Pass the current turn.

    In AR: increments consecutive-pass counter (may end the AR).
    In OR BUILD / STATION / BUY_TRAIN: advances to the next OR sub-phase.
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        in_ar = state.game_loop_phase in _ar_phases()
        in_or_passable = state.or_phase in (
            ORPhase.BUILD,
            ORPhase.STATION,
            ORPhase.BUY_TRAIN,
        )
        if not (in_ar or (state.game_loop_phase == GameLoopPhase.OR and in_or_passable)):
            return Err(
                RuleViolation(
                    rule="5.4",
                    message=f"Pass not allowed in {state.game_loop_phase}/{state.or_phase}",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        if state.game_loop_phase in _ar_phases():
            return _advance_ar(state, reset_passes=False)
        # OR: advance the sub-phase.
        assert state.or_phase is not None
        return dataclasses.replace(state, or_phase=advance_or_phase(state.or_phase))


# ===========================================================================
# OR – Build phase
# ===========================================================================


@dataclass(frozen=True)
class LayTile:
    """Lay a yellow tile in the build phase (rule 5.4 BUILD, 5.5.1)."""

    player_id: PlayerId
    tile_id: int
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD, rule="5.5.1")

    def apply(self, state: GameState) -> GameState:
        return state  # board mutation deferred to Phase 2/5 integration


@dataclass(frozen=True)
class UpgradeTile:
    """Upgrade an existing tile in the build phase (rule 5.5.1.14)."""

    player_id: PlayerId
    tile_id: int
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD, rule="5.5.1.14")

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UseNFAbility:
    """Use the Nord-Flügel private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UseOBAbility:
    """Use the Oldenburg-Bremen private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


@dataclass(frozen=True)
class UsePFBuildAbility:
    """Use the Pfalzbahn private railway build ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUILD)

    def apply(self, state: GameState) -> GameState:
        return state


# ===========================================================================
# OR – Station phase
# ===========================================================================


@dataclass(frozen=True)
class PlaceStation:
    """Place a company station token (rule 5.4 STATION)."""

    player_id: PlayerId
    company_id: str
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION)

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))


@dataclass(frozen=True)
class UsePFStationAbility:
    """Use the Pfalzbahn private railway station ability."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION)

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))


# ===========================================================================
# OR – Run / Dividend-decision phase
# ===========================================================================


@dataclass(frozen=True)
class RunTrains:
    """Run the company's trains to collect revenue (rule 5.4 RUN, 5.5.3).

    Transitions RUN → DIVIDEND_DECISION upon application.
    """

    player_id: PlayerId
    company_id: str
    route_values: list[int]  # revenue per route

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.RUN, rule="5.5.3")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.RUN))


@dataclass(frozen=True)
class DeclareDividend:
    """Pay out the full revenue to shareholders (rule 5.5.3.11.5).

    Transitions DIVIDEND_DECISION → BUY_TRAIN upon application.
    """

    player_id: PlayerId
    company_id: str
    amount: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(
            state, or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION)
        )


@dataclass(frozen=True)
class WithholdDividend:
    """Retain all revenue in company treasury (rule 5.5.3.11.5).

    Transitions DIVIDEND_DECISION → BUY_TRAIN upon application.
    """

    player_id: PlayerId
    company_id: str

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(
            state, or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION)
        )


# ===========================================================================
# OR – Train-purchase phase
# ===========================================================================


@dataclass(frozen=True)
class BuyTrainFromBank:
    """Buy a locomotive from the bank (rule 5.4 BUY_TRAIN, 5.3).

    Triggers a game-phase advance when the first train of a new tier is
    purchased; scraps the obsolete tier as specified in rule 5.3.  Multiple
    purchases across different companies can each trigger a phase change.
    """

    player_id: PlayerId
    company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.3")
        if isinstance(result, Err):
            return result
        available = state.available_trains.get(self.tier, 0)
        if available <= 0:
            return Err(
                RuleViolation(
                    rule="5.3",
                    message=f"No tier-{self.tier} trains left in the bank",
                )
            )
        price = TRAIN_PRICES.get(self.tier, 0)
        company_balance = state.company_cash.get(self.company_id, 0)
        if company_balance < price:
            return Err(
                RuleViolation(
                    rule="5.3",
                    message=(
                        f"{self.company_id} cannot afford tier-{self.tier} train "
                        f"(needs {price}, has {company_balance})"
                    ),
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        price = TRAIN_PRICES[self.tier]
        # Update bank and company treasury.
        new_available = {**state.available_trains, self.tier: state.available_trains[self.tier] - 1}
        new_company_cash = {
            **state.company_cash,
            self.company_id: state.company_cash.get(self.company_id, 0) - price,
        }
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [self.tier],
        }
        new_state = dataclasses.replace(
            state,
            available_trains=new_available,
            company_cash=new_company_cash,
            company_trains=new_company_trains,
            bank_balance=state.bank_balance + price,
        )
        # Phase change: runs *after* train is placed, may scrap older trains.
        return _apply_phase_change(new_state, self.tier)


@dataclass(frozen=True)
class BuyTrainFromPool:
    """Buy a discarded locomotive from the market pool (rule 5.4 BUY_TRAIN)."""

    player_id: PlayerId
    company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.BUY_TRAIN)

    def apply(self, state: GameState) -> GameState:
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [self.tier],
        }
        new_state = dataclasses.replace(state, company_trains=new_company_trains)
        return _apply_phase_change(new_state, self.tier)


@dataclass(frozen=True)
class BuyTrainFromCompany:
    """Buy a locomotive directly from another company (rule 5.4 BUY_TRAIN)."""

    player_id: PlayerId
    company_id: str
    from_company_id: str
    tier: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        if self.tier not in state.company_trains.get(self.from_company_id, []):
            return Err(
                RuleViolation(
                    rule="5.4",
                    message=f"{self.from_company_id} does not own a tier-{self.tier} train",
                )
            )
        return _require_or_phase(state, ORPhase.BUY_TRAIN)

    def apply(self, state: GameState) -> GameState:
        src_trains = list(state.company_trains.get(self.from_company_id, []))
        src_trains.remove(self.tier)
        dst_trains = state.company_trains.get(self.company_id, []) + [self.tier]
        new_company_trains = {
            **state.company_trains,
            self.from_company_id: src_trains,
            self.company_id: dst_trains,
        }
        return dataclasses.replace(state, company_trains=new_company_trains)


# ===========================================================================
# Special actions
# ===========================================================================


@dataclass(frozen=True)
class OpenPreussen:
    """Open Preußen as a fully nationalised company (special rule)."""

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.4")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class ConvertToPreussenShare:
    """Convert a Vorpreußische share to a 5% Preußen share (rule 2.4)."""

    player_id: PlayerId
    share_id: str

    def validate(self, state: GameState) -> ValidateResult:
        return _require_loop_phase(state, *_ar_phases(), rule="2.4")

    def apply(self, state: GameState) -> GameState:
        return _advance_ar(state, reset_passes=True)


@dataclass(frozen=True)
class ChooseBadenHomeStation:
    """Choose the Baden home station (Mannheim or Ludwigshafen, rule 5.5.2.10)."""

    player_id: PlayerId
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.5.2.10")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.STATION, rule="5.5.2.10")

    def apply(self, state: GameState) -> GameState:
        return dataclasses.replace(state, or_phase=advance_or_phase(ORPhase.STATION))
