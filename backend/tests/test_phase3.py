"""Tests for Phase 3: route finding and revenue calculation.

Each test maps to an acceptance criterion of issue #4. The rule references point
to the Hans-im-Glück 1835 rulebook (section 5.5.3).
"""
import time
from itertools import permutations

import pytest

from eg1835.domain.loader import GameDataLoader
from eg1835.domain.revenue import (
    PayoutMode,
    ShareHolding,
    distribute,
    pool_payout,
    shareholder_payout,
)
from eg1835.domain.routing import Edge, RouteFinder, RouteNetwork, Station

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def network() -> RouteNetwork:
    """The real-situation network loaded from route_network.yml."""
    return GameDataLoader().load_route_network()


def _line(*station_values: tuple[str, int]) -> RouteNetwork:
    """Build a simple chain network from (id, single-phase-value) pairs.

    All stations are wired in series with one edge between neighbours; every
    station scores ``value`` in phase 1.
    """
    net = RouteNetwork()
    ids = [sid for sid, _ in station_values]
    for sid, value in station_values:
        net.add_station(Station(id=sid, name=sid, revenue={1: value}))
    for left, right in zip(ids, ids[1:], strict=False):
        net.add_edge(Edge(id=f"{left}_{right}", a=left, b=right))
    return net


# --------------------------------------------------------------------------
# 5.5.3.4 / basic single-train scoring
# --------------------------------------------------------------------------


class TestSingleTrain:
    def test_three_train_oldenburg_bremen_hamburg(self, network: RouteNetwork) -> None:
        """3-loco Oldenburg -> Bremen -> Hamburg scores the correct sum.

        Phase 1 values: 10 + 20 + 30 = 60.
        """
        finder = RouteFinder(network, phase=1)
        result = finder.best_route_set([3], token_stations={"oldenburg"})
        assert result.total_value == 60
        route = result.routes[0]
        assert set(route.stations) == {"oldenburg", "bremen", "hamburg"}

    def test_reach_limits_station_count(self, network: RouteNetwork) -> None:
        """Reach caps the number of stations counted (rule 5.5.3.4)."""
        finder = RouteFinder(network, phase=1)
        for route in finder.routes_for_train(2):
            assert len(route.stations) <= 2

    def test_route_needs_two_stations(self) -> None:
        """A route must connect at least two distinct stations (rule 5.5.3.2)."""
        net = _line(("a", 10))  # isolated single station, no edges
        finder = RouteFinder(net, phase=1)
        assert finder.routes_for_train(3) == []

    def test_company_token_required(self) -> None:
        """Every route must include a company station (rule 5.5.3.3)."""
        net = _line(("a", 10), ("b", 20), ("c", 30))
        finder = RouteFinder(net, phase=1)
        for route in finder.routes_for_train(3, token_stations={"a"}):
            assert "a" in route.stations


# --------------------------------------------------------------------------
# 5.5.3.8 / 5.5.3.10 -- several locomotives
# --------------------------------------------------------------------------


