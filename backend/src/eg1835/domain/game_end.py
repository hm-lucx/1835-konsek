"""End-of-game logic (rule 6).

The bank running dry triggers the end, but *when* the game actually finishes
depends on the round in which it happened (rule 6.1):

* bank empty during an **OR**  → finish the running operating round, then end.
* bank empty during an **AR**  → finish the stock round *and one more* OR.

Amounts the bank can no longer pay are *noted* (``bank_owed``) and credited to
the player at the final settlement (rule 6.1).  The settlement counts cash plus
the current share value of every holding; company assets (locos, treasury) do
**not** count (rule 6.2).
"""
from __future__ import annotations

import dataclasses

from .game_state import GameState


def bank_is_empty(state: GameState) -> bool:
    """True once the bank has no money left (rule 6.1)."""
    return state.bank_balance <= 0


def schedule_end(state: GameState) -> GameState:
    """Mark the end as pending and schedule the remaining rounds (rule 6.1).

    From an OR the current operating round still finishes; from an AR the stock
    round finishes and one further operating round is played.  In both cases one
    operating-round completion remains before the game is over.
    """
    if state.end_pending or state.game_over:
        return state
    return dataclasses.replace(state, end_pending=True, pending_final_ors=1)


def pay_player_from_bank(state: GameState, player: str, amount: int) -> GameState:
    """Pay ``amount`` to ``player`` from the bank (rule 6.1).

    Whatever the bank cannot cover is noted in ``bank_owed`` and credited at the
    final settlement.  Draining the bank schedules the end of the game.
    """
    if amount <= 0:
        return state
    payable = max(0, min(amount, state.bank_balance))
    shortfall = amount - payable

    new_cash = {**state.cash_per_player, player: state.cash_per_player.get(player, 0) + payable}
    new_owed = dict(state.bank_owed)
    if shortfall > 0:
        new_owed[player] = new_owed.get(player, 0) + shortfall

    new_state = dataclasses.replace(
        state,
        bank_balance=state.bank_balance - payable,
        cash_per_player=new_cash,
        bank_owed=new_owed,
    )
    if bank_is_empty(new_state):
        new_state = schedule_end(new_state)
    return new_state


def complete_operating_round(state: GameState) -> GameState:
    """Register that one operating round finished; end the game if it was last."""
    if not state.end_pending or state.game_over:
        return state
    remaining = state.pending_final_ors - 1
    if remaining <= 0:
        return dataclasses.replace(state, pending_final_ors=0, game_over=True)
    return dataclasses.replace(state, pending_final_ors=remaining)


def complete_stock_round(state: GameState) -> GameState:
    """Register that a stock round finished.

    A stock round never ends the game directly: even when the end is pending the
    extra operating round (rule 6.1) must still be played afterwards.
    """
    return state


def share_value(state: GameState, player: str) -> int:
    """Current market value of all of ``player``'s shares (rule 6.2.2)."""
    total = 0
    for company_id, pct in state.player_shares.get(player, {}).items():
        price = state.share_prices.get(company_id)
        if price is not None:
            total += price * (pct // 10)
    return total


def final_scores(state: GameState) -> dict[str, int]:
    """Final net worth per player (rule 6.2): cash + owed + share value.

    Company assets (locomotives, treasury) are excluded.  Bankrupt players score
    nothing.
    """
    scores: dict[str, int] = {}
    for player in state.players:
        if player in state.bankrupt_players:
            scores[player] = 0
            continue
        scores[player] = (
            state.cash_per_player.get(player, 0)
            + state.bank_owed.get(player, 0)
            + share_value(state, player)
        )
    return scores
