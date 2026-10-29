"""Integration regressions for the shared prototype backend."""
import math
import sys
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api import main as api
from core.simulation_engine import Simulation
from core.city_graph import CityGraph
from challenges.challenge4 import AStarRouter
from challenges.challenge3 import GAambulancePlacer
from challenges.challenge2 import build_road_network, find_bridges
from config.simulation_config import SimConfig


@pytest.fixture
def client(monkeypatch):
    api._cancel.set()
    api._resume.set()
    if api._worker:
        api._worker.join(3)
    model = Simulation(seed=0, verbose=False)
    for a, b in [(0, 1), (1, 2), (2, 3), (0, 3)]:
        model.graph.add_edge(a, b, 1)
    for n in model.graph.nodes.values():
        n.risk_level = 'LOW'
    model.graph.nodes[0].node_type = SimConfig.HOSPITAL
    model.graph.nodes[1].node_type = SimConfig.DEPOT
    model.graph.nodes[2].node_type = SimConfig.RESIDENTIAL
    model.graph.nodes[3].node_type = SimConfig.RESIDENTIAL
    model.state.ambulances = [0, 1]
    model.state.router = AStarRouter(model.graph)
    model._setup_router_callbacks()
    model.state.router.set_mission(0, [2, 3])
    model.state.is_initialized = True
    monkeypatch.setattr(api, 'sim', model)
    monkeypatch.setattr(api, '_revision', 0)
    monkeypatch.setattr(api, '_job', {'status': 'idle'})
    monkeypatch.setattr(SimConfig, 'GA_GENERATIONS', 8)
    monkeypatch.setattr(SimConfig, 'GA_POP_SIZE', 4)
    with TestClient(api.app) as connection:
        yield connection


def test_unreachable_routes_serialize_and_do_not_leak_observers(client):
    graph = api.sim.graph
    sizes = [len(graph._block_observers), len(graph._unblock_observers), len(graph._risk_observers)]
    for _ in range(5):
        result = client.post('/simulation/route', json={'src': 0, 'dst': 224})
        assert result.status_code == 200
        assert result.json()['path_cost'] is None
        assert result.json()['reachable'] is False
    assert sizes == [len(graph._block_observers), len(graph._unblock_observers), len(graph._risk_observers)]
    state = client.get('/state')
    assert state.status_code == 200  # infinite initial GA fitness also serializes
    assert state.json()['events']['metrics']['ga_best_fitness'] is None


@pytest.mark.parametrize('payload', [{'src': True, 'dst': 1}, {'src': '0', 'dst': 1}, {'src': -1, 'dst': 1}, {'src': 0, 'dst': 1, 'extra': 2}])
def test_strict_route_validation(client, payload):
    assert client.post('/simulation/route', json=payload).status_code == 422


def test_flood_snapshot_and_restore(client):
    first = client.post('/simulation/flood_node/2').json()
    state = first['state']
    assert state['step'] == 0
    assert state['events']['metrics']['total_floods'] == 1
    assert state['events']['metrics']['total_edges_blocked'] == first['edges_blocked'] == 2
    assert state['analysis']['deadZones'] == 1
    assert not state['graph']['nodes'][2]['accessible']
    second = client.post('/simulation/flood_node/2').json()
    assert not second['flooded']
    assert second['state']['events']['metrics']['total_floods'] == 1
    restored = client.post('/simulation/unblock_road/1/2').json()['state']
    assert restored['graph']['nodes'][2]['accessible']
    assert restored['events']['metrics']['total_edges_blocked'] == 1
    assert restored['active_routes'] == restored['router']['current_path']


def test_step_limit_is_truthful_and_duration_stops(client):
    api.sim.state.max_steps = 1
    assert client.post('/simulation/step').json()['stepped']
    assert api.sim.events.metrics.simulation_end_time > 0
    assert not client.post('/simulation/step').json()['stepped']
    assert api.sim.state.step == 1


