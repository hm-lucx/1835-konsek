"""Route finding for 1835 (Phase 3).

Implements the routing constraints of the 1835 rulebook, rules 5.5.3.1 - 5.5.3.10:

* 5.5.3.2  A route must connect at least two distinct stations.
* 5.5.3.3  A station of the operating company must lie on the route.
* 5.5.3.4  The number of stations on a route may not exceed the locomotive reach.
* 5.5.3.5  No station may be used twice; the two halves of a double city count
           separately (modelled as two distinct station nodes).
* 5.5.3.6  A route may *end* at a blocked station but may not pass *through* it.
* 5.5.3.8  No track segment (edge) may be used twice -- not within one route and
           not across the routes of several locomotives of the same company.
* 5.5.3.10 Several locomotives run fully separate routes. A branch (junction)
           without a station may be used by at most one locomotive.

Revenue handling (rule 5.5.3.11) lives in :mod:`eg1835.domain.revenue`.

The graph is intentionally vertex-simple: a route never visits the same node
twice. This automatically satisfies 5.5.3.5 and 5.5.3.8 within a single route
and is a faithful model of 1835 play for the situations covered by Phase 3.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field


@dataclass
class Station:
    """A revenue location (city, town, double-city half or off-board area).

    ``revenue`` maps the game phase (1-3) to the value scored when the station
    is part of a route. ``ferry_revenue`` is an alternative table used when the
    route reaches the station across a ferry edge (rule 5.5.3.11.3, e.g. the
    brown Hamburg off-board: 50 without / 60 with ferry).
    """

    id: str
    name: str
    revenue: Mapping[int, int]
    is_offboard: bool = False
    blocked: bool = False
    available_from_phase: int = 1
    ferry_revenue: Mapping[int, int] | None = None

    def is_available(self, phase: int) -> bool:
        """Whether the station may be visited in the given phase (5.5.3.11.3).

        Off-board connections such as Elsaß-Lothringen only open up from a
        certain phase onwards.
        """
        return phase >= self.available_from_phase

    def value(self, phase: int, ferry_used: bool) -> int:
        """Revenue contribution of this station in ``phase``."""
        if ferry_used and self.ferry_revenue is not None:
            ferry_value = self.ferry_revenue.get(phase)
            if ferry_value is not None:
                return ferry_value
        return self.revenue.get(phase, 0)


@dataclass
class Edge:
    """A track segment connecting two nodes. ``id`` is unique (5.5.3.8)."""

    id: str
    a: str
    b: str
    ferry: bool = False


@dataclass(frozen=True)
class Route:
    """A single locomotive's run through the network."""

    nodes: tuple[str, ...]
    edges: tuple[str, ...]
    stations: tuple[str, ...]
    junctions: frozenset[str]
    value: int

    @property
    def edge_set(self) -> frozenset[str]:
        """The set of track segments occupied by this route."""
        return frozenset(self.edges)


# A route that scores nothing -- used so a locomotive may run empty when no
# disjoint route is available for it (rule 5.5.3.10).
EMPTY_ROUTE = Route(nodes=(), edges=(), stations=(), junctions=frozenset(), value=0)


@dataclass
class RouteSet:
    """The optimal combination of routes for a company's locomotives."""

    routes: list[Route]
    total_value: int


class RouteNetwork:
    """Adjacency graph of stations, junctions and track segments."""

    def __init__(self) -> None:
        self.stations: dict[str, Station] = {}
        self.junctions: dict[str, str] = {}
        self.edges: dict[str, Edge] = {}
        self._adjacency: dict[str, list[tuple[str, str]]] = {}

    # --- construction -----------------------------------------------------

    def add_station(self, station: Station) -> None:
        self.stations[station.id] = station
        self._adjacency.setdefault(station.id, [])

    def add_junction(self, junction_id: str, name: str = "") -> None:
        self.junctions[junction_id] = name
        self._adjacency.setdefault(junction_id, [])

    def add_edge(self, edge: Edge) -> None:
        if edge.a not in self._adjacency or edge.b not in self._adjacency:
            raise ValueError(f"Edge {edge.id} references an unknown node")
        if edge.id in self.edges:
            raise ValueError(f"Duplicate edge id {edge.id}")
        self.edges[edge.id] = edge
        self._adjacency[edge.a].append((edge.id, edge.b))
        self._adjacency[edge.b].append((edge.id, edge.a))

    # --- queries ----------------------------------------------------------

    def is_station(self, node_id: str) -> bool:
        return node_id in self.stations

    def neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """Return ``(edge_id, neighbor_id)`` pairs adjacent to ``node_id``."""
        return self._adjacency.get(node_id, [])


