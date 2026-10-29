# tests/test_routing.py — Automated Routing and Correctness Tests
# Verifies Section 15.2 of MASTER PROJECT PROMPT:
#   - Weighted shortest paths
#   - Hop-count trap: multi-hop cheaper than direct path
#   - A* vs Reference Dijkstra optimality equivalence
#   - Blocked edges bypass
#   - Unreachable destination handling
#   - Directional risk sensitivity in path selection

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.city_graph import CityGraph
from challenges.challenge4 import AStarRouter
from algorithms.reference_dijkstra import dijkstra, validate_path


class TestRoutingCorrectness:
    """Rigorous routing tests testing edge costs, A*, and reference Dijkstra."""

    def test_hop_count_trap_multi_hop_cheaper_than_direct(self):
        """
        MANDATORY TEST FROM PROMPT (Section 15.2):
        Construct a graph where 0 -> 2 direct edge cost is 100.0 (1 hop),
        but 0 -> 1 -> 2 has costs 1.0 + 1.0 = 2.0 (2 hops).
        A correct weighted pathfinder MUST choose 0 -> 1 -> 2.
        Algorithms minimizing hop count fail this test.
        """
        graph = CityGraph()
        # Direct edge: expensive
        graph.add_edge(0, 2, 100.0)
        # 2-hop path: very cheap
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)

        # 1. Test Reference Dijkstra
        nodes_dict = {nid: n.to_dict() for nid, n in graph.nodes.items()}
        edges_list = [e.to_dict() for e in graph.edges.values()]
        ref_result = dijkstra(nodes_dict, edges_list, start_id=0, goal_id=2)

        assert ref_result["reachable"] is True
        assert ref_result["path"] == [0, 1, 2], f"Reference Dijkstra picked suboptimal hops: {ref_result['path']}"
        assert ref_result["path_cost"] == 2.0
        assert ref_result["hops"] == 2

        # 2. Test A* Router
        router = AStarRouter(graph)
        astar_path = router.astar(0, 2)
        assert astar_path == [0, 1, 2], f"A* picked 1-hop expensive edge instead of cheap 2-hop path: {astar_path}"

    def test_astar_matches_reference_dijkstra(self):
        """Verify that A* produces the exact optimal cost reported by reference Dijkstra."""
        graph = CityGraph()
        # Create a small grid-like graph with varying weights
        #  0 --(2.0)-- 1 --(1.0)-- 2
        #  |           |           |
        # (5.0)       (1.5)       (4.0)
        #  |           |           |
        #  3 --(1.0)-- 4 --(2.0)-- 5
        graph.add_edge(0, 1, 2.0)
        graph.add_edge(1, 2, 1.0)
        graph.add_edge(0, 3, 5.0)
        graph.add_edge(1, 4, 1.5)
        graph.add_edge(2, 5, 4.0)
        graph.add_edge(3, 4, 1.0)
        graph.add_edge(4, 5, 2.0)

        nodes_dict = {nid: n.to_dict() for nid, n in graph.nodes.items()}
        edges_list = [e.to_dict() for e in graph.edges.values()]
        ref = dijkstra(nodes_dict, edges_list, start_id=0, goal_id=5)

        router = AStarRouter(graph)
        astar_path = router.astar(0, 5)

        assert astar_path is not None
        # Validate A* path against graph
        validation = validate_path(astar_path, nodes_dict, edges_list, claimed_cost=ref["path_cost"])
        assert validation["valid"] is True
        assert validation["optimal"] is True
        assert abs(validation["actual_cost"] - ref["path_cost"]) < 1e-6

    def test_routing_respects_blocked_edges(self):
        """When the shortest path is blocked, the router must take the detour."""
        graph = CityGraph()
        # Path A: 0 -> 1 -> 2 (cost 1 + 1 = 2)
        # Path B: 0 -> 3 -> 2 (cost 3 + 3 = 6)
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)
        graph.add_edge(0, 3, 3.0)
        graph.add_edge(3, 2, 3.0)

        router = AStarRouter(graph)
        assert router.astar(0, 2) == [0, 1, 2]

        # Block road (1, 2)
        graph.block_road(1, 2)

        # Must detour through 3
        new_path = router.astar(0, 2)
        assert new_path == [0, 3, 2]

    def test_unreachable_target_returns_none(self):
        graph = CityGraph()
        graph.add_edge(0, 1, 1.0)
        # Node 10 is completely disconnected
        router = AStarRouter(graph)
        assert router.astar(0, 10) is None

        nodes_dict = {nid: n.to_dict() for nid, n in graph.nodes.items()}
        edges_list = [e.to_dict() for e in graph.edges.values()]
        ref = dijkstra(nodes_dict, edges_list, start_id=0, goal_id=10)
        assert ref["reachable"] is False
        assert ref["path"] == []

    def test_routing_sensitive_to_risk_multipliers(self):
        """High-risk zones double the edge cost, making alternative low-risk routes preferable."""
        graph = CityGraph()
        # Route through node 1: base cost 2.0 + 2.0 = 4.0
        # Route through node 2: base cost 3.0 + 3.0 = 6.0
        graph.add_edge(0, 1, 2.0)
        graph.add_edge(1, 3, 2.0)
        graph.add_edge(0, 2, 3.0)
        graph.add_edge(2, 3, 3.0)

        router = AStarRouter(graph)
        assert router.astar(0, 3) == [0, 1, 3]

        # Now make node 1 HIGH risk (multiplier 2.0)
        # Traversal into node 1 costs 2.0 * 2.0 = 4.0. Traversal 1->3 costs 2.0 * 1.0 = 2.0. Total = 6.0.
        # But if node 1 risk is HIGH and edge cost is 2.5:
        graph.nodes[1].risk_level = "HIGH"
        graph.nodes[3].risk_level = "HIGH"
        # 0->1 costs 2.0 * 2.0 = 4.0. 1->3 costs 2.0 * 2.0 = 4.0. Total = 8.0.
        # Route through 2: 0->2 (LOW=3.0), 2->3 (HIGH=3.0*2.0=6.0). Wait, let's keep 3 LOW:
        graph.nodes[3].risk_level = "LOW"
        graph.nodes[1].risk_level = "HIGH"  # entering 1 costs 2.0 * 2.0 = 4.0
        # Total via 1: 0->1 (4.0) + 1->3 (2.0) = 6.0
        # Make route via 2 cheaper: base cost 2.5 + 2.5 = 5.0
        graph.edges[(0, 2)].cost = 2.5
        graph.edges[(2, 3)].cost = 2.5
        # Total via 2: 0->2 (2.5) + 2->3 (2.5) = 5.0
        # Router should now pick [0, 2, 3] because 5.0 < 6.0
        new_path = router.astar(0, 3)
        assert new_path == [0, 2, 3]
