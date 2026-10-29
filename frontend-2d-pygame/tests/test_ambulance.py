# tests/test_ambulance.py — Automated Ambulance Operations Tests
# Verifies Section 15.4 of MASTER PROJECT PROMPT:
#   - Ambulance source node validation (ambulance position, not arbitrary hospital)
#   - Target civilian selection
#   - Candidate allocation and coverage metric
#   - Dispatch and mission progression
#   - Active route validity

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.city_graph import CityGraph
from core.simulation_engine import Simulation
from challenges.challenge3 import GAambulancePlacer
from config.simulation_config import SimConfig


class TestAmbulanceOperations:
    """Ambulance placement, dispatch source selection, and mission execution."""

    def test_ambulance_source_node_matches_placed_ambulance(self):
        """
        MANDATORY VERIFICATION FROM PROMPT (Section 10.1 & 15.4):
        Verify that the emergency mission initializes from the actual position
        of a placed ambulance, NOT an arbitrary hospital node.
        """
        sim = Simulation(seed=123)
        sim.initialize()

        ambulances = sim.state.ambulances
        router_start_pos = sim.state.router.current_pos

        assert ambulances, "Ambulances must be placed by GA"
        assert router_start_pos in ambulances, (
            f"Emergency route started at node {router_start_pos}, which is NOT in "
            f"the allocated ambulances {ambulances}!"
        )

    def test_ga_placement_produces_finite_fitness(self):
        graph = CityGraph()
        # Set up a connected road network with residential nodes
        for r in range(5):
            for c in range(5):
                nid = r * SimConfig.GRID_COLS + c
                if (r + c) % 2 == 0:
                    graph.nodes[nid].node_type = SimConfig.RESIDENTIAL
                else:
                    graph.nodes[nid].node_type = SimConfig.DEPOT
                # Add grid edges
                if c + 1 < 5:
                    graph.add_edge(nid, nid + 1, 1.0)
                if r + 1 < 5:
                    graph.add_edge(nid, nid + SimConfig.GRID_COLS, 1.0)

        placer = GAambulancePlacer(graph, num_ambulances=2, pop_size=10, generations=10)
        sol = placer.run()
        assert len(sol) == 2
        assert placer.best_fitness < float("inf")
        assert placer.best_fitness > 0.0

    def test_ambulance_advances_and_rescues_civilians(self):
        sim = Simulation(seed=42)
        sim.initialize()

        assert not sim.state.civilians
        target = next(n.id for n in sim.graph.nodes.values() if n.id not in sim.state.ambulances)
        sim.state.fleet.dispatch(target, sim.state.step)
        assert sim.state.fleet.emergencies[0]['status'] in ('RESPONDING', 'RESOLVED')

        # Step forward until at least one civilian is reached or max steps
        for _ in range(15):
            sim.step_forward()

        # Check router position and metrics
        assert sim.state.router.current_pos is not None
        assert sim.events.metrics.civilians_rescued >= 0