class RouteFinder:
    """Enumerates legal routes and picks the maximum-revenue combination.

    Rule 5.5.3.11.2 forbids deliberately scoring less than the maximum, so the
    finder always returns the optimal route set.
    """

    def __init__(self, network: RouteNetwork, phase: int) -> None:
        self.network = network
        self.phase = phase

    # --- single locomotive ------------------------------------------------

    def routes_for_train(
        self, reach: int, token_stations: Iterable[str] | None = None
    ) -> list[Route]:
        """All legal routes for a locomotive with the given ``reach``.

        ``token_stations`` are the stations carrying the operating company's
        station marker; if given, every route must include at least one of them
        (rule 5.5.3.3). ``None`` disables the check.
        """
        tokens = set(token_stations) if token_stations is not None else None
        routes: dict[frozenset[str], Route] = {}

        for start in self.network.stations:
            station = self.network.stations[start]
            if not station.is_available(self.phase):
                continue
            self._dfs(
                node=start,
                reach=reach,
                tokens=tokens,
                visited={start},
                path_nodes=[start],
                path_edges=[],
                station_count=1,
                routes=routes,
            )
        return list(routes.values())

    def _dfs(
        self,
        node: str,
        reach: int,
        tokens: set[str] | None,
        visited: set[str],
        path_nodes: list[str],
        path_edges: list[str],
        station_count: int,
        routes: dict[frozenset[str], Route],
    ) -> None:
        is_station = self.network.is_station(node)

        if is_station and station_count >= 2:
            self._record(path_nodes, path_edges, tokens, routes)

        # A blocked station can only be an endpoint: never expand through it
        # (5.5.3.6). The reach caps the number of stations on the route
        # (5.5.3.4).
        if is_station and self.network.stations[node].blocked:
            return
        if station_count >= reach:
            return

        for edge_id, neighbor in self.network.neighbors(node):
            if edge_id in path_edges or neighbor in visited:
                continue
            neighbor_is_station = self.network.is_station(neighbor)
            if neighbor_is_station and not self.network.stations[neighbor].is_available(
                self.phase
            ):
                continue

            visited.add(neighbor)
            path_nodes.append(neighbor)
            path_edges.append(edge_id)
            self._dfs(
                node=neighbor,
                reach=reach,
                tokens=tokens,
                visited=visited,
                path_nodes=path_nodes,
                path_edges=path_edges,
                station_count=station_count + (1 if neighbor_is_station else 0),
                routes=routes,
            )
            path_edges.pop()
            path_nodes.pop()
            visited.remove(neighbor)

    def _record(
        self,
        path_nodes: list[str],
        path_edges: list[str],
        tokens: set[str] | None,
        routes: dict[frozenset[str], Route],
    ) -> None:
        stations = tuple(n for n in path_nodes if self.network.is_station(n))
        if tokens is not None and not (set(stations) & tokens):
            return
        key = frozenset(path_edges)
        if key in routes:
            return
        junctions = frozenset(n for n in path_nodes if not self.network.is_station(n))
        value = self._value(path_nodes, path_edges)
        routes[key] = Route(
            nodes=tuple(path_nodes),
            edges=tuple(path_edges),
            stations=stations,
            junctions=junctions,
            value=value,
        )

    def _value(self, path_nodes: list[str], path_edges: list[str]) -> int:
        total = 0
        for i, node in enumerate(path_nodes):
            if not self.network.is_station(node):
                continue
            incident: list[str] = []
            if i > 0:
                incident.append(path_edges[i - 1])
            if i < len(path_edges):
                incident.append(path_edges[i])
            ferry_used = any(self.network.edges[e].ferry for e in incident)
            total += self.network.stations[node].value(self.phase, ferry_used)
        return total

    # --- several locomotives ---------------------------------------------

    def best_route_set(
        self, train_reaches: list[int], token_stations: Iterable[str] | None = None
    ) -> RouteSet:
        """Maximum-revenue disjoint route assignment for several locomotives.

        Routes must be pairwise edge-disjoint (5.5.3.8) and junction-disjoint
        (5.5.3.10); they may share stations. A 6+6 locomotive is passed as two
        reaches ``[6, 6]``.
        """
        tokens = set(token_stations) if token_stations is not None else None
        candidates: list[list[Route]] = []
        for reach in train_reaches:
            options = self.routes_for_train(reach, tokens)
            options.append(EMPTY_ROUTE)
            options.sort(key=lambda r: r.value, reverse=True)
            candidates.append(options)

        # Optimistic suffix bound: best obtainable value from train i onwards
        # ignoring disjointness, used to prune the search.
        suffix_best = [0] * (len(candidates) + 1)
        for i in range(len(candidates) - 1, -1, -1):
            suffix_best[i] = suffix_best[i + 1] + candidates[i][0].value

        best = _SearchResult(value=0, routes=[EMPTY_ROUTE] * len(candidates))
        self._search(
            index=0,
            candidates=candidates,
            used_edges=set(),
            used_junctions=set(),
            chosen=[],
            current_value=0,
            suffix_best=suffix_best,
            best=best,
        )
        return RouteSet(routes=list(best.routes), total_value=best.value)

    def _search(
        self,
        index: int,
        candidates: list[list[Route]],
        used_edges: set[str],
        used_junctions: set[str],
        chosen: list[Route],
        current_value: int,
        suffix_best: list[int],
        best: _SearchResult,
    ) -> None:
        if current_value + suffix_best[index] <= best.value:
            return
        if index == len(candidates):
            if current_value > best.value:
                best.value = current_value
                best.routes = list(chosen)
            return

        for route in candidates[index]:
            if used_edges & route.edge_set:
                continue
            if used_junctions & route.junctions:
                continue
            used_edges |= route.edge_set
            used_junctions |= route.junctions
            chosen.append(route)
            self._search(
                index=index + 1,
                candidates=candidates,
                used_edges=used_edges,
                used_junctions=used_junctions,
                chosen=chosen,
                current_value=current_value + route.value,
                suffix_best=suffix_best,
                best=best,
            )
            chosen.pop()
            used_edges -= route.edge_set
            used_junctions -= route.junctions


@dataclass
class _SearchResult:
    value: int
    routes: list[Route] = field(default_factory=list)
