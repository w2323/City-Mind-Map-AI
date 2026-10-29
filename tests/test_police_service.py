"""Operational dispatch, patrols, access failures, queues and independent care tasks."""
import random
from types import SimpleNamespace
import pytest
from core.city_graph import CityGraph
from core.event_manager import EventManager
from core.disasters import DisasterManager
from core.ambulance_fleet import AmbulanceFleet
from core.medical_network import MedicalNetwork
from core.air_rescue import AirRescue
from core.police_service import PoliceService,compare_strategies
from core.simulation_engine import Simulation
from config.simulation_config import SimConfig


@pytest.fixture
def world():
    graph=CityGraph()
    graph.nodes={n:graph.nodes[n] for n in range(9)}
    graph.adj={n:[] for n in graph.nodes}
    for n in graph.nodes.values():
        n.risk_level='LOW'
        n.node_type=SimConfig.RESIDENTIAL
    for n in range(8):
        graph.add_edge(n,n+1,1)
    events=EventManager(verbose=False)
    service=PoliceService(graph,events,stations=[0,8],unit_count=2)
    yield graph,events,service
    events.close()


def test_stations_own_real_cars_and_begin_without_reports(world):
    graph,_,service=world
    assert not service.reports and not service.automatic_incidents
    assert len(service.stations)==2 and len(service.units)==2
    assert all(u['position']==u['home'] and u['status']=='AVAILABLE' for u in service.units)


def test_nearest_by_permitted_road_cost_busy_exclusion_and_movement(world):
    graph,_,service=world
    graph.add_edge(8,1,.1)
    first=service.report(1,'THEFT',1,0)
    assert first['unit_id']=='POL-02'  # geographically far, cheapest actual road route
    assert service.units[1]['position']==8  # dispatch never teleports
    second=service.report(7,'VANDALISM',1,0)
    assert second['unit_id']=='POL-01'
    service.advance(1)
    assert service.units[1]['position']==1 and first['police_status']=='ON_SCENE'
    assert first['status']!='RESOLVED'


def test_police_handle_then_return_and_record_arrival_once(world):
    _,_,service=world
    report=service.report(2,'THEFT',1,0)
    service.advance(1)
    assert service.units[0]['position']==1 and report['arrival_step'] is None
    service.advance(2)
    assert report['arrival_step']==2
    service.advance(3)
    assert report['status']=='ON_SCENE'
    service.advance(4)
    assert report['status']=='RESOLVED' and service.units[0]['status']=='RETURNING'
    assert service.units[0]['position']==2
    service.advance(5)
    service.advance(6)
    assert service.units[0]['status']=='AVAILABLE' and service.units[0]['position']==0
    assert service.summary(6)['mean_response_steps']==2
    assert service.summary(6)['police_handled']==1 and service.response_times==[2]


def test_busy_reports_queue_by_severity_and_wait_age(world):
    _,_,service=world
    service.report(1,'THEFT',1,0)
    service.report(7,'THEFT',1,0)
    low=service.report(3,'THEFT',1,0)
    urgent=service.report(4,'DISTURBANCE',3,0)
    assert low['status']==urgent['status']=='QUEUED'
    for step in range(1,5):
        service.advance(step)
    assert urgent['unit_id']=='POL-01' and low['unit_id']=='POL-02'
    assert service.summary(4)['queued']==0


def test_old_reports_gain_priority_to_avoid_starvation(world,monkeypatch):
    _,_,service=world
    monkeypatch.setattr(SimConfig,'POLICE_QUEUE_AGING_STEPS',1)
    service.report(1,'THEFT',1,0)
    service.report(7,'THEFT',1,0)
    old=service.report(3,'THEFT',1,0)
    for step in (1,2,3):
        service.advance(step)
    urgent=service.report(4,'THEFT',3,3)
    service.advance(4)
    assert old['unit_id']=='POL-01' and urgent['unit_id']=='POL-02'


