# tests/test_graph.py — Automated Graph Integrity and Semantics Tests
# Verifies Section 15.1 of MASTER PROJECT PROMPT:
#   - Unique node IDs
#   - Valid endpoints
#   - Consistent adjacency
#   - Valid weights
#   - Blocked-edge representation & unblocking
#   - Serialization (to_dict & from_dict roundtrip)
#   - Cost calculation with risk multipliers
#   - Missing data / isolated nodes

import os
import sys
import pytest

# Ensure imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.city_graph import CityGraph, Node, Edge
from config.simulation_config import SimConfig


class TestGraphIntegrity:
    """Core graph data structure integrity."""

    def test_node_ids_unique_and_sequential(self):
        graph = CityGraph()
        node_ids = set()
        for nid, node in graph.nodes.items():
            assert nid == node.id, f"Dict key {nid} does not match node.id {node.id}"
            assert nid not in node_ids, f"Duplicate node ID found: {nid}"
            node_ids.add(nid)
            # Row and column coordinates must be within grid dimensions
            assert 0 <= node.row < SimConfig.GRID_ROWS
            assert 0 <= node.col < SimConfig.GRID_COLS
            assert node.id == node.row * SimConfig.GRID_COLS + node.col
        assert len(node_ids) == SimConfig.GRID_ROWS * SimConfig.GRID_COLS

    def test_edges_have_valid_endpoints(self):
        graph = CityGraph()
        # Add sample edges
        graph.add_edge(0, 1, 1.0)
        graph.add_edge(1, 16, 1.4)
        for (a, b), edge in graph.edges.items():
            assert a in graph.nodes, f"Endpoint {a} does not exist in graph"
            assert b in graph.nodes, f"Endpoint {b} does not exist in graph"
            assert a < b, f"Edge key ({a}, {b}) is not canonically ordered"
            assert edge.cost >= 0.0, f"Edge cost must be non-negative: {edge.cost}"

    def test_consistent_adjacency(self):
        graph = CityGraph()
        graph.add_edge(5, 6, 1.0)
        graph.add_edge(6, 21, 1.0)

        # Adjacency symmetry
        assert 6 in graph.adj[5]
        assert 5 in graph.adj[6]
        assert 21 in graph.adj[6]
        assert 6 in graph.adj[21]

        # Neighbors query
        assert 6 in graph.get_neighbors(5)
        assert 5 in graph.get_neighbors(6)

    def test_blocked_edge_representation_and_unblocking(self):
        graph = CityGraph()
        graph.add_edge(10, 11, 1.0)
        assert 11 in graph.get_neighbors(10)
        assert 10 in graph.get_neighbors(11)
        assert graph.get_edge_cost(10, 11) == 1.0

        # Block the road
        graph.block_road(10, 11)
        key = (10, 11)
        assert graph.edges[key].blocked is True
        assert 11 not in graph.get_neighbors(10)
        assert 10 not in graph.get_neighbors(11)
        assert graph.get_edge_cost(10, 11) == float("inf")

        # Unblock the road
        graph.unblock_road(10, 11)
        assert graph.edges[key].blocked is False
        assert 11 in graph.get_neighbors(10)
        assert 10 in graph.get_neighbors(11)
        assert graph.get_edge_cost(10, 11) == 1.0

    def test_serialization_roundtrip(self):
        graph = CityGraph()
        graph.nodes[0].node_type = SimConfig.HOSPITAL
        graph.nodes[0].population = 25
        graph.nodes[0].risk_level = "HIGH"
        graph.nodes[1].node_type = SimConfig.RESIDENTIAL
        graph.nodes[1].population = 150
        graph.add_edge(0, 1, 1.2)
        graph.block_road(0, 1)

        d = graph.to_dict()
        restored = CityGraph.from_dict(d)

        assert restored.nodes[0].node_type == SimConfig.HOSPITAL
        assert restored.nodes[0].population == 25
        assert restored.nodes[0].risk_level == "HIGH"
        assert restored.nodes[1].node_type == SimConfig.RESIDENTIAL
        assert restored.nodes[1].population == 150
        key = (0, 1)
        assert key in restored.edges
        assert restored.edges[key].blocked is True
        assert restored.edges[key].cost == 1.2

    def test_cost_calculation_with_directional_risk(self):
        graph = CityGraph()
        graph.add_edge(1, 2, 10.0)
        graph.nodes[1].risk_level = "LOW"     # multiplier 1.0
        graph.nodes[2].risk_level = "HIGH"    # multiplier 2.0

        # Moving 1 -> 2 enters HIGH risk node 2: cost should be 10.0 * 2.0 = 20.0
        cost_1_to_2 = graph.get_edge_cost(1, 2)
        assert cost_1_to_2 == 20.0, f"Expected 20.0 entering HIGH risk, got {cost_1_to_2}"

        # Moving 2 -> 1 enters LOW risk node 1: cost should be 10.0 * 1.0 = 10.0
        cost_2_to_1 = graph.get_edge_cost(2, 1)
        assert cost_2_to_1 == 10.0, f"Expected 10.0 entering LOW risk, got {cost_2_to_1}"

    def test_isolated_node_detection(self):
        graph = CityGraph()
        # All nodes have no edges initially
        disc = graph.find_disconnected_nodes()
        assert len(disc) == len(graph.nodes)

        # Connect node 0 and 1
        graph.add_edge(0, 1, 1.0)
        disc_after = graph.find_disconnected_nodes()
        assert 0 not in disc_after
        assert 1 not in disc_after
