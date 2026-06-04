"""View projection + legal-action enumeration for the frontend (Phase 9).

The domain ``GameState`` is the source of truth but its shape is optimised for
the rules engine.  This module projects it into the render-friendly view-model
the frontend expects (board / stocks / players / companies) and enumerates the
*concrete* legal actions for the current phase.  No game logic lives here beyond
reading state -- validity is still decided by each action's ``validate``.

Board geometry (placed tiles / stations) is not yet tracked in the domain
(deferred since Phase 3/6), so the board projection renders the static layout
from ``board.yml`` with empty station lists.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from ..domain.fsm import TRAIN_SPECS
from ..domain.game_state import GameState
from ..domain.loader import GameDataLoader
from ..domain.serialization import snake_name
from ..domain.start_packet import START_PACKET_ITEMS, buyable_item_ids

# Player-share certificate denomination (10 % per regular certificate).
_CERT_PERCENT = 10

# Locomotive list price per train id (rule Promotionstabellen) for <TrainPool/>.
TRAIN_PRICE_BY_NAME: dict[str, int] = {
    name: spec.price for name, spec in TRAIN_SPECS.items()
}


@lru_cache(maxsize=1)
def _static_data() -> dict[str, Any]:
    """Load and cache the immutable board / tile / company reference data."""
    loader = GameDataLoader()
    board = loader.load_board()
    tiles = {t.id: t for t in loader.load_tiles()}
    companies = loader.load_aktiengesellschaften()
    return {"board": board, "tiles": tiles, "companies": companies}


def _board_view(state: GameState) -> dict[str, Any]:
    board = _static_data()["board"]
    positions: dict[str, Any] = {}
    for key, pos in board.positions.items():
        positions[key] = {
            "coordinate": {"q": pos.coordinate.q, "r": pos.coordinate.r},
            "tile_id": pos.tile_id,
            "location_name": pos.location_name,
            "stations": [],  # placed-station tracking is deferred
        }
    return {"width": board.width, "height": board.height, "positions": positions}


def _tiles_view() -> dict[str, Any]:
    tiles = _static_data()["tiles"]
    return {
        str(tile.id): {
            "id": tile.id,
            "color": tile.color,
            "name": tile.name,
            "cities": tile.cities,
        }
        for tile in tiles.values()
    }


def _stocks_view(state: GameState) -> dict[str, Any]:
    # Group companies sharing a price field; render order is deterministic
    # (placed-marker stacking is not tracked in the domain yet -- rule 5.3.4).
    order: dict[str, list[str]] = {}
    for company_id, price in sorted(state.share_prices.items()):
        order.setdefault(str(price), []).append(company_id)
    return {
        "share_prices": dict(state.share_prices),
        "share_price_order": order,
        "pool_shares": dict(state.pool_shares),
        "unsold_shares": dict(state.unsold_shares),
    }


def _players_view(state: GameState) -> list[dict[str, Any]]:
    # Reverse the private-ownership map: player → [private ids].
    privates_by_player: dict[str, list[str]] = {}
    for private_id, owner in state.private_owners.items():
        privates_by_player.setdefault(owner, []).append(private_id)

    players: list[dict[str, Any]] = []
    for player_id in state.players:
        players.append(
            {
                "player_id": player_id,
                "cash": state.cash_per_player.get(player_id, 0),
                "shares": dict(state.player_shares.get(player_id, {})),
                "privates": sorted(privates_by_player.get(player_id, [])),
                "paper_count": state.player_certificates.get(player_id, 0),
                "paper_limit": state.certificate_limit(player_id),
                "bankrupt": player_id in state.bankrupt_players,
            }
        )
    return players


def _companies_view(state: GameState) -> list[dict[str, Any]]:
    companies: list[dict[str, Any]] = []
    for company in _static_data()["companies"]:
        cid = company.id
        companies.append(
            {
                "id": cid,
                "name": company.name,
                "status": state.company_status.get(cid, "inactive"),
                "treasury": state.company_cash.get(cid, 0),
                "trains": [{"tier": tier} for tier in state.company_trains.get(cid, [])],
                "stations": [],  # placed-station tracking is deferred
                "share_price": state.share_prices.get(cid, 0),
                "director_id": state.company_directors.get(cid),
            }
        )
    return companies


def build_view(state: GameState, sequence: int) -> dict[str, Any]:
    """Project the domain state into the frontend render view-model."""
    return {
        "sequence": sequence,
        "game_loop_phase": state.game_loop_phase.value,
        "phase": state.game_loop_phase.value,
        "or_phase": state.or_phase.value if state.or_phase is not None else None,
        "colored_phase": state.colored_phase,
        "active_company_id": state.active_company_id,
        "game_over": state.game_over,
        "bank_balance": state.bank_balance,
        "train_prices": dict(TRAIN_PRICE_BY_NAME),
        "available_trains": dict(state.available_trains),
        "board": _board_view(state),
        "tiles": _tiles_view(),
        "stocks": _stocks_view(state),
        "players": _players_view(state),
        "companies": _companies_view(state),
    }


# ---------------------------------------------------------------------------
# Concrete legal-action enumeration
# ---------------------------------------------------------------------------


def _action(action_type: str, **fields: Any) -> dict[str, Any]:
    return {"type": snake_name(action_type), **fields}


def _start_packet_actions(state: GameState) -> list[dict[str, Any]]:
    actions = [
        _action("BuyStartItem", item_id=item_id)
        for item_id in sorted(buyable_item_ids(state.start_packet_rows))
        if item_id in START_PACKET_ITEMS
    ]
    actions.append(_action("Pass"))
    return actions


def _ar_actions(state: GameState, player_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    holdings = state.player_shares.get(player_id, {})
    for company_id, available in sorted(state.unsold_shares.items()):
        if available >= _CERT_PERCENT:
            actions.append(
                _action("BuyShareFromBank", company_id=company_id, percent=_CERT_PERCENT)
            )
    for company_id, pooled in sorted(state.pool_shares.items()):
        if pooled >= _CERT_PERCENT:
            actions.append(
                _action("BuyShareFromPool", company_id=company_id, percent=_CERT_PERCENT)
            )
    for company_id, pct in sorted(holdings.items()):
        if pct >= _CERT_PERCENT:
            actions.append(
                _action("SellShares", company_id=company_id, percent=_CERT_PERCENT)
            )
    actions.append(_action("Pass"))
    return actions


# Action types offered per OR sub-phase (concrete params are filled by the
# client from the board/company selection -- map actions are clicked on HexMap).
_OR_SUBPHASE_TYPES: dict[str, tuple[str, ...]] = {
    "build": ("LayTile", "UpgradeTile", "UseOBAbility", "UsePFBuildAbility", "Pass"),
    "station": (
        "PlaceStation",
        "UseNFAbility",
        "UsePFStationAbility",
        "ChooseBadenHomeStation",
        "Pass",
    ),
    "run": ("RunTrains",),
    "dividend_decision": ("DeclareDividend", "WithholdDividend"),
    "buy_train": (
        "BuyTrainFromBank",
        "BuyTrainFromCompany",
        "BuyMandatoryTrain",
        "Pass",
    ),
    "done": (),
}


def _or_actions(state: GameState) -> list[dict[str, Any]]:
    sub = state.or_phase.value if state.or_phase is not None else "done"
    return [_action(name) for name in _OR_SUBPHASE_TYPES.get(sub, ())]


def legal_actions(state: GameState, player_id: str) -> dict[str, Any]:
    """Concrete legal actions for ``player_id`` in the current phase."""
    loop = state.game_loop_phase.value
    if state.game_over:
        actions: list[dict[str, Any]] = []
    elif loop == "start_packet_ar":
        actions = _start_packet_actions(state)
    elif loop == "ar":
        actions = _ar_actions(state, player_id)
    else:
        actions = _or_actions(state)

    return {
        "player_id": player_id,
        "phase": loop,
        "or_phase": state.or_phase.value if state.or_phase is not None else None,
        "actions": actions,
    }