def test_risk_weight_changes_patrol_destination_without_teleporting(world):
    graph,events,_=world
    graph.nodes[2].risk_level='HIGH'
    weighted=PoliceService(graph,events,stations=[0],unit_count=2,strategy='risk_weighted')
    uniform=PoliceService(graph,events,stations=[0],unit_count=2,strategy='uniform')
    weighted.advance(1)
    uniform.advance(1)
    assert weighted.units[1]['target']==2
    assert uniform.units[1]['target']==1
    assert weighted.units[1]['position']==uniform.units[1]['position']==0


def test_gate_unreachable_is_not_busy_and_clear_resumes_response(world):
    graph,events,service=world
    gates=DisasterManager(graph,events)
    gates.unleash(4,1,0)
    report=service.report(4,'THEFT',2,0)
    assert report['status']=='UNREACHABLE' and report['unit_id'] is None
    assert service.summary(0)['available']==2
    gates.clear(1)
    service.refresh(1)
    assert report['status']=='RESPONDING'
    for step in range(2,20):
        service.advance(step)
    assert report['status']=='RESOLVED'


def test_closure_during_response_requeues_without_moving_through_block(world):
    graph,_,service=world
    report=service.report(3,'THEFT',1,0)
    service.advance(1)
    assert service.units[0]['position']==1
    graph.block_road(1,2)
    service.refresh(1)
    assert report['unit_id']=='POL-02'  # another reachable unit takes over
    assert service.units[0]['position']==1
    assert service.units[0]['status']=='RETURNING'
    service.advance(2)
    assert service.units[0]['position']==0


def test_patrols_move_on_roads_preserve_reserves_and_can_be_interrupted(world):
    graph,events,_=world
    service=PoliceService(graph,events,stations=[0,8],unit_count=4)
    service.advance(1)
    assert sum(u['status']=='PATROLLING' for u in service.units)==2
    assert all(u['status']=='AVAILABLE' for u in service.units if u['reserve'])
    prior={u['id']:u['position'] for u in service.units}
    service.advance(2)
    assert any(u['position']!=prior[u['id']] for u in service.units)
    for unit in service.units:
        assert abs(unit['position']-prior[unit['id']])<=1
    patroller=next(u for u in service.units if not u['reserve'])
    report=service.report(patroller['position'],'THEFT',1,2)
    assert report['unit_id']==patroller['id'] and report['police_status']=='ON_SCENE'
    service.configure(2,patrol_enabled=False)
    assert not any(u['status']=='PATROLLING' for u in service.units)


def test_auto_generation_is_optional_seeded_and_does_not_change_model_risk(world):
    graph,events,service=world
    baseline={n:nod.risk_level for n,nod in graph.nodes.items()}
    service.advance(1)
    assert not service.reports
    clone=PoliceService(graph,events,stations=[0,8],unit_count=2)
    for model in (service,clone):
        model.configure(1,automatic_incidents=True,auto_probability=1)
        model.advance(2)
    assert [(r['node_id'],r['kind'],r['severity']) for r in service.reports]==[(r['node_id'],r['kind'],r['severity']) for r in clone.reports]
    assert service.reports[0]['source']=='AUTOMATIC'
    assert {n:nod.risk_level for n,nod in graph.nodes.items()}==baseline


def test_medical_completion_is_independent_and_ambulance_can_cross_gate(world):
    graph,events,_=world
    network=MedicalNetwork(graph,[0],events)
    fleet=AmbulanceFleet(graph,events,centers=[0])
    fleet.network=network
    service=PoliceService(graph,events,fleet,network,stations=[4],unit_count=1)
    report=service.report(4,'INJURY',1,0)
    assert report['police_status']=='ON_SCENE' and report['medical_status']=='RESPONDING'
    for step in (1,2):
        fleet.advance(step)
        service.advance(step)
    assert report['police_status']=='COMPLETE' and report['status']=='WAITING_MEDICAL'
    assert events.metrics.civilians_rescued==0
    for step in (3,4):
        fleet.advance(step)
        service.advance(step)
    assert report['status']=='RESOLVED' and events.metrics.civilians_rescued==1
    gates=DisasterManager(graph,events)
    gates.unleash(6,1,4)
    second=service.report(6,'INJURY',1,4)
    assert second['police_status']=='UNREACHABLE'
    for step in range(5,24):
        fleet.advance(step)
        service.advance(step)
    assert second['medical_status']=='RESOLVED' and second['status']=='UNREACHABLE'


