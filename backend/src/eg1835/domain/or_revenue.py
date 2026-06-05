"""Train-run revenue for a company (Phase 10).

Bridges the OR flow to the Phase-3 routing engine: a company's station node set
is derived from its home city plus its placed station markers, mapped onto the
route-network station ids by name; the best disjoint route set for its
locomotives then yields the run revenue (rules 5.5.3).

Limitation (documented): the route network is the curated Phase-3 fixture
(`route_network.yml`), not a graph derived from individually placed yellow
tiles -- that needs per-tile edge geometry which the data set does not carry.
Revenue is therefore computed for companies whose cities exist on the fixture
network; others score 0 until tile-geometry data is authored.
"""
from __future__ import annotations

from functools import lru_cache

from .fsm import tier_reaches
from .game_state import GameState
from .loader import GameDataLoader
from .routing import RouteFinder, RouteNetwork


def _normalize(name: str) -> str:
    table = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    out = name.strip().lower()
    for src, dst in table.items():
        out = out.replace(src, dst)
    return out


@lru_cache(maxsize=1)
def _network() -> RouteNetwork:
    return GameDataLoader().load_route_network()


@lru_cache(maxsize=1)
def _field_names() -> dict[str, str]:
    """Board field "q,r" → normalized location name (only network stations)."""
    network = _network()
    board = GameDataLoader().load_board()
    return {
        key: _normalize(pos.location_name)
        for key, pos in board.positions.items()
        if _normalize(pos.location_name) in network.stations
    }


@lru_cache(maxsize=1)
def _home_nodes() -> dict[str, str]:
    """Company id → its home-city network node (where it exists on the fixture)."""
    network = _network()
    homes: dict[str, str] = {}
    for company in GameDataLoader().load_aktiengesellschaften():
        node = _normalize(company.home_city)
        if node in network.stations:
            homes[company.id] = node
    return homes


def company_station_nodes(state: GameState, company_id: str) -> set[str]:
    """Network station ids the company has a marker on (home + placed)."""
    nodes: set[str] = set()
    home = _home_nodes().get(company_id)
    if home is not None:
        nodes.add(home)
    field_names = _field_names()
    for key, companies in state.placed_stations.items():
        if company_id in companies and key in field_names:
            nodes.add(field_names[key])
    return nodes


def company_revenue(state: GameState, company_id: str) -> int:
    """Maximum run revenue for ``company_id`` given its trains and stations."""
    reaches: list[int] = []
    for tier in state.company_trains.get(company_id, []):
        reaches.extend(tier_reaches(tier))
    nodes = company_station_nodes(state, company_id)
    if not reaches or not nodes:
        return 0
    finder = RouteFinder(_network(), state.colored_phase)
    return finder.best_route_set(reaches, token_stations=nodes).total_value
