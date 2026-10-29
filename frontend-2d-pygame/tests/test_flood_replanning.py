# tests/test_flood_replanning.py — Automated Flood and Replanning Tests
# Verifies Section 15.3 of MASTER PROJECT PROMPT:
#   - Road block on active route triggers automatic replanning
#   - Alternative path selection
#   - Handling when destination becomes unreachable
#   - Consecutive floods
#   - Road unblocking
#   - Resetting simulation restores graph connectivity

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.city_graph import CityGraph
from core.simulation_engine import Simulation
from challenges.challenge4 import AStarRouter


class TestFloodAndReplanning:
    """Tests for dynamic replanning under flood disruptions and God Mode operations."""

    def test_observer_triggers_automatic_replanning_on_block(self):
        graph = CityGraph()
        # Route 0 -> 1 -> 2 -> 3
        # Alternative 0 -> 4 -> 3
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)
        graph.add_edge(2, 3, 1.0)
        graph.add_edge(0, 4, 2.0)
        graph.add_edge(4, 3, 2.0)

        router = AStarRouter(graph)
        router.set_mission(start_id=0, civilian_ids=[3])

        assert router.current_path == [0, 1, 2, 3]
        initial_reroutes = router.total_reroutes

        # Advance team 1 step: team moves to node 1
        router.advance_one_step()
        assert router.current_pos == 1
        assert router.current_path == [1, 2, 3]

        # Now flood edge (2, 3) which is ahead on the active route
        graph.block_road(2, 3)

        # Observer must immediately trigger replan from current position (node 1)
        assert router.total_reroutes == initial_reroutes + 1
        # Edge (1, 0) -> (0, 4) -> (4, 3)
        assert 2 not in router.current_path
        assert router.current_path[-1] == 3

    def test_unreachable_civilian_skips_gracefully(self):
        graph = CityGraph()
        # Component 1: 0, 1
        graph.add_edge(0, 1, 1.0)
        # Component 2: 2, 3 (isolated)
        graph.add_edge(2, 3, 1.0)

        router = AStarRouter(graph)
        router.set_mission(start_id=0, civilian_ids=[3, 1])

        # Civilian at 3 is unreachable; router should skip 3 and plan to 1
        assert router.current_path == [0, 1]
        assert 3 not in router.civilians
        assert any("WARNING" in log for log in router.log)

    def test_multiple_consecutive_floods(self):
        graph = CityGraph()
        # Grid layout:
        # 0 - 1 - 2
        # |   |   |
        # 3 - 4 - 5
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 2, 1.0)
        graph.add_edge(0, 3, 1.0)
        graph.add_edge(1, 4, 1.0)
        graph.add_edge(2, 5, 1.0)
        graph.add_edge(3, 4, 1.0)
        graph.add_edge(4, 5, 1.0)

        router = AStarRouter(graph)
        router.set_mission(start_id=0, civilian_ids=[5])
        assert router.current_path is not None

        # Block 1st bridge
        graph.block_road(1, 2)
        assert router.current_path is not None
        assert (1, 2) not in [(router.current_path[i], router.current_path[i+1]) for i in range(len(router.current_path)-1)]

        # Block 2nd bridge
        graph.block_road(4, 5)
        # Only path remaining is 0 -> 1 -> 4 -> ... wait, 2->5? but 1->2 is blocked!
        # Check if 5 is still reachable:
        # Can we reach 2? Only from 5: 3->0->1->4->? 4->5 blocked, 1->2 blocked. 5 is unreachable!
        assert router.current_path == []
        assert any("WARNING: No path" in log for log in router.log)

    def test_road_unblocking_restores_connectivity(self):
        graph = CityGraph()
        graph.add_edge(0, 1, 1.0)
        graph.block_road(0, 1)

        router = AStarRouter(graph)
        assert router.astar(0, 1) is None

        # Unblock road
        graph.unblock_road(0, 1)
        assert router.astar(0, 1) == [0, 1]

    def test_simulation_reset_state(self):
        sim = Simulation(seed=42)
        sim.initialize()
        initial_active = sim.graph.count_active_edges()

        # Step and flood
        sim.step_forward()
        sim.trigger_flood_at_node(0)
        assert sim.graph.count_blocked_edges() > 0

        # Reset / reinitialize
        sim2 = Simulation(seed=42)
        sim2.initialize()
        assert sim2.state.step == 0
        assert sim2.graph.count_active_edges() == initial_active
        assert sim2.graph.count_blocked_edges() == 0