def test_isolated_injury_can_request_real_helicopter_and_ambulance_handoff(world):
    graph,events,_=world
    graph.block_road(3,4)
    network=MedicalNetwork(graph,[0],events)
    fleet=AmbulanceFleet(graph,events,centers=[0])
    fleet.network=network
    air=AirRescue(graph,network,fleet)
    service=PoliceService(graph,events,fleet,network,air,stations=[4],unit_count=1)
    report=service.report(4,'INJURY',1,0)
    assert report['medical_status']=='HELICOPTER_REQUIRED'
    emergency=service.medical_rescue(report['id'],0)
    assert emergency['id']==report['medical_emergency_id']
    for step in range(1,40):
        fleet.advance(step)
        air.advance(step)
        service.advance(step)
        assert air.fuel>=0
        if report['status']=='RESOLVED':
            break
    assert report['status']=='RESOLVED' and events.metrics.civilians_rescued==1


def test_duplicate_invalid_and_bounded_reports(world,monkeypatch):
    _,_,service=world
    service.report(2,'THEFT',1,0)
    with pytest.raises(ValueError,match='active'):
        service.report(2,'THEFT',2,0)
    with pytest.raises(ValueError):
        service.report(1000,'THEFT',1,0)
    with pytest.raises(ValueError):
        service.report(3,'THEFT',True,0)
    monkeypatch.setattr(SimConfig,'POLICE_MAX_REPORTS',1)
    with pytest.raises(ValueError,match='limit'):
        service.report(3,'THEFT',1,0)


def test_station_planning_does_not_teleport_and_finds_unserved_component(world):
    graph,_,service=world
    graph.block_road(3,4)
    # Remove the second station and its unit, leaving nodes 4..8 without a station.
    service.stations=service.stations[:1]
    service.units=service.units[:1]
    positions=[u['position'] for u in service.units]
    plan=service.plan_stations()
    assert plan['additions'][0]['node_id']==6
    assert plan['additions'][0]['gain']==5
    assert positions==[u['position'] for u in service.units]
    service.add_station(6)
    assert len(service.units)==3 and service.covered_nodes()==set(graph.nodes)
    assert service.to_dict(0)['recommendations']['stale']


def test_comparison_is_reproducible_matched_and_does_not_mutate_live_city():
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        before=model.graph.to_dict()
        units=[dict(u) for u in model.state.police.units]
        one=compare_strategies(model.graph,7,30,6)
        two=compare_strategies(model.graph,7,30,6)
        assert one==two
        assert all(r['reported']==6 and r['total_units']==10 for r in one['results'])
        assert model.graph.to_dict()==before and model.state.police.units==units
        assert not model.state.police.reports
    finally:
        model.events.close()

def test_patrol_off_parks_cars_and_dispatch_moves_only_assigned_unit(world):
    graph,events,_=world
    service=PoliceService(graph,events,stations=[0,8],unit_count=6)
    for step in (1,2,3):
        service.advance(step)
    assert any(u['status']=='PATROLLING' for u in service.units)
    positions={u['id']:u['position'] for u in service.units}
    service.configure(3,patrol_enabled=False)
    assert all(u['status']=='AVAILABLE' and not u['path'] and u['target'] is None for u in service.units)
    service.advance(4)
    assert positions=={u['id']:u['position'] for u in service.units}
    target=next(n for n in graph.nodes if n not in positions.values())
    report=service.report(target,'THEFT',1,4)
    assigned=report['unit_id']
    for step in range(5,24):
        service.advance(step)
        assert service.patrol_enabled is False
        assert not any(u['status']=='PATROLLING' for u in service.units)
        assert all(u['position']==positions[u['id']] and not u['path']
                   for u in service.units if u['id']!=assigned)
    assert report['status']=='RESOLVED'
    service.configure(24,patrol_enabled=True)
    service.advance(25)
    assert any(u['status']=='PATROLLING' for u in service.units)


