"""Action framework for 1835 Konsek (Phases 4–7).

Every state mutation goes through an Action: validate first, then apply.
Actions are immutable frozen dataclasses; GameState is never mutated in place.

Phase 6 fills in the operating-round bodies: build limits (5.4.1), station
cost (5.5.2), dividend price moves (5.5.3.12) and the locomotive economy
(5.5.4: limit, director financing, phase changes and Preußen triggers).
Phase 7 adds the special cases: the private-railway abilities (rule 3.1.3, in
``companies.privates.abilities``), Preußen opening (chapter 4), the Baden home
station (5.5.2.10) and the bankruptcy cascade (5.5.4.11–13).

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
    BuyTrainFromBank · BuyTrainFromPool · BuyTrainFromCompany · BuyMandatoryTrain

Special
    OpenPreussen · ConvertToPreussenShare · ChooseBadenHomeStation
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .action_base import (
    PlayerId,
    RuleViolation,
    ValidateResult,
    _ar_phases,
    _require_loop_phase,
    _require_or_phase,
)
from .companies.privates.abilities import (
    ML_FIELD,
    register_built_field,
)
from .companies.privates.abilities import (
    UseNFAbility as UseNFAbility,  # re-exported for the public action API
)
from .companies.privates.abilities import (
    UseOBAbility as UseOBAbility,
)
from .companies.privates.abilities import (
    UsePFBuildAbility as UsePFBuildAbility,
)
from .companies.privates.abilities import (
    UsePFStationAbility as UsePFStationAbility,
)
from .fsm import (
    TRAIN_SPECS,
    GameLoopPhase,
    ORPhase,
    advance_or_phase,
    coloured_phase_trigger,
    ors_for_coloured_phase,
    scrap_train_on_first_purchase,
    tier_to_train_id,
    train_id_to_tier,
    train_limit_for_phase,
)
from .game_end import pay_company_from_bank, pay_player_from_bank
from .game_state import GameState
from .or_revenue import company_revenue
from .result import Err, Ok
from .share_price import step_down, step_up
from .start_packet import (
    START_PACKET_ITEMS,
    buyable_item_ids,
    remove_item,
)


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
        # OR count scheduled by a phase change takes effect now ("ab der
        # nächsten AR") -- rule 5.2.
        new_state = dataclasses.replace(
            new_state, ors_per_set=new_state.pending_ors_per_set
        )
    return new_state


def _apply_train_purchase_effects(state: GameState, train_id: str) -> GameState:
    """Apply every rule-5.5.4.14 / 5.2 consequence of buying ``train_id``.

    Idempotent per train id: a consequence fires only on the *first* purchase of
    that locomotive type (tracked in ``trains_first_bought``).  Effects:

    * ``game_phase`` rises to the train's tier (legacy "highest tier" tracker).
    * First 3-Lok / 5-Lok advances the coloured phase and schedules the new OR
      count for the next AR (rule 5.2).
    * First 4 / 4+4 / 6 / 6+6 scraps all obsolete locomotives (rule 5.5.4.14).
    * First 4-Lok lets Preußen open; first 4+4-Lok forces it (rules 4, 4.6).
    * First 5-Lok converts the remaining Vorpreußische + BS + HA into Preußen
      shares (rules 3.1.3.5, 5.5.4.14).
    """
    tier = train_id_to_tier(train_id)
    is_first = train_id not in state.trains_first_bought

    # game_phase = highest tier ever bought (legacy tracker).
    new_game_phase = max(state.game_phase, tier) if tier is not None else state.game_phase

    new_state = dataclasses.replace(
        state,
        game_phase=new_game_phase,
        trains_first_bought=state.trains_first_bought | {train_id},
    )
    if not is_first:
        return new_state  # consequences only fire on the first copy

    # Scrap obsolete locomotives across every company (rule 5.5.4.14).
    scrap_id = scrap_train_on_first_purchase(train_id)
    if scrap_id is not None:
        scrap_tier = train_id_to_tier(scrap_id)
        new_company_trains = {
            cid: [t for t in trains if t != scrap_tier]
            for cid, trains in new_state.company_trains.items()
        }
        new_state = dataclasses.replace(new_state, company_trains=new_company_trains)

    # Coloured-phase advance + scheduled OR-count change (rule 5.2).
    trigger = coloured_phase_trigger(train_id)
    if trigger is not None and trigger > new_state.colored_phase:
        new_state = dataclasses.replace(
            new_state,
            colored_phase=trigger,
            pending_ors_per_set=ors_for_coloured_phase(trigger),
        )

    # Preußen activation rules (4, 4.6).
    if train_id == "4":
        new_state = dataclasses.replace(new_state, preussen_can_open=True)
    elif train_id == "4+4":
        new_state = dataclasses.replace(
            new_state, preussen_can_open=True, preussen_must_open=True
        )

    # First 5-Lok: forced conversion of remaining pre-Prussians + BS + HA.
    if train_id == "5":
        new_state = _convert_remaining_to_preussen(new_state)

    return new_state


# Companies that must convert into Preußen shares when the first 5-Lok is
# bought: the six Vorpreußische plus the black private railways BS and HA
# (rules 3.1.3.5, 5.5.4.14).  Note: id "BS" denotes both the Vorpreußische
# Berlin-Stettiner and the Braunschweigische private railway in the data set.
_CONVERTS_TO_PREUSSEN = frozenset({"BM", "BP", "MD", "KM", "BS", "AK", "HA"})


def _convert_remaining_to_preussen(state: GameState) -> GameState:
    """Convert every still-active convertible company into Preußen shares.

    Each holder's percentage in a convertible company is moved into Preußen
    ("PR") holdings; the company's status becomes "converted".  Companies that
    were already nationalised/converted are left untouched (rule 4.5: no double
    use).  Marks Preußen as opened.
    """
    new_status = dict(state.company_status)
    new_player_shares = {p: dict(sh) for p, sh in state.player_shares.items()}

    for company_id in _CONVERTS_TO_PREUSSEN:
        status = state.company_status.get(company_id, "inactive")
        if status in ("nationalized", "converted"):
            continue
        converted_any = False
        for shares in new_player_shares.values():
            pct = shares.pop(company_id, 0)
            if pct > 0:
                shares["PR"] = shares.get("PR", 0) + pct
                converted_any = True
        if converted_any or company_id in state.company_status:
            new_status[company_id] = "converted"

    return dataclasses.replace(
        state,
        company_status=new_status,
        player_shares=new_player_shares,
        preussen_opened=True,
    )


# Preußen price-marker start field (rule 4.2).
PREUSSEN_PRICE = 154


def _open_preussen(state: GameState, owner: str) -> GameState:
    """Bring Preußen into operation, owned/directed by ``owner`` (chapter 4).

    Steps (rules 4.1–4.5):

    * Berlin-Potsdamer's treasury and locomotives pass to Preußen (4.2).
    * Operating capital = 154 M per *already-sold* Preußen share + BP treasury
      + the treasuries of the annexed Vorpreußische (4.2, 4.4).
    * Remaining Vorpreußische + BS + HA are converted into Preußen shares and
      their locomotives annexed (4.3, 4.4) – Preußen may exceed the locomotive
      limit on annexation (rule 5.5.4.9).
    * If Berlin-Potsdamer already operated this OR, Preußen pauses this OR
      (double-use protection, rule 4.5).
    """
    # Capital from Preußen shares sold *before* opening (rule 4.2).
    pr_pct_before = sum(sh.get("PR", 0) for sh in state.player_shares.values())
    capital = PREUSSEN_PRICE * (pr_pct_before // 10) + state.company_cash.get("BP", 0)

    # Annex Berlin-Potsdamer's locomotives and empty its treasury (4.2).
    pre = dataclasses.replace(
        state,
        company_trains={
            **state.company_trains,
            "BP": [],
            "PR": list(state.company_trains.get("PR", []))
            + list(state.company_trains.get("BP", [])),
        },
        company_cash={**state.company_cash, "BP": 0},
    )

    # Convert remaining Vorpreußische + BS + HA into Preußen shares (4.3).
    converted = _convert_remaining_to_preussen(pre)

    # Annex treasuries and locomotives of every converted Vorpreußische (4.4).
    final_trains = {cid: list(t) for cid, t in converted.company_trains.items()}
    final_cash = dict(converted.company_cash)
    pr_trains = list(final_trains.get("PR", []))
    for cid in _PREUSSISCHE_COMPANIES:
        if cid == "BP" or converted.company_status.get(cid) != "converted":
            continue
        pr_trains += final_trains.get(cid, [])
        final_trains[cid] = []
        capital += final_cash.get(cid, 0)
        final_cash[cid] = 0
    final_trains["PR"] = pr_trains
    final_cash["PR"] = capital

    return dataclasses.replace(
        converted,
        company_trains=final_trains,
        company_cash=final_cash,
        share_prices={**converted.share_prices, "PR": PREUSSEN_PRICE},
        company_status={**converted.company_status, "PR": "launched"},
        company_directors={**converted.company_directors, "PR": owner},
        preussen_opened=True,
        preussen_must_open=False,
        preussen_paused_this_or="BP" in state.companies_operated_this_or,
    )


def _resolve_train_id(tier: int | None, train: str | None) -> str | None:
    """Resolve a buy-train action's identity to a canonical train id.

    Accepts either the Phase-6 ``train`` id ("4+4", …) or a legacy integer
    ``tier``.  Returns None if neither resolves to a known locomotive.
    """
    if train is not None:
        return train if train in TRAIN_SPECS else None
    if tier is not None:
        return tier_to_train_id(tier)
    return None


def _unknown_loco_err(tier: int | None, train: str | None) -> Err[RuleViolation]:
    """Standard error for an unresolvable buy-train identity (rule 5.5.4)."""
    return Err(RuleViolation("5.5.4", f"Unknown locomotive: tier={tier} train={train}"))


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

    # Capital = par price × shares already in player hands (2.7.5)
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
        bank_balance=state.bank_balance - capital,  # bank pays capital (rule 2.7.5)
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


# ---------------------------------------------------------------------------
# Phase 6 private helpers (OR build / station limits)
# ---------------------------------------------------------------------------


def _max_tiles_this_turn(state: GameState, company_id: str) -> int:
    """Tile-lay limit for a company this turn (rule 5.4.1).

    Vorpreußische: 1.  AGs in coloured phase 1: 2 (yellow).  AGs from phase 2: 1.
    Private-railway special build rights are counted separately and are not
    modelled here.
    """
    if company_id in _PREUSSISCHE_COMPANIES:
        return 1
    return 2 if state.colored_phase == 1 else 1


def _train_limit_reached(state: GameState, company_id: str) -> bool:
    """True if *company_id* is at its locomotive limit (rule 5.5.4.7).

    Uses the *current* coloured-phase limit: a company at the limit may not buy
    even if the new train would trigger a phase change that scraps one of its
    locomotives.
    """
    owned = len(state.company_trains.get(company_id, []))
    return owned >= train_limit_for_phase(state.colored_phase)


def _can_finance_train(state: GameState, company_id: str, price: int) -> bool:
    """True if the company (plus director's private cash) can pay ``price``.

    Rule 5.5.4.11–12: the treasury pays first; for an AG the director must cover
    any shortfall from private cash.  (Selling shares to avoid bankruptcy is
    issue #8 scope, so a shortfall the director cannot cover fails here.)
    """
    company_balance = state.company_cash.get(company_id, 0)
    if company_balance >= price:
        return True
    director = state.company_directors.get(company_id)
    if director is None:
        return False
    return state.cash_per_player.get(director, 0) >= price - company_balance


def _pay_for_train(
    state: GameState, company_id: str, price: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Return updated (company_cash, player_cash) after paying ``price``.

    Director-financed purchases leave the treasury at exactly 0 M (rule
    5.5.4.12).  When no director is registered (test scaffolding), the treasury
    simply pays directly.
    """
    company_balance = state.company_cash.get(company_id, 0)
    new_player_cash = dict(state.cash_per_player)
    director = state.company_directors.get(company_id)
    if company_balance >= price:
        new_balance = company_balance - price
    elif director is not None:
        shortfall = price - company_balance
        new_player_cash[director] = new_player_cash.get(director, 0) - shortfall
        new_balance = 0  # AG keeps no Mark after a director-financed buy
    else:
        new_balance = company_balance - price
    new_company_cash = {**state.company_cash, company_id: new_balance}
    return new_company_cash, new_player_cash


# ---------------------------------------------------------------------------
# Phase 7 – bankruptcy resolution (rules 5.5.4.11–5.5.4.13)
# ---------------------------------------------------------------------------


def _player_order_clockwise_from(state: GameState, index: int) -> list[str]:
    """Players in clockwise (increasing-index) order starting at ``index``."""
    n = len(state.players)
    return [state.players[(index + i) % n] for i in range(n)]


def _successor_director(state: GameState, company_id: str, leaving: str) -> str:
    """Determine the successor director of ``company_id`` (rule 5.5.4.13).

    Most shares wins; on a tie the next player clockwise from the wooden-loco
    (start-player) seat; if nobody holds a share, the start player takes over.
    """
    holders = {
        p: state.player_shares.get(p, {}).get(company_id, 0)
        for p in state.players
        if p != leaving and p not in state.bankrupt_players
    }
    best = max(holders.values(), default=0)
    if best > 0:
        tied = [p for p in state.players if holders.get(p, 0) == best]
        if len(tied) == 1:
            return tied[0]
        for candidate in _player_order_clockwise_from(state, state.start_player_index):
            if candidate in tied:
                return candidate
    return state.players[state.start_player_index]


def _liquidate_director_shares(
    state: GameState, director: str, company_id: str
) -> tuple[GameState, int]:
    """Force-sell the director's shares to the pool (rule 5.5.4.13 step 3).

    Shares of *other* companies are sold in full; shares of the bankrupt
    company only down to the director's certificate (so the post is not lost),
    each capped by the 50 % pool ceiling.  Proceeds are paid by the bank at the
    current share price (no price-stepping during a forced liquidation -- a
    documented simplification).
    """
    holdings = dict(state.player_shares.get(director, {}))
    new_pool = dict(state.pool_shares)
    proceeds = 0
    for cid, pct in list(holdings.items()):
        if cid == "PR":
            continue
        keep = _DIRECTOR_THRESHOLD if cid == company_id else 0
        room = _MAX_POOL_PCT - new_pool.get(cid, 0)
        sellable = max(0, min(pct - keep, room))
        if sellable <= 0:
            continue
        price = state.share_prices.get(cid, 100)
        proceeds += price * (sellable // 10)
        holdings[cid] = pct - sellable
        new_pool[cid] = new_pool.get(cid, 0) + sellable
    new_cash = dict(state.cash_per_player)
    new_cash[director] = new_cash.get(director, 0) + proceeds
    new_state = dataclasses.replace(
        state,
        player_shares={**state.player_shares, director: holdings},
        pool_shares=new_pool,
        cash_per_player=new_cash,
        bank_balance=state.bank_balance - proceeds,
    )
    return new_state, proceeds


def _declare_bankruptcy(
    state: GameState, director: str, company_id: str, shortfall: int
) -> GameState:
    """Resolve a player's bankruptcy (rule 5.5.4.13 step 4).

    The bank finances the remaining ``shortfall`` as company debt (the company
    must save until it is repaid), takes over every remaining share of the
    bankrupt player -- the director certificate goes into the pool -- and a
    successor director is determined.  The player leaves the game.
    """
    holdings = state.player_shares.get(director, {})
    new_pool = dict(state.pool_shares)
    for cid, pct in holdings.items():
        if pct > 0:
            new_pool[cid] = new_pool.get(cid, 0) + pct

    successor = _successor_director(state, company_id, leaving=director)
    new_debt = dict(state.company_debt)
    new_debt[company_id] = new_debt.get(company_id, 0) + shortfall
    return dataclasses.replace(
        state,
        player_shares={**state.player_shares, director: {}},
        pool_shares=new_pool,
        cash_per_player={**state.cash_per_player, director: 0},
        bankrupt_players=state.bankrupt_players | {director},
        company_directors={**state.company_directors, company_id: successor},
        company_debt=new_debt,
    )


def _director_pays(
    state: GameState, director: str, shortfall: int
) -> tuple[GameState, int]:
    """Spend as much of the director's private cash as covers ``shortfall``.

    Returns the updated state and the remaining shortfall.
    """
    have = state.cash_per_player.get(director, 0)
    pay = min(have, shortfall)
    new_state = dataclasses.replace(
        state, cash_per_player={**state.cash_per_player, director: have - pay}
    )
    return new_state, shortfall - pay


def _finance_mandatory_train(state: GameState, company_id: str, price: int) -> GameState:
    """Finance a mandatory locomotive through the full cascade (5.5.4.11–13).

    treasury → director's private cash → forced share sale → bankruptcy.  The
    bank always receives ``price`` for the locomotive; the function returns the
    state after the loco is paid for (placement is done by the caller).
    """
    director = state.company_directors.get(company_id)
    treasury = state.company_cash.get(company_id, 0)
    state = dataclasses.replace(state, bank_balance=state.bank_balance + price)

    # Step 1: treasury (rule 5.5.4.11).
    if treasury >= price or director is None:
        return dataclasses.replace(
            state, company_cash={**state.company_cash, company_id: treasury - price}
        )
    state = dataclasses.replace(state, company_cash={**state.company_cash, company_id: 0})
    shortfall = price - treasury

    # Step 2: director's private cash (rule 5.5.4.12).
    state, shortfall = _director_pays(state, director, shortfall)
    if shortfall <= 0:
        return state

    # Step 3: forced share sale (rule 5.5.4.13).
    state, _ = _liquidate_director_shares(state, director, company_id)
    state, shortfall = _director_pays(state, director, shortfall)
    if shortfall <= 0:
        return state

    # Step 4: bankruptcy (rule 5.5.4.13).
    return _declare_bankruptcy(state, director, company_id, shortfall)


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

        # Record private-railway ownership (rule 3.1) so its special ability can
        # later be used by this player (Phase 7).
        new_private_owners = {**state.private_owners, self.item_id: self.player_id}

        # When the packet empties BY and SA go to the Aktienkurstafel (rule 2.5.2).
        # Par prices from aktiengesellschaften.yml: BY=92 M, SA=88 M.
        packet_empty = all(len(row) == 0 for row in new_rows)
        new_unsold = dict(state.unsold_shares)
        new_prices = dict(state.share_prices)
        new_status = dict(state.company_status)
        if packet_empty:
            for ag, par in (("BY", 92), ("SA", 88)):
                new_unsold[ag] = 100  # all 100% in Nichtverkaufte Aktien
                new_prices[ag] = par
                new_status[ag] = "inactive"

        new_state = dataclasses.replace(
            state,
            cash_per_player=new_cash,
            bank_balance=state.bank_balance + item.cost,
            start_packet_rows=new_rows,
            player_shares=new_player_shares,
            player_certificates=new_certs,
            private_owners=new_private_owners,
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
    """Lay a tile in the build phase (rules 5.4 BUILD, 5.4.1, 5.5.1).

    Enforces the per-turn tile-lay limit (rule 5.4.1).  Stays in BUILD so a
    phase-1 AG can lay its second tile; ``Pass`` advances BUILD → STATION.
    Board geometry is deferred to the Phase 2/3 board integration.

    An optional ``field_id`` names a tracked special field (e.g. an OB field or
    Mannheim/Ludwigshafen); laying there registers the field so that, for
    instance, a foreign build on OB's second field closes the Ostbayern
    (rule 3.1.3.2).
    """

    player_id: PlayerId
    tile_id: int
    q: int
    r: int
    field_id: str | None = None

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUILD, rule="5.5.1")
        if isinstance(result, Err):
            return result
        company_id = state.active_company_id
        if company_id is None:
            return Err(RuleViolation("5.4", "No active company in OR turn"))
        laid = state.tiles_laid_this_turn.get(company_id, 0)
        if laid >= _max_tiles_this_turn(state, company_id):
            return Err(
                RuleViolation(
                    "5.4.1",
                    f"{company_id} already laid {laid} tile(s) this turn",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        company_id = state.active_company_id
        assert company_id is not None
        new_counts = {
            **state.tiles_laid_this_turn,
            company_id: state.tiles_laid_this_turn.get(company_id, 0) + 1,
        }
        new_state = dataclasses.replace(
            state,
            tiles_laid_this_turn=new_counts,
            placed_tiles={**state.placed_tiles, f"{self.q},{self.r}": self.tile_id},
        )
        if self.field_id is not None:
            new_state = register_built_field(new_state, self.field_id)
        return new_state


@dataclass(frozen=True)
class UpgradeTile:
    """Upgrade an existing tile in the build phase (rule 5.5.1.14).

    Counts against the same per-turn build limit as ``LayTile`` (rule 5.4.1).
    """

    player_id: PlayerId
    tile_id: int
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUILD, rule="5.5.1.14")
        if isinstance(result, Err):
            return result
        company_id = state.active_company_id
        if company_id is None:
            return Err(RuleViolation("5.4", "No active company in OR turn"))
        laid = state.tiles_laid_this_turn.get(company_id, 0)
        if laid >= _max_tiles_this_turn(state, company_id):
            return Err(
                RuleViolation(
                    "5.4.1",
                    f"{company_id} already laid {laid} tile(s) this turn",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        company_id = state.active_company_id
        assert company_id is not None
        new_counts = {
            **state.tiles_laid_this_turn,
            company_id: state.tiles_laid_this_turn.get(company_id, 0) + 1,
        }
        return dataclasses.replace(
            state,
            tiles_laid_this_turn=new_counts,
            placed_tiles={**state.placed_tiles, f"{self.q},{self.r}": self.tile_id},
        )


# Private-railway build abilities (NF, OB, PF-build) live in
# ``companies.privates.abilities`` and are re-exported via the import at the top
# of this module.


# ===========================================================================
# OR – Station phase
# ===========================================================================


@dataclass(frozen=True)
class PlaceStation:
    """Place an additional company station token (rules 5.4 STATION, 5.5.2).

    Cost = 20 M × ``distance`` (field distance to the home station; the home
    station itself is free and placed at launch).  At most one station per OR
    turn (rule 5.5.2).  Vorpreußische companies may only ever hold their home
    station, so an additional station is rejected for them.  The field
    distance is supplied by the caller (board-distance routing is Phase 3+).
    """

    player_id: PlayerId
    company_id: str
    q: int
    r: int
    distance: int = 0  # field distance to home; 20 M per field (rule 5.5.2)

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.STATION, rule="5.5.2")
        if isinstance(result, Err):
            return result
        if self.company_id in _PREUSSISCHE_COMPANIES:
            return Err(
                RuleViolation(
                    "5.5.2",
                    f"{self.company_id} is Vorpreußische – only a home station allowed",
                )
            )
        if state.stations_built_this_turn.get(self.company_id, 0) >= 1:
            return Err(
                RuleViolation("5.5.2", f"{self.company_id} already built a station this turn")
            )
        cost = 20 * self.distance
        if state.company_cash.get(self.company_id, 0) < cost:
            return Err(
                RuleViolation(
                    "5.5.2",
                    f"{self.company_id} cannot afford station "
                    f"(needs {cost} M for {self.distance} fields)",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        cost = 20 * self.distance
        new_company_cash = {
            **state.company_cash,
            self.company_id: state.company_cash.get(self.company_id, 0) - cost,
        }
        new_counts = {
            **state.stations_built_this_turn,
            self.company_id: state.stations_built_this_turn.get(self.company_id, 0) + 1,
        }
        key = f"{self.q},{self.r}"
        existing = state.placed_stations.get(key, ())
        new_stations = {**state.placed_stations, key: (*existing, self.company_id)}
        return dataclasses.replace(
            state,
            company_cash=new_company_cash,
            stations_built_this_turn=new_counts,
            placed_stations=new_stations,
            or_phase=advance_or_phase(ORPhase.STATION),
        )


# The Pfalzbahn station ability (UsePFStationAbility) lives in
# ``companies.privates.abilities`` and is re-exported via the top-of-module import.


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
    route_values: list[int] = dataclasses.field(default_factory=list)  # legacy override

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.RUN, rule="5.5.3")

    def apply(self, state: GameState) -> GameState:
        # Revenue is computed from the company's stations + trains via the
        # routing engine (rule 5.5.3); ``route_values`` is only a legacy fallback
        # when the network does not yet cover the company's cities.
        computed = company_revenue(state, self.company_id)
        revenue = computed if computed > 0 else sum(self.route_values)
        return dataclasses.replace(
            state,
            last_run_revenue={**state.last_run_revenue, self.company_id: revenue},
            or_phase=advance_or_phase(ORPhase.RUN),
        )


@dataclass(frozen=True)
class DeclareDividend:
    """Pay out the full revenue to shareholders (rules 5.5.3.11.5, 5.5.3.12).

    Each player receives ``amount`` × their holding; the remainder (pool /
    unsold shares / rounding) stays in the company treasury.  The share price
    then moves **one field up** (rule 5.5.3.12).  Transitions
    DIVIDEND_DECISION → BUY_TRAIN.
    """

    player_id: PlayerId
    company_id: str
    amount: int = 0  # 0 → use the revenue computed by RunTrains

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")
        if isinstance(result, Err):
            return result
        # A company that owes the bank must save until the debt is repaid (5.5.4.13).
        if state.company_debt.get(self.company_id, 0) > 0:
            return Err(
                RuleViolation(
                    "5.5.4.13",
                    f"{self.company_id} must save until its bank debt is repaid",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        revenue = self.amount if self.amount > 0 else state.last_run_revenue.get(
            self.company_id, 0
        )
        # Dividends are paid by the bank to each shareholder (rule 5.5.3.11);
        # draining the bank schedules the game end (rule 6.1).
        new_state = state
        distributed = 0
        for player, shares in state.player_shares.items():
            pct = shares.get(self.company_id, 0)
            if pct > 0:
                share_amount = revenue * pct // 100
                new_state = pay_player_from_bank(new_state, player, share_amount)
                distributed += share_amount

        # The portion for pool / unsold / company-held shares goes to the treasury.
        new_state = pay_company_from_bank(new_state, self.company_id, revenue - distributed)

        # Payout moves the price one field up (rule 5.5.3.12).
        new_prices = dict(new_state.share_prices)
        if self.company_id in new_prices:
            new_prices[self.company_id] = step_up(new_prices[self.company_id])

        return dataclasses.replace(
            new_state,
            share_prices=new_prices,
            or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION),
        )


@dataclass(frozen=True)
class WithholdDividend:
    """Retain all revenue in the company treasury (rules 5.5.3.11.5, 5.5.3.12).

    The full ``amount`` is added to the treasury and the share price moves
    **one field down** (rule 5.5.3.12).  Transitions DIVIDEND_DECISION →
    BUY_TRAIN.
    """

    player_id: PlayerId
    company_id: str
    amount: int = 0

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        return _require_or_phase(state, ORPhase.DIVIDEND_DECISION, rule="5.5.3.11.5")

    def apply(self, state: GameState) -> GameState:
        revenue = self.amount if self.amount > 0 else state.last_run_revenue.get(
            self.company_id, 0
        )
        # Saved revenue first repays any outstanding bank debt (rule 5.5.4.13);
        # the rest is paid by the bank into the treasury.
        debt = state.company_debt.get(self.company_id, 0)
        repaid = min(debt, revenue)
        new_state = dataclasses.replace(
            state, company_debt={**state.company_debt, self.company_id: debt - repaid}
        )
        new_state = pay_company_from_bank(new_state, self.company_id, revenue - repaid)

        # Saving moves the price one field down (rule 5.5.3.12).
        new_prices = dict(new_state.share_prices)
        if self.company_id in new_prices:
            new_prices[self.company_id] = step_down(new_prices[self.company_id])

        return dataclasses.replace(
            new_state,
            share_prices=new_prices,
            or_phase=advance_or_phase(ORPhase.DIVIDEND_DECISION),
        )


# ===========================================================================
# OR – Train-purchase phase
# ===========================================================================


@dataclass(frozen=True)
class BuyTrainFromBank:
    """Buy a locomotive from the bank (rules 5.4 BUY_TRAIN, 5.5.4).

    Identity is the canonical ``train`` id ("2", "4+4", …); a legacy integer
    ``tier`` is also accepted (Phase-4 compatibility).  Enforces the locomotive
    limit (5.5.4.7) and director financing (5.5.4.11–12), then applies every
    phase-change consequence (5.2, 5.5.4.14) via ``_apply_train_purchase_effects``.
    """

    player_id: PlayerId
    company_id: str
    tier: int | None = None
    train: str | None = None

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.5.4")
        if isinstance(result, Err):
            return result
        train_id = _resolve_train_id(self.tier, self.train)
        if train_id is None:
            return _unknown_loco_err(self.tier, self.train)
        tier = train_id_to_tier(train_id)
        if state.available_trains.get(tier, 0) <= 0:  # type: ignore[arg-type]
            return Err(RuleViolation("5.5.4", f"No {train_id}-Lok left in the bank"))
        if _train_limit_reached(state, self.company_id):
            limit = train_limit_for_phase(state.colored_phase)
            return Err(
                RuleViolation(
                    "5.5.4.7",
                    f"{self.company_id} is at its locomotive limit "
                    f"({limit} in phase {state.colored_phase})",
                )
            )
        price = TRAIN_SPECS[train_id].price
        if not _can_finance_train(state, self.company_id, price):
            return Err(
                RuleViolation(
                    "5.5.4.12",
                    f"{self.company_id} cannot finance {train_id}-Lok ({price} M) "
                    "even with director's private cash",
                )
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        train_id = _resolve_train_id(self.tier, self.train)
        assert train_id is not None
        tier = train_id_to_tier(train_id)
        assert tier is not None
        price = TRAIN_SPECS[train_id].price

        new_company_cash, new_player_cash = _pay_for_train(state, self.company_id, price)
        new_available = {
            **state.available_trains,
            tier: state.available_trains.get(tier, 0) - 1,
        }
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [tier],
        }
        new_state = dataclasses.replace(
            state,
            available_trains=new_available,
            company_cash=new_company_cash,
            cash_per_player=new_player_cash,
            company_trains=new_company_trains,
            bank_balance=state.bank_balance + price,
        )
        # Phase-change consequences run *after* the train is placed.
        return _apply_train_purchase_effects(new_state, train_id)


@dataclass(frozen=True)
class BuyTrainFromPool:
    """Buy a scrapped locomotive from the bank pool at its printed price.

    Available from the moment a locomotive is scrapped (rule 5.5.4.8).  Subject
    to the same limit / financing rules as a bank purchase.  Pool inventory
    accounting is deferred to the persistence layer (issue #9).
    """

    player_id: PlayerId
    company_id: str
    tier: int | None = None
    train: str | None = None

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.5.4")
        if isinstance(result, Err):
            return result
        train_id = _resolve_train_id(self.tier, self.train)
        if train_id is None:
            return _unknown_loco_err(self.tier, self.train)
        if _train_limit_reached(state, self.company_id):
            return Err(RuleViolation("5.5.4.7", f"{self.company_id} is at its locomotive limit"))
        price = TRAIN_SPECS[train_id].price
        if not _can_finance_train(state, self.company_id, price):
            return Err(
                RuleViolation("5.5.4.12", f"{self.company_id} cannot finance {train_id}-Lok")
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        train_id = _resolve_train_id(self.tier, self.train)
        assert train_id is not None
        tier = train_id_to_tier(train_id)
        assert tier is not None
        price = TRAIN_SPECS[train_id].price

        new_company_cash, new_player_cash = _pay_for_train(state, self.company_id, price)
        new_company_trains = {
            **state.company_trains,
            self.company_id: state.company_trains.get(self.company_id, []) + [tier],
        }
        new_state = dataclasses.replace(
            state,
            company_cash=new_company_cash,
            cash_per_player=new_player_cash,
            company_trains=new_company_trains,
            bank_balance=state.bank_balance + price,
        )
        return _apply_train_purchase_effects(new_state, train_id)


@dataclass(frozen=True)
class BuyTrainFromCompany:
    """Buy a locomotive directly from another company (rule 5.5.4.3).

    Only allowed from coloured phase 2 onward; the price is freely negotiable
    and transferred from the buyer's to the seller's treasury.
    """

    player_id: PlayerId
    company_id: str
    from_company_id: str
    tier: int | None = None
    train: str | None = None
    price: int = 0  # negotiated price (rule 5.5.4.3)

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.5.4")
        if isinstance(result, Err):
            return result
        if state.colored_phase < 2:
            return Err(
                RuleViolation(
                    "5.5.4.3",
                    "Buying locomotives between companies is allowed from phase 2 only",
                )
            )
        train_id = _resolve_train_id(self.tier, self.train)
        if train_id is None:
            return _unknown_loco_err(self.tier, self.train)
        tier = train_id_to_tier(train_id)
        if tier not in state.company_trains.get(self.from_company_id, []):
            return Err(
                RuleViolation(
                    "5.5.4.3",
                    f"{self.from_company_id} does not own a {train_id}-Lok",
                )
            )
        if _train_limit_reached(state, self.company_id):
            return Err(RuleViolation("5.5.4.7", f"{self.company_id} is at its locomotive limit"))
        if state.company_cash.get(self.company_id, 0) < self.price:
            return Err(
                RuleViolation("5.5.4.3", f"{self.company_id} cannot afford {self.price} M")
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        train_id = _resolve_train_id(self.tier, self.train)
        assert train_id is not None
        tier = train_id_to_tier(train_id)
        assert tier is not None

        src_trains = list(state.company_trains.get(self.from_company_id, []))
        src_trains.remove(tier)
        dst_trains = state.company_trains.get(self.company_id, []) + [tier]
        new_company_trains = {
            **state.company_trains,
            self.from_company_id: src_trains,
            self.company_id: dst_trains,
        }
        # Price moves between the two treasuries (rule 5.5.4.3).
        new_company_cash = {
            **state.company_cash,
            self.company_id: state.company_cash.get(self.company_id, 0) - self.price,
            self.from_company_id: state.company_cash.get(self.from_company_id, 0) + self.price,
        }
        new_state = dataclasses.replace(
            state,
            company_trains=new_company_trains,
            company_cash=new_company_cash,
        )
        return _apply_train_purchase_effects(new_state, train_id)


@dataclass(frozen=True)
class BuyMandatoryTrain:
    """Buy the compulsory locomotive a company owes at the end of its turn.

    Unlike ``BuyTrainFromBank`` this never fails for lack of funds: it runs the
    full financing cascade (rules 5.5.4.11–13) treasury → director's private
    cash → forced share sale → bankruptcy.  The locomotive is always acquired.
    """

    player_id: PlayerId
    company_id: str
    tier: int | None = None
    train: str | None = None

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.5.4")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.BUY_TRAIN, rule="5.5.4")
        if isinstance(result, Err):
            return result
        train_id = _resolve_train_id(self.tier, self.train)
        if train_id is None:
            return _unknown_loco_err(self.tier, self.train)
        tier = train_id_to_tier(train_id)
        if state.available_trains.get(tier, 0) <= 0:  # type: ignore[arg-type]
            return Err(RuleViolation("5.5.4", f"No {train_id}-Lok left in the bank"))
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        train_id = _resolve_train_id(self.tier, self.train)
        assert train_id is not None
        tier = train_id_to_tier(train_id)
        assert tier is not None
        price = TRAIN_SPECS[train_id].price

        # Finance through the full cascade (may end in bankruptcy).
        new_state = _finance_mandatory_train(state, self.company_id, price)
        # Place the locomotive and remove it from the bank stock.
        new_state = dataclasses.replace(
            new_state,
            available_trains={
                **new_state.available_trains,
                tier: new_state.available_trains.get(tier, 0) - 1,
            },
            company_trains={
                **new_state.company_trains,
                self.company_id: new_state.company_trains.get(self.company_id, []) + [tier],
            },
        )
        return _apply_train_purchase_effects(new_state, train_id)


# ===========================================================================
# Special actions
# ===========================================================================


@dataclass(frozen=True)
class OpenPreussen:
    """Berlin-Potsdamer's owner brings Preußen into operation (chapter 4).

    Allowed once at least one 4-Lok has been bought (``preussen_can_open``) and
    mandatory once a 4+4-Lok has been bought (``preussen_must_open``, rule 4.6).
    """

    player_id: PlayerId

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(
            state, GameLoopPhase.OR, GameLoopPhase.AR, rule="4.1"
        )
        if isinstance(result, Err):
            return result
        if state.preussen_opened:
            return Err(RuleViolation("4.1", "Preußen is already in operation"))
        if not (state.preussen_can_open or state.preussen_must_open):
            return Err(
                RuleViolation("4.6", "Preußen may open only after the first 4-Lok")
            )
        if state.player_shares.get(self.player_id, {}).get("BP", 0) <= 0:
            return Err(
                RuleViolation("4.1", f"{self.player_id} does not own Berlin-Potsdamer")
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        return _open_preussen(state, self.player_id)


@dataclass(frozen=True)
class ConvertToPreussenShare:
    """Voluntarily convert one holding into a Preußen share (rules 4.3, 4.7).

    ``share_id`` is the convertible company id (a Vorpreußische, or BS / HA).
    """

    player_id: PlayerId
    share_id: str

    def validate(self, state: GameState) -> ValidateResult:
        if not state.preussen_opened:
            return Err(RuleViolation("4.7", "Preußen is not in operation yet"))
        if self.share_id not in _CONVERTS_TO_PREUSSEN:
            return Err(
                RuleViolation("4.3", f"{self.share_id} is not convertible to Preußen")
            )
        if state.player_shares.get(self.player_id, {}).get(self.share_id, 0) <= 0:
            return Err(
                RuleViolation("4.3", f"{self.player_id} holds no {self.share_id}")
            )
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        shares = dict(state.player_shares.get(self.player_id, {}))
        pct = shares.pop(self.share_id, 0)
        shares["PR"] = shares.get("PR", 0) + pct
        return dataclasses.replace(
            state,
            player_shares={**state.player_shares, self.player_id: shares},
            company_status={**state.company_status, self.share_id: "converted"},
        )


@dataclass(frozen=True)
class ChooseBadenHomeStation:
    """Place Baden's home station in Mannheim or Ludwigshafen (rule 5.5.2.10).

    Possible only once M/L has been built; until Baden makes this choice no
    other company may build in the field (enforced in the private abilities).
    """

    player_id: PlayerId
    q: int
    r: int

    def validate(self, state: GameState) -> ValidateResult:
        result = _require_loop_phase(state, GameLoopPhase.OR, rule="5.5.2.10")
        if isinstance(result, Err):
            return result
        result = _require_or_phase(state, ORPhase.STATION, rule="5.5.2.10")
        if isinstance(result, Err):
            return result
        if state.active_company_id != "BA" or state.company_directors.get("BA") != self.player_id:
            return Err(
                RuleViolation("5.5.2.10", "Only Baden's director may choose its home")
            )
        if ML_FIELD not in state.built_fields:
            return Err(RuleViolation("5.5.2.10", "Mannheim/Ludwigshafen is not built yet"))
        if state.baden_home_chosen:
            return Err(RuleViolation("5.5.2.10", "Baden's home station is already placed"))
        return Ok(None)

    def apply(self, state: GameState) -> GameState:
        key = f"{self.q},{self.r}"
        existing = state.placed_stations.get(key, ())
        return dataclasses.replace(
            state,
            baden_home_chosen=True,
            home_fields={**state.home_fields, "BA": key},
            placed_stations={**state.placed_stations, key: (*existing, "BA")},
        )
