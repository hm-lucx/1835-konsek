"""Operating-round flow / turn manager (Phase 10).

The per-action ``apply`` methods only advance their own OR sub-phase.  This
module drives the *cross-company* flow on top of that:

* initialise the operating order when an OR begins (Vorpreußische (1)–(6)
  before AGs, AGs by descending share price — rule 5.3.3/5.3.4),
* hand over to the next company when one finishes its turn (``or_phase == DONE``),
* chain ``ors_per_set`` operating rounds, then start a stock round (rule 5.2),
* trigger the game end at round boundaries (rule 6).

``step`` = ``progress_or(action.apply(state))`` is applied uniformly on both the
write path (submit) and replay, so persisted history and live state never
diverge.  ``progress_or`` is pure and idempotent: it only acts when an OR needs
initialising or the current company is ``DONE``.
"""
from __future__ import annotations

import dataclasses
from typing import Protocol

from .fsm import GameLoopPhase, ORPhase
from .game_end import complete_operating_round, complete_stock_round
from .game_state import GameState

# Vorpreußische operate first, in their printed order (1)–(6) (rule 5.3.3).
_VORPREUSSISCHE_ORDER = ("BM", "BP", "MD", "KM", "BS", "AK")
# Stable tiebreaker order for AGs on equal share price.
_AG_ORDER = ("BY", "SA", "BA", "WÜ", "HE", "MS", "OL", "PR")
_CLOSED = frozenset({"converted", "nationalized"})


class _Applicable(Protocol):
    def apply(self, state: GameState) -> GameState: ...


def step(action: _Applicable, state: GameState) -> GameState:
    """Apply an action, then progress the OR flow (used by submit *and* replay)."""
    return progress_or(action.apply(state))


def _operating_order(state: GameState) -> tuple[str, ...]:
    order: list[str] = []
    for cid in _VORPREUSSISCHE_ORDER:
        if state.company_status.get(cid) in _CLOSED:
            continue
        if any(sh.get(cid, 0) > 0 for sh in state.player_shares.values()):
            order.append(cid)
    launched = [c for c in _AG_ORDER if state.company_status.get(c) == "launched"]
    launched.sort(key=lambda c: (-state.share_prices.get(c, 0), _AG_ORDER.index(c)))
    order.extend(launched)
    return tuple(order)


def _start_company_turn(state: GameState, order: tuple[str, ...], index: int) -> GameState:
    return dataclasses.replace(
        state,
        operating_order=order,
        operating_index=index,
        active_company_id=order[index],
        or_phase=ORPhase.BUILD,
        tiles_laid_this_turn={},
        stations_built_this_turn={},
    )


def _start_stock_round(state: GameState) -> GameState:
    state = complete_stock_round(state)
    return dataclasses.replace(
        state,
        game_loop_phase=GameLoopPhase.AR,
        or_phase=None,
        active_company_id=None,
        operating_order=(),
        operating_index=0,
        ors_completed_in_set=0,
        ar_consecutive_passes=0,
        current_player_index=state.start_player_index,
        companies_operated_this_or=frozenset(),
        ar_sold_companies={p: () for p in state.players},
        companies_launched_this_ar=(),
    )


def _begin_operating_round(state: GameState) -> GameState:
    """Open a fresh OR, or skip straight to an AR if nobody operates."""
    order = _operating_order(state)
    if not order:
        return _start_stock_round(state)
    state = dataclasses.replace(state, companies_operated_this_or=frozenset())
    return _start_company_turn(state, order, 0)


def _finish_operating_round(state: GameState) -> GameState:
    state = complete_operating_round(state)
    if state.game_over:
        return state
    completed = state.ors_completed_in_set + 1
    if completed < state.ors_per_set:
        return _begin_operating_round(
            dataclasses.replace(
                state, ors_completed_in_set=completed, active_company_id=None
            )
        )
    return _start_stock_round(state)


def progress_or(state: GameState) -> GameState:
    """Advance the cross-company OR flow after an action was applied."""
    if state.game_over or state.game_loop_phase != GameLoopPhase.OR:
        return state

    # Just entered an OR (from the start-packet AR or a stock round): set it up.
    if state.active_company_id is None:
        return _begin_operating_round(state)

    # The current company finished its turn → hand over / chain rounds.
    if state.or_phase == ORPhase.DONE:
        operated = state.companies_operated_this_or | {state.active_company_id}
        next_index = state.operating_index + 1
        if next_index < len(state.operating_order):
            return _start_company_turn(
                dataclasses.replace(state, companies_operated_this_or=operated),
                state.operating_order,
                next_index,
            )
        return _finish_operating_round(
            dataclasses.replace(state, companies_operated_this_or=operated)
        )

    return state


def current_actor(state: GameState) -> str | None:
    """The player who is allowed to act next, or None (e.g. game over).

    AR / start-packet: the player at ``current_player_index``.  OR: the director
    of the operating company; for an ownerless Vorpreußische the largest holder.
    """
    if state.game_over:
        return None
    if state.game_loop_phase in (GameLoopPhase.START_PACKET_AR, GameLoopPhase.AR):
        return state.players[state.current_player_index]
    active = state.active_company_id
    if active is None:
        return None
    director = state.company_directors.get(active)
    if director is not None:
        return director
    holders = {
        p: state.player_shares.get(p, {}).get(active, 0) for p in state.players
    }
    best = max(holders.values(), default=0)
    if best <= 0:
        return None
    return next(p for p in state.players if holders[p] == best)