class TestMultipleTrains:
    def test_two_plus_two_munich_passau_regensburg_nuremberg(
        self, network: RouteNetwork
    ) -> None:
        """2+2-loco over München/Passau/Regensburg/Nürnberg (phase 2).

        Optimal disjoint split scores 130 across four distinct stations.
        """
        finder = RouteFinder(network, phase=2)
        result = finder.best_route_set(
            [2, 2], token_stations={"muenchen", "regensburg"}
        )
        assert result.total_value == 130
        visited = {s for route in result.routes for s in route.stations}
        assert len(visited) == 4
        assert {"muenchen", "regensburg", "nuernberg"} <= visited

    def test_trains_share_station_but_not_edges(self) -> None:
        """Two locos may share a station but never a track segment (5.5.3.8)."""
        net = RouteNetwork()
        for sid in ("a", "b", "hub", "c", "d"):
            net.add_station(Station(id=sid, name=sid, revenue={1: 10}))
        net.add_edge(Edge(id="a_hub", a="a", b="hub"))
        net.add_edge(Edge(id="b_hub", a="b", b="hub"))
        net.add_edge(Edge(id="c_hub", a="c", b="hub"))
        net.add_edge(Edge(id="d_hub", a="d", b="hub"))

        finder = RouteFinder(net, phase=1)
        result = finder.best_route_set([3, 3], token_stations={"hub"})

        # Both trains run a 3-station route through the shared hub.
        assert result.total_value == 60
        assert all("hub" in r.stations for r in result.routes)
        # Edge-disjoint across the two routes.
        edges_a, edges_b = (r.edge_set for r in result.routes)
        assert not (edges_a & edges_b)
        # The hub station is shared by both routes.
        assert all(len(r.stations) == 3 for r in result.routes)

    def test_junction_used_by_only_one_train(self) -> None:
        """A station-less branch may be used by at most one loco (5.5.3.10).

        a - J - b   and   c - J - d : although the four edges are distinct, the
        two routes cannot both pass through junction J.
        """
        net = RouteNetwork()
        for sid in ("a", "b", "c", "d"):
            net.add_station(Station(id=sid, name=sid, revenue={1: 10}))
        net.add_junction("J", "branch")
        net.add_edge(Edge(id="a_J", a="a", b="J"))
        net.add_edge(Edge(id="J_b", a="J", b="b"))
        net.add_edge(Edge(id="c_J", a="c", b="J"))
        net.add_edge(Edge(id="J_d", a="J", b="d"))

        finder = RouteFinder(net, phase=1)
        result = finder.best_route_set([3, 3])

        # Only one train can route through the junction; the other runs empty.
        users = [r for r in result.routes if "J" in r.junctions]
        assert len(users) == 1
        assert result.total_value == 20  # a-J-b (10+10), second loco idle


# --------------------------------------------------------------------------
# 5.5.3.6 -- blocked stations
# --------------------------------------------------------------------------


class TestBlockedStation:
    def _net(self) -> RouteNetwork:
        net = RouteNetwork()
        net.add_station(Station(id="a", name="a", revenue={1: 10}))
        net.add_station(Station(id="b", name="b", revenue={1: 20}, blocked=True))
        net.add_station(Station(id="c", name="c", revenue={1: 30}))
        net.add_edge(Edge(id="a_b", a="a", b="b"))
        net.add_edge(Edge(id="b_c", a="b", b="c"))
        return net

    def test_blocked_station_allowed_as_endpoint(self) -> None:
        finder = RouteFinder(self._net(), phase=1)
        routes = finder.routes_for_train(3, token_stations={"a"})
        ending_at_b = [r for r in routes if r.stations == ("a", "b")]
        assert ending_at_b, "route ending at the blocked station must be legal"

    def test_blocked_station_forbidden_as_through_point(self) -> None:
        finder = RouteFinder(self._net(), phase=1)
        routes = finder.routes_for_train(3, token_stations={"a"})
        # No route may pass through 'b' to reach 'c'.
        assert all("c" not in r.stations for r in routes)
        for route in routes:
            interior = route.stations[1:-1]
            assert "b" not in interior


# --------------------------------------------------------------------------
# 5.5.3.11.3 -- Fernverbindungen, Hamburg ferry and Elsaß-Lothringen
# --------------------------------------------------------------------------


class TestOffboardConnections:
    def _hamburg_net(self, with_ferry: bool) -> RouteNetwork:
        net = RouteNetwork()
        net.add_station(Station(id="bremen", name="Bremen", revenue={3: 0}))
        net.add_station(
            Station(
                id="hamburg",
                name="Hamburg",
                is_offboard=True,
                revenue={3: 50},
                ferry_revenue={3: 60},
            )
        )
        net.add_edge(Edge(id="bremen_hamburg", a="bremen", b="hamburg", ferry=with_ferry))
        return net

    def test_hamburg_brown_with_ferry_scores_60(self) -> None:
        finder = RouteFinder(self._hamburg_net(with_ferry=True), phase=3)
        result = finder.best_route_set([2], token_stations={"bremen"})
        assert result.total_value == 60

    def test_hamburg_brown_without_ferry_scores_50(self) -> None:
        finder = RouteFinder(self._hamburg_net(with_ferry=False), phase=3)
        result = finder.best_route_set([2], token_stations={"bremen"})
        assert result.total_value == 50

    def test_elsass_only_usable_from_phase_2(self, network: RouteNetwork) -> None:
        """Elsaß-Lothringen is unreachable in phase 1, reachable from phase 2."""
        phase1 = RouteFinder(network, phase=1)
        reachable_p1 = {
            s for route in phase1.routes_for_train(6) for s in route.stations
        }
        assert "elsass" not in reachable_p1

        phase2 = RouteFinder(network, phase=2)
        result = phase2.best_route_set([6], token_stations={"strassburg"})
        visited = {s for r in result.routes for s in r.stations}
        assert "elsass" in visited


