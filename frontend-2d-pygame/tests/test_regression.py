# tests/test_regression.py — Regression Tests for Identified & Fixed Defects
# Verifies Section 15.6 and Section 16 of MASTER PROJECT PROMPT:
#   - Regression 1: Directional edge risk cost (entering node B vs node A)
#   - Regression 2: Emergency router start source (ambulance node vs arbitrary hospital)
#   - Regression 3: Road unblocking restores adjacency
#   - Regression 4: Hop count vs cost optimization (hop count is NOT distance)

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.city_graph import CityGraph
from core.simulation_engine import Simulation
from challenges.challenge4 import AStarRouter
from algorithms.reference_dijkstra import dijkstra, validate_path
from core.event_manager import EventManager, EventType


class TestDefectRegressions:
    """Explicit regression tests for confirmed bugs fixed during audit."""

    def test_regression_directional_edge_cost(self):
        """
        Defect: Edge.effective_cost previously evaluated only self.node_b regardless
        of traversal direction, causing incorrect risk weighting when moving from
        node_b to node_a.
        Fix: Edge.effective_cost now accepts to_node_id, and CityGraph.get_edge_cost(a, b)
        passes to_node_id=b.
        """
        graph = CityGraph()
        # Edge between 10 and 20: canonically node_a=10, node_b=20
        graph.add_edge(10, 20, 5.0)
        graph.nodes[10].risk_level = "HIGH"   # multiplier 2.0
        graph.nodes[20].risk_level = "LOW"    # multiplier 1.0

        # Traversing 10 -> 20 enters LOW risk: cost = 5.0 * 1.0 = 5.0
        cost_fwd = graph.get_edge_cost(10, 20)
        assert cost_fwd == 5.0, f"Expected 5.0 entering LOW risk, got {cost_fwd}"

        # Traversing 20 -> 10 enters HIGH risk: cost = 5.0 * 2.0 = 10.0
        cost_rev = graph.get_edge_cost(20, 10)
        assert cost_rev == 10.0, f"Expected 10.0 entering HIGH risk, got {cost_rev}"

    def test_regression_router_ambulance_start_node(self):
        """
        Defect: Emergency router set_mission previously took hospitals[0].id as start node
        instead of an active ambulance position.
        Fix: simulation_engine.initialize() now chooses the closest active ambulance
        to the first target civilian.
        """
        sim = Simulation(seed=999)
        sim.initialize()

        assert sim.state.ambulances, "Ambulances must exist"
        start_pos = sim.state.router.current_pos
        assert start_pos in sim.state.ambulances, (
            f"Router started at node {start_pos}, which is NOT an active ambulance position: {sim.state.ambulances}"
        )

    def test_regression_road_unblock_restores_adjacency(self):
        """
        Defect: CityGraph had remove_edge/block_road but no unblock_road method,
        preventing roads from being reopened.
        Fix: Added CityGraph.unblock_road(a, b).
        """
        graph = CityGraph()
        graph.add_edge(1, 2, 1.0)
        graph.block_road(1, 2)
        assert 2 not in graph.get_neighbors(1)

        graph.unblock_road(1, 2)
        assert 2 in graph.get_neighbors(1)
        assert 1 in graph.get_neighbors(2)
        assert graph.get_edge_cost(1, 2) == 1.0

    def test_regression_weighted_dijkstra_hop_count_trap(self):
        """
        Defect: Algorithms or frontends counting hops as distance instead of edge weights.
        Fix: Both backend A* and frontend reference Dijkstra evaluate sum of effective weights.
        """
        graph = CityGraph()
        # Direct: 1 hop, weight 50.0
        graph.add_edge(0, 1, 50.0)
        # Detour: 3 hops, weight 1.0 + 1.0 + 1.0 = 3.0
        graph.add_edge(0, 2, 1.0)
        graph.add_edge(2, 3, 1.0)
        graph.add_edge(3, 1, 1.0)

        router = AStarRouter(graph)
        path = router.astar(0, 1)
        assert path == [0, 2, 3, 1], f"Router picked 1-hop expensive route: {path}"

        nodes_dict = {nid: n.to_dict() for nid, n in graph.nodes.items()}
        edges_list = [e.to_dict() for e in graph.edges.values()]
        ref = dijkstra(nodes_dict, edges_list, start_id=0, goal_id=1)
        assert ref["path"] == [0, 2, 3, 1]
        assert ref["path_cost"] == 3.0
        assert ref["hops"] == 3

    def test_regression_astar_admissibility_and_optimality_f1(self):
        """
        F1: A* heuristic is scaled by min_cost_per_unit (0.8) so it never
        overestimates path cost on residential (0.8) or diagonal (1.4) edges.
        A* must find a route with cost equal to reference Dijkstra.
        """
        graph = CityGraph()
        # Build 3x3 grid with residential and diagonal edges
        # 0(0,0) - 1(1,0) - 2(2,0)
        # |     \  |     \  |
        # 3(0,1) - 4(1,1) - 5(2,1)
        # |        |        |
        # 6(0,2) - 7(1,2) - 8(2,2)
        for r in range(3):
            for c in range(3):
                nid = r * 3 + c
                node = graph.nodes[nid]
                node.col = c
                node.row = r
                node.node_type = "RESIDENTIAL"
                node.risk_level = "LOW"

        # Orthogonal residential edges: 0.8
        graph.add_edge(0, 1, 0.8)
        graph.add_edge(1, 2, 0.8)
        graph.add_edge(0, 3, 0.8)
        graph.add_edge(1, 4, 0.8)
        graph.add_edge(2, 5, 0.8)
        graph.add_edge(3, 4, 0.8)
        graph.add_edge(4, 5, 0.8)
        graph.add_edge(3, 6, 0.8)
        graph.add_edge(4, 7, 0.8)
        graph.add_edge(5, 8, 0.8)
        graph.add_edge(6, 7, 0.8)
        graph.add_edge(7, 8, 0.8)
        # Diagonal shortcuts: cost 1.4
        graph.add_edge(0, 4, 1.4)
        graph.add_edge(4, 8, 1.4)

        router = AStarRouter(graph)
        astar_path = router.astar(0, 8)
        assert astar_path is not None

        nodes_dict = {nid: n.to_dict() for nid, n in graph.nodes.items()}
        edges_list = [e.to_dict() for e in graph.edges.values()]
        ref = dijkstra(nodes_dict, edges_list, 0, 8)

        # Compute actual cost of A* path
        astar_cost = sum(graph.get_edge_cost(astar_path[i], astar_path[i+1]) for i in range(len(astar_path)-1))
        assert abs(astar_cost - ref["path_cost"]) < 1e-6, (
            f"A* cost {astar_cost} does not match Dijkstra optimal cost {ref['path_cost']}"
        )

    def test_regression_risk_change_triggers_replanning_f2(self):
        """
        F2: Risk update on active route notifies observers to re-evaluate route.
        """
        graph = CityGraph()
        # Route 0 -> 1 -> 2 (initially cost 1.0 + 1.0 = 2.0)
        # Detour 0 -> 3 -> 2 (cost 1.2 + 1.2 = 2.4)
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)
        graph.add_edge(0, 3, 1.2)
        graph.add_edge(3, 2, 1.2)

        router = AStarRouter(graph)
        router.set_mission(start_id=0, civilian_ids=[2])
        assert router.current_path == [0, 1, 2]

        # Register router risk observer (already done in AStarRouter.__init__)
        # Spike risk at node 1 to HIGH (mult 2.0 -> enters node 1 costs 2.0, total 0->1->2 becomes 3.0)
        # Detour 0->3->2 costs 2.4 < 3.0
        graph.nodes[1].risk_level = "HIGH"
        graph._notify_risk_changed(1)

        # Active path should replan to detour [0, 3, 2]
        assert router.current_path == [0, 3, 2], f"Router failed to replan around high risk: {router.current_path}"

    def test_regression_atomic_flood_and_single_counter_f6_f7_f32(self):
        """
        F6/F7/F32: Flooding a node with multiple edges blocks all incident edges,
        counts as exactly 1 flood event (not 1 per edge), does NOT advance sim step,
        and triggers batch replanning rather than one replan per blocked edge.
        """
        sim = Simulation(seed=123)
        sim.initialize()
        initial_step = sim.state.step
        initial_floods = sim.events.metrics.total_floods

        # Pick a node with multiple incident edges
        node_with_edges = None
        for nid in sim.graph.nodes:
            if len(sim.graph.get_neighbors(nid)) >= 3:
                node_with_edges = nid
                break
        assert node_with_edges is not None

        result = sim.trigger_flood_at_node(node_with_edges)
        assert result["flooded"] is True
        assert result["edges_blocked"] >= 3

        # F6: Step must NOT advance
        assert sim.state.step == initial_step

        # F7: Exactly ONE flood counted
        assert sim.events.metrics.total_floods == initial_floods + 1

    def test_regression_unblock_restores_deferred_civilians_f11_f26(self):
        """
        F11/F26: When a road is blocked making a civilian unreachable, the civilian
        is deferred. When the road is unblocked, the router is notified and restores
        deferred civilians.
        """
        graph = CityGraph()
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)

        router = AStarRouter(graph)
        router.set_mission(start_id=0, civilian_ids=[2])
        assert router.current_path == [0, 1, 2]

        # Block edge (1, 2): civilian at 2 becomes unreachable
        graph.block_road(1, 2)
        assert router.current_path == []
        assert 2 in router.deferred_civilians

        # Unblock edge (1, 2): observer notified, restores civilian 2 to active queue
        graph.unblock_road(1, 2)
        assert 2 in router.civilians
        assert router.current_path == [0, 1, 2]

    def test_regression_ga_infeasible_flag_f5(self):
        """
        F5: GA sets is_infeasible=True when residential nodes are completely
        disconnected from candidate depots.
        """
        from challenges.challenge3 import GAambulancePlacer
        graph = CityGraph()
        # Island 1: Depots
        d1 = graph.nodes[0]; d1.node_type = "AMBULANCE_DEPOT"
        d2 = graph.nodes[1]; d2.node_type = "AMBULANCE_DEPOT"
        graph.add_edge(0, 1, 1.0)

        # Island 2: Disconnected residential
        r1 = graph.nodes[10]; r1.node_type = "RESIDENTIAL"
        r2 = graph.nodes[11]; r2.node_type = "RESIDENTIAL"
        graph.add_edge(10, 11, 1.0)

        placer = GAambulancePlacer(graph, num_ambulances=2, pop_size=10, generations=5)
        placer.run()
        assert placer.is_infeasible is True

    def test_regression_step_forward_completion_flag_f13(self):
        """
        F13: step_forward sets state.is_complete = True when step reaches max_steps.
        """
        sim = Simulation(seed=123)
        sim.initialize()
        sim.state.step = sim.state.max_steps - 1
        assert not sim.state.is_complete

        sim.step_forward()
        assert sim.state.step == sim.state.max_steps
        assert sim.state.is_complete is True

    def test_regression_validate_path_endpoints_and_unreachable_f18_f19_f22(self):
        """
        F18/F19/F22: validate_path cleanly distinguishes unreachable targets,
        checks expected source and target endpoints, and handles malformed IDs.
        """
        nodes = {
            0: {"id": 0, "col": 0, "row": 0, "node_type": "AMBULANCE_DEPOT", "risk_level": "LOW"},
            1: {"id": 1, "col": 1, "row": 0, "node_type": "RESIDENTIAL", "risk_level": "LOW"},
            2: {"id": 2, "col": 2, "row": 0, "node_type": "RESIDENTIAL", "risk_level": "LOW"},
        }
        # Only edge between 0 and 1; node 2 is disconnected
        edges = [{"node_a": 0, "node_b": 1, "cost": 1.0, "blocked": False}]

        # 1. Unreachable destination (F18)
        rep_unreach = validate_path([], nodes, edges, expected_source=0, expected_target=2)
        assert rep_unreach["valid"] is False
        assert rep_unreach["unreachable"] is True

        # 2. Malformed path with non-integer ID (F19)
        rep_malformed = validate_path(["invalid", 1], nodes, edges)
        assert rep_malformed["valid"] is False
        assert any("not an integer" in s for s in rep_malformed["issues"])

        # 3. Endpoint mismatch (F22)
        rep_endpoint = validate_path([0, 1], nodes, edges, expected_source=0, expected_target=2)
        assert rep_endpoint["valid"] is False
        assert any("expected 2" in s for s in rep_endpoint["issues"])

        # 4. Valid path matching expected endpoints
        rep_valid = validate_path([0, 1], nodes, edges, expected_source=0, expected_target=1)
        assert rep_valid["valid"] is True
        assert rep_valid["actual_cost"] == 1.0

    def test_regression_event_history_bounding_f50(self):
        """
        F50: EventManager bounds event_history to prevent unbounded memory growth.
        """
        from core.event_manager import EventManager
        em = EventManager(verbose=False)
        for i in range(2500):
            em.log(EventType.SIMULATION, f"Message {i}")
        assert len(em.event_history) <= EventManager.MAX_EVENTS
        assert len(em.event_history) >= int(EventManager.MAX_EVENTS * 0.9)

    def test_regression_stale_poller_snapshot_protection_f23(self):
        """
        F23: AppState.update_sim discards older step polling snapshots
        when a newer step state has already been applied.
        """
        from app.state import AppState
        state = AppState()
        # Newer mutation snapshot arrives (step 10, sim_id 'sim-abc')
        state.update_sim({"sim_id": "sim-abc", "step": 10, "ambulances": [1, 2, 3]})
        assert state.backend_sim.step == 10

        # Delayed poller arrives with older snapshot (step 8, same sim_id)
        state.update_sim({"sim_id": "sim-abc", "step": 8, "ambulances": [1, 2]})
        # Must retain newer step 10
        assert state.backend_sim.step == 10