def test_patrol_off_keeps_existing_response_and_clears_patrol_assignments(world):
    graph,events,_=world
    service=PoliceService(graph,events,stations=[0,8],unit_count=4)
    service.advance(1)
    service.advance(2)
    report=service.report(4,'THEFT',3,2)
    responder=next(u for u in service.units if u['id']==report['unit_id'])
    idle_before={u['id']:u['position'] for u in service.units if u is not responder}
    service.configure(2,patrol_enabled=False)
    for step in range(3,25):
        service.advance(step)
        assert all(u['position']==idle_before[u['id']] for u in service.units if u is not responder)
    assert report['status']=='RESOLVED'


def test_returning_car_can_respond_without_finishing_trip_home(world):
    _,_,service=world
    report=service.report(2,'THEFT',1,0)
    for step in range(1,5):
        service.advance(step)
    assert report['status']=='RESOLVED' and service.units[0]['status']=='RETURNING'
    new=service.report(3,'THEFT',1,4)
    assert new['unit_id']=='POL-01'  # one road away, not the idle car five roads away
    assert service.units[0]['position']==2
    service.advance(5)
    assert new['arrival_step']==5


def test_car_cut_off_from_home_can_still_respond_in_its_component(world):
    graph,_,service=world
    service.report(3,'THEFT',1,0)
    for step in range(1,6):
        service.advance(step)
    graph.block_road(1,2)
    service.refresh(5)
    assert service.units[0]['status']=='BLOCKED'
    report=service.report(4,'THEFT',1,5)
    assert report['unit_id']=='POL-01'


def test_all_traversed_patrol_nodes_count_as_visits(world):
    graph,events,_=world
    graph.nodes[4].risk_level='HIGH'
    service=PoliceService(graph,events,stations=[0],unit_count=2)
    unit=service.units[1]
    unit.update(status='PATROLLING',phase='PATROLLING',target=4,path=[0,1,2,3,4])
    service.advance(1)
    assert unit['position']==1 and service.last_visited[1]==1


def test_blocked_injury_road_response_can_switch_to_helicopter(world):
    graph,events,_=world
    network=MedicalNetwork(graph,[0],events)
    fleet=AmbulanceFleet(graph,events,centers=[0])
    fleet.network=network
    air=AirRescue(graph,network,fleet)
    service=PoliceService(graph,events,fleet,network,air,stations=[4],unit_count=1)
    report=service.report(6,'INJURY',1,0)
    original=report['medical_emergency_id']
    fleet.advance(1)
    service.advance(1)
    graph.block_road(3,4)
    network.refresh()
    fleet.replan()
    service.refresh(1)
    assert report['medical_status']=='HELICOPTER_REQUIRED'
    assert next(e for e in fleet.emergencies if e['id']==original)['status']=='ABORTED'
    assert events.metrics.civilians_rescued==0
    # The old base itself lost road support. Rebase physically before takeoff.
    if air.relocation_plan()['required']:
        air.relocate(1)
        for tick in range(2,15):
            air.advance(tick)
            if air.status=='READY':
                break
    service.medical_rescue(report['id'],1)
    for step in range(2,55):
        fleet.advance(step)
        air.advance(step)
        service.advance(step)
        if report['status']=='RESOLVED':
            break
    assert report['status']=='RESOLVED' and events.metrics.civilians_rescued==1

def test_simulation_horizon_does_not_freeze_police_return_after_case_resolution():
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        police=model.state.police
        police.configure(0,patrol_enabled=False)
        home=police.stations[0]['node_id']
        target=next(iter(model.graph.get_neighbors(home)))
        report=police.report(target,'THEFT',1,0)
        for _ in range(20):
            model.step_forward()
            if report['status']=='RESOLVED':
                break
        unit=next(u for u in police.units if u['id']==report['unit_id'])
        assert unit['status']=='RETURNING' and unit['position']!=unit['home']
        model.state.max_steps=model.state.step+1
        horizon=model.state.max_steps
        model.step_forward()
        assert model.state.max_steps>horizon and not model.state.is_complete
        for _ in range(20):
            if unit['status']=='AVAILABLE':
                break
            model.step_forward()
        assert unit['position']==unit['home'] and unit['status']=='AVAILABLE'
    finally:
        model.events.close()
