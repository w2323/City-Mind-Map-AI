# tests/test_frontend_integration.py — Frontend Client and State Integration Tests
# Verifies Section 15.5 of MASTER PROJECT PROMPT:
#   - Backend connection failure handling (graceful error reporting, no crashes)
#   - Timeout handling
#   - Malformed response handling
#   - Missing fields and zero vs missing distinctions
#   - AppState thread safety & updates
#   - Empty/disconnected graph resilience

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.state import AppState, ConnectionStatus, ActiveScreen
from backend_client.api_client import CityMindClient


class TestFrontendIntegration:
    """Tests for API client resilience, error handling, and state integrity."""

    def test_client_handles_unreachable_backend_gracefully(self):
        # Point client to a port that has nothing listening
        client = CityMindClient(base_url="http://127.0.0.1:59999")
        ok, err = client.ping()
        assert ok is False
        assert err is not None
        assert "Cannot connect" in err

        data, err = client.get_state()
        assert data is None
        assert err is not None

        data, err = client.restart()
        assert data is None
        assert err is not None

        data, err = client.step()
        assert data is None
        assert err is not None

        data, err = client.flood_node(10)
        assert data is None
        assert err is not None

    def test_client_rejects_invalid_node_id_locally(self):
        client = CityMindClient()
        data, err = client.flood_node(-5)
        assert data is None
        assert "Invalid node_id" in err

        data, err = client.flood_node("not_an_int")  # type: ignore
        assert data is None
        assert "Invalid node_id" in err

    def test_app_state_handles_empty_payload(self):
        state = AppState()
        assert state.connection == ConnectionStatus.DISCONNECTED
        assert state.has_graph is False
        assert state.get_node(0) is None
        assert state.get_edge(0, 1) is None

        # Updating with empty dict should not crash
        state.update_graph({})
        assert state.has_graph is False
        state.update_sim({})
        assert state.backend_sim.step == 0

    def test_app_state_preserves_zero_distinct_from_missing(self):
        state = AppState()
        sim_payload = {
            "step": 0,
            "ambulances": [],
            "civilians_remaining": [],
            "events": {
                "metrics": {
                    "civilians_rescued": 0,
                    "total_floods": 0,
                }
            }
        }
        state.update_sim(sim_payload)
        metrics = state.backend_sim.metrics
        assert metrics.get("civilians_rescued") == 0
        assert metrics.get("total_floods") == 0
        # Truly missing metric returns None, distinguishable from 0
        assert metrics.get("non_existent_metric") is None

    def test_local_log_ring_buffer(self):
        state = AppState()
        log = state.local_log
        log.max_entries = 10
        for i in range(25):
            log.add(f"Msg {i}", level="info" if i % 2 == 0 else "error", category="TEST")

        entries = log.entries()
        assert len(entries) == 10
        assert entries[-1]["msg"] == "Msg 24"

        errors = log.entries(level_filter="error")
        assert all(e["level"] == "error" for e in errors)

    def test_api_route_and_mutation_validation_f8_f9_f10_f16_f41(self):
        """
        F8/F9/F10/F16/F41: Validate /simulation/route endpoint, 404s for invalid
        node/edge IDs on flood, block, and unblock endpoints.
        """
        from fastapi.testclient import TestClient
        from backend.api.main import app
        with TestClient(app) as client:
            res = client.post('/start').json()
            assert res['message'] == 'Simulation restarted'
            assert res['sim_id']
            response = client.post('/simulation/route', json={'src': 0, 'dst': 1})
            assert response.status_code == 200
            data = response.json()
            assert data['src'] == 0 and data['dst'] == 1
            assert data['reachable'] and data['path'] and data['path_cost'] >= 0
            assert client.post('/simulation/route', json={'src': 99999, 'dst': 1}).status_code == 404
            assert client.post('/simulation/flood_node/99999').status_code == 404
            assert client.post('/simulation/block_road/99999/88888').status_code == 404
            assert client.post('/simulation/unblock_road/99999/88888').status_code == 404

    def test_accessible_flag_and_disconnected_nodes_sync_f27_f35_f48(self):
        """
        F27/F35/F48: Verify node.accessible flag and find_disconnected_nodes()
        update consistently upon edge blocking and unblocking.
        """
        from core.city_graph import CityGraph
        graph = CityGraph()
        # Node 0 connected only to 1
        graph.add_edge(0, 1, 1.0)
        # Node 2 connected to 3
        graph.add_edge(2, 3, 1.0)

        # Node 0 has active neighbor 1
        assert graph.nodes[0].accessible is True

        # Block edge (0, 1) -> node 0 has no active neighbors
        graph.block_road(0, 1)
        assert graph.nodes[0].accessible is False
        assert 0 in graph.find_disconnected_nodes()

        # Unblock edge (0, 1) -> node 0 is accessible again
        graph.unblock_road(0, 1)
        assert graph.nodes[0].accessible is True
        assert 0 not in graph.find_disconnected_nodes()