# --------------------------------------------------------------------------
# 5.5.3.11.2 -- the maximum must be run
# --------------------------------------------------------------------------


class TestMandatoryMaximum:
    def test_finder_never_returns_suboptimal_route(self) -> None:
        """best_route_set matches the brute-force optimum (rule 5.5.3.11.2)."""
        net = RouteNetwork()
        for sid, val in (("a", 10), ("b", 50), ("c", 20), ("d", 40), ("e", 30)):
            net.add_station(Station(id=sid, name=sid, revenue={1: val}))
        for left, right in (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("a", "e")):
            net.add_edge(Edge(id=f"{left}_{right}", a=left, b=right))

        finder = RouteFinder(net, phase=1)
        routes = finder.routes_for_train(3)
        brute_force_best = max(r.value for r in routes)

        result = finder.best_route_set([3])
        assert result.total_value == brute_force_best

    def test_two_train_optimum_matches_brute_force(self) -> None:
        net = RouteNetwork()
        for sid, val in (("a", 10), ("b", 50), ("c", 20), ("d", 40)):
            net.add_station(Station(id=sid, name=sid, revenue={1: val}))
        for left, right in (("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")):
            net.add_edge(Edge(id=f"{left}_{right}", a=left, b=right))

        finder = RouteFinder(net, phase=1)
        routes = finder.routes_for_train(2)

        # Brute-force the best edge/junction-disjoint pair.
        best_pair = 0
        for r1, r2 in permutations(routes, 2):
            if not (r1.edge_set & r2.edge_set) and not (r1.junctions & r2.junctions):
                best_pair = max(best_pair, r1.value + r2.value)

        result = finder.best_route_set([2, 2])
        assert result.total_value == best_pair


# --------------------------------------------------------------------------
# 5.5.3.11.5 / .6 / .7 -- dividend distribution
# --------------------------------------------------------------------------


class TestPayout:
    def test_ag_all_or_nothing_retain(self) -> None:
        """An AG retains the whole revenue or none -- no split (5.5.3.11.5)."""
        holdings = [ShareHolding("alice", 60), ShareHolding("bob", 40)]
        result = distribute(100, PayoutMode.FULL_RETAIN, holdings)
        assert result.to_treasury == 100
        assert result.to_shareholders == {}

    def test_ag_full_payout(self) -> None:
        holdings = [ShareHolding("alice", 60), ShareHolding("bob", 40)]
        result = distribute(100, PayoutMode.FULL_PAYOUT, holdings)
        assert result.to_treasury == 0
        assert result.to_shareholders == {"alice": 60, "bob": 40}

    def test_shareholder_share_rounds_up(self) -> None:
        # 95 * 10% = 9.5 -> rounded up to 10 (rule 5.5.3.11.6).
        assert shareholder_payout(95, 10) == 10

    def test_pool_share_rounds_down(self) -> None:
        # 95 * 10% = 9.5 -> rounded down to 9 (rule 5.5.3.11.7).
        assert pool_payout(95, 10) == 9

    def test_preussen_five_percent_rounding_asymmetry(self) -> None:
        """5% Preußen: shareholder rounds up, pool rounds down (5.5.3.11.6/.7)."""
        revenue = 90  # 5% of 90 = 4.5
        shareholder = ShareHolding("president", 5)
        pool = ShareHolding("pool", 5, is_pool=True)
        result = distribute(revenue, PayoutMode.FULL_PAYOUT, [shareholder, pool])
        assert result.to_shareholders["president"] == 5  # ceil(4.5)
        assert result.to_shareholders["pool"] == 4  # floor(4.5)


# --------------------------------------------------------------------------
# Performance
# --------------------------------------------------------------------------


class TestPerformance:
    def test_full_board_under_500ms(self, network: RouteNetwork) -> None:
        """A full computation on the loaded board stays under 500 ms."""
        finder = RouteFinder(network, phase=3)
        start = time.perf_counter()
        finder.best_route_set([6])
        finder.best_route_set([6, 6])
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"route computation took {elapsed * 1000:.0f} ms"
