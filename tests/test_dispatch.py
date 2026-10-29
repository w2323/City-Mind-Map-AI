"""Explicit depot dispatch regressions; dispatch uses real road cost without a coverage radius."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from core.city_graph import CityGraph
from core.event_manager import EventManager
from core.ambulance_fleet import AmbulanceFleet
from core.simulation_engine import Simulation
from config.simulation_config import SimConfig


@pytest.fixture
def fleet():
    graph=CityGraph()
    for n in graph.nodes.values():
        n.risk_level='LOW'
    graph.nodes[0].node_type=SimConfig.DEPOT
    graph.nodes[4].node_type=SimConfig.DEPOT
    for a,b,cost in [(0,1,1),(1,2,1),(2,3,1),(3,4,1),(0,5,.2),(5,6,.2)]:
        graph.add_edge(a,b,cost)
    events=EventManager(verbose=False)
    result=AmbulanceFleet(graph,events)
    yield result
    events.close()


def test_no_default_emergencies_and_one_unit_at_each_depot(fleet):
    assert not fleet.emergencies
    assert len(fleet.units)==2
    assert all(u['status']=='AVAILABLE' and u['position']==u['depot'] for u in fleet.units)


def test_nearest_by_road_cost_and_busy_units_are_excluded(fleet):
    first=fleet.dispatch(1,0)
    assert first['ambulance_id']=='AMB-01'
    second=fleet.dispatch(2,0)
    assert second['ambulance_id']=='AMB-02'
    with pytest.raises(ValueError,match='No available'):
        fleet.dispatch(6,0)


def test_no_radius_and_all_road_reachable_nodes_are_served(fleet):
    assert all('radius' not in u for u in fleet.to_dict())
    assert 6 in fleet.to_dict()[0]['reachable_nodes']
    assert fleet.dispatch(6,0)['ambulance_id']=='AMB-01'


def test_arrival_resolves_and_unit_returns_before_becoming_available(fleet):
    event=fleet.dispatch(2,0)
    unit=fleet.units[0]
    assert unit['status']=='RESPONDING'
    fleet.advance(1)
    assert event['status']=='RESPONDING' and unit['position']==1
    fleet.advance(2)
    assert event['status']=='RESOLVED' and unit['status']=='RETURNING'
    assert fleet.events.metrics.civilians_rescued==1
    fleet.advance(3)
    fleet.advance(4)
    assert unit['status']=='AVAILABLE' and unit['position']==0
    assert fleet.events.metrics.civilians_rescued==1


def test_duplicate_and_unreachable_emergencies_do_not_add_records(fleet):
    fleet.dispatch(2,0)
    with pytest.raises(ValueError,match='already responding'):
        fleet.dispatch(2,0)
    with pytest.raises(ValueError,match='No available'):
        fleet.dispatch(224,0)
    assert len(fleet.emergencies)==1
    with pytest.raises(KeyError):
        fleet.dispatch(9999,0)


def test_blocked_unit_waits_and_restored_roads_resume(fleet):
    event=fleet.dispatch(2,0)
    fleet.graph.block_road(0,1)
    fleet.advance(1)
    assert fleet.units[0]['status']=='BLOCKED'
    assert fleet.units[0]['position']==0 and event['status']=='RESPONDING'
    fleet.graph.unblock_road(0,1)
    fleet.advance(2)
    assert fleet.units[0]['status']=='RESPONDING' and fleet.units[0]['position']==1
    fleet.advance(3)
    assert event['status']=='RESOLVED'


def test_emergency_at_depot_resolves_without_getting_stuck(fleet):
    event=fleet.dispatch(0,0)
    assert event['status']=='RESOLVED'
    assert fleet.units[0]['status']=='AVAILABLE'
    assert fleet.events.metrics.avg_response_time==0


def test_full_simulation_starts_idle_and_ga_does_not_teleport_fleet():
    model=Simulation(seed=42,verbose=False,automatic_events=False)
    try:
        model.initialize()
        original=[u['position'] for u in model.state.fleet.units]
        state=model.state.to_dict()
        assert state['mission_status']=='IDLE'
        assert not state['civilians_remaining'] and not state['active_routes'] and not state['emergencies']
        assert state['router']['current_pos'] is None
        for _ in range(5):
            model.step_forward()
        assert original==[u['position'] for u in model.state.fleet.units]
        assert model.state.optimized_placements
    finally:
        model.events.close()