def test_concurrent_steps_are_serialized(client):
    api.sim.state.max_steps = 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: client.post('/simulation/step'), range(8)))
    assert all(r.status_code == 200 for r in results)
    assert sum(r.json()['stepped'] for r in results) == 4
    assert api.sim.state.step == 4


def test_browser_mutations_reject_untrusted_origin(client):
    assert client.post('/simulation/step', headers={'Origin': 'https://untrusted.example'}).status_code == 403
    assert api.sim.state.step == 0
    assert client.post('/simulation/step', headers={'Origin': 'http://localhost:5173'}).status_code == 200


def test_export_and_ambulance_rankings(client):
    result = client.get('/simulation/ambulance_routes/2').json()
    assert result['best']['src'] == 1
    assert result['best']['path_cost'] == 1
    assert client.get('/simulation/ambulance_routes/99999').status_code == 404
    csv = client.get('/metrics/export')
    assert csv.status_code == 200 and 'text/csv' in csv.headers['content-type']
    assert 'sim_id,step,metric,value' in csv.text
    assert 'coveragePct' in csv.text


def wait_job(client, terminal):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get('/state').json()['optimization']
        if job['status'] in terminal:
            return job
        time.sleep(.01)
    pytest.fail('Job did not finish')


def test_real_optimization_commits_and_limits_work(client):
    assert client.post('/simulation/optimization/start', json={'runs': 9999}).status_code == 422
    response = client.post('/simulation/optimization/start', json={'runs': 2})
    assert response.status_code == 200
    job = wait_job(client, {'completed', 'failed'})
    assert job['status'] == 'completed'
    assert job['run'] == 2 and job['generation'] == 8
    assert job['fitness'] is not None
    assert api.sim.state.ambulances == job['positions']
    assert api._revision == 1


def test_paused_job_cancels_on_graph_mutation(client, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    original = GAambulancePlacer.run
    def slow_run(self, progress=None):
        entered.set()
        release.wait(3)
        return original(self, progress)
    monkeypatch.setattr(GAambulancePlacer, 'run', slow_run)
    assert client.post('/simulation/optimization/start', json={'runs': 1}).status_code == 200
    assert entered.wait(2)
    try:
        assert client.post('/simulation/optimization/pause').status_code == 200
        assert client.get('/state').json()['optimization']['status'] == 'paused'
        positions = list(api.sim.state.ambulances)
        client.post('/simulation/block_road/0/1')
        release.set()
        job = wait_job(client, {'cancelled'})
        assert job['status'] == 'cancelled'
        assert api.sim.state.ambulances == positions
    finally:
        release.set()


def test_target_at_current_position_is_rescued():
    router = AStarRouter(CityGraph())
    router.set_mission(0, [0])
    router.advance_one_step(1)
    assert router.visited == [0]
    assert not router.civilians


def test_cheap_long_roads_keep_astar_optimal():
    graph = CityGraph()
    graph.add_edge(0, 1, 1)
    graph.add_edge(0, 224, .1)
    graph.add_edge(224, 1, .1)
    router = AStarRouter(graph)
    assert router.astar(0, 1) == [0, 224, 1]


@pytest.mark.parametrize('cost', [-1, 0, math.inf, math.nan])
def test_invalid_road_costs_rejected(cost):
    with pytest.raises(ValueError):
        CityGraph().add_edge(0, 1, cost)


def test_seeded_simulations_are_independent():
    a, b = Simulation(seed=0, verbose=False), Simulation(seed=0, verbose=False)
    try:
        a.initialize()
        b.initialize()
        assert a.graph.to_dict() == b.graph.to_dict()
        assert a.state.ambulances == b.state.ambulances
        assert not find_bridges(a.graph)
        for _ in range(3):
            a.step_forward()
            b.step_forward()
        assert a.graph.to_dict() == b.graph.to_dict()
    finally:
        a.events.close()
        b.events.close()
