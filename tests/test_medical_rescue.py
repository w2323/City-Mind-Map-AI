"""Road-cut coverage, facility planning, and complete fuel-safe air handoffs."""
import math
import random
import pytest
from core.city_graph import CityGraph
from core.event_manager import EventManager
from core.medical_network import MedicalCenterPlanner, MedicalNetwork
from core.ambulance_fleet import AmbulanceFleet
from core.air_rescue import AirRescue
from core.simulation_engine import Simulation
from config.simulation_config import SimConfig


@pytest.fixture
def rescue():
    graph=CityGraph()
    graph.nodes={n: graph.nodes[n] for n in range(9)}
    graph.adj={n: [] for n in graph.nodes}
    for n in graph.nodes.values():
        n.risk_level='LOW'
        n.node_type=SimConfig.RESIDENTIAL
    graph.nodes[0].node_type=SimConfig.HOSPITAL
    for a,b in [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7)]:
        graph.add_edge(a,b,1)
    events=EventManager(verbose=False)
    network=MedicalNetwork(graph,[0],events)
    fleet=AmbulanceFleet(graph,events,centers=[0])
    fleet.network=network
    air=AirRescue(graph,network,fleet)
    yield graph,network,fleet,air
    events.close()


def tick(fleet,air,step):
    fleet.advance(step)
    air.advance(step)


def test_ga_searches_city_and_prioritises_total_reach_over_distance(rescue):
    graph,_,_,_=rescue
    planner=MedicalCenterPlanner(graph,count=2,rng=random.Random(3),generations=6)
    sites=planner.run()
    assert 8 in sites  # isolated component needs a center to attain full coverage
    assert any(n not in (0,8) for n in sites)  # searches beyond the original hospital
    assert planner.score(sites)[0]==0
    assert planner.score([0,1])[0]==1


def test_ga_reports_partial_coverage_when_centers_cannot_cover_all_components(rescue):
    graph,_,_,_=rescue
    planner=MedicalCenterPlanner(graph,count=1,rng=random.Random(3),generations=4)
    sites=planner.run()
    assert sites[0]!=8 and planner.score(sites)[0]==1
    assert planner.is_infeasible and planner.best_fitness>=1e9


def test_road_cut_detects_entire_tail_and_recommends_component_medoid(rescue):
    graph,network,fleet,_=rescue
    graph.block_road(3,4)
    network.refresh()
    assert network.reachable=={0,1,2,3}
    assert network.notifications[0]['node_ids']==[4,5,6,7]
    best=network.recommendations[0]
    assert best['covered_nodes']==[4,5,6,7]
    assert best['node_id'] in (5,6) and best['gain']==4
    assert 7 not in fleet.to_dict()[0]['reachable_nodes']
    old_count=len(network.notifications)
    network.refresh()
    assert len(network.notifications)==old_count  # read polling never duplicates warnings
    graph.unblock_road(3,4)
    network.refresh()
    assert 7 in network.reachable
    assert network.notifications[-1]['kind']=='info'


def test_air_requires_road_disconnection_not_simply_busy_units(rescue):
    _,_,fleet,air=rescue
    fleet.dispatch(6,0)
    assert not air.eligibility(7)['required']
    with pytest.raises(ValueError,match='Use an ambulance'):
        air.dispatch(7,0)
    assert air.eligibility(8)['required']


def test_full_flight_delivers_to_hospital_then_returns_to_nearest_building(rescue):
    _,network,fleet,air=rescue
    emergency=air.dispatch(8,0)
    travelled=0
    phases=set()
    expected_pad=None
    for step in range(1,40):
        old=air.position
        phases.add(air.status)
        tick(fleet,air,step)
        travelled+=air.distance(old,air.position)
        assert air.fuel>=0
        if emergency['resolved_step']==step:
            assert air.position==air.point(emergency['hospital_id'])
            assert emergency['hospital_id']==0 and not air.carrying
            expected_pad=air.nearest(air.position)
            assert air.status=='RETURNING'
        if emergency['status']=='RESOLVED' and air.status=='READY':
            break
    assert {'OUTBOUND','TO_HOSPITAL','RETURNING'} <= phases
    assert air.landed_node==expected_pad and air.landed_node not in network.centers
    assert emergency['ambulance_id'] is None
    assert all(u['status']=='AVAILABLE' and u['position']==u['depot'] for u in fleet.units)
    assert math.isclose(air.capacity-air.fuel,travelled*air.burn,abs_tol=1e-8)
    assert fleet.events.metrics.civilians_rescued==1
    air.refuel()
    assert air.fuel==air.capacity


def test_insufficient_fuel_prevents_launch_and_airborne_refuel_is_rejected(rescue):
    _,_,_,air=rescue
    air.fuel=20
    with pytest.raises(ValueError,match='Refuel'):
        air.dispatch(8,0)
    assert air.status=='READY' and not air.fleet.emergencies
    air.refuel()
    air.dispatch(8,0)
    with pytest.raises(ValueError,match='after landing'):
        air.refuel()


def test_low_fuel_diverts_before_consuming_landing_reserve(rescue):
    _,network,fleet,air=rescue
    air.dispatch(8,0)
    air.fuel=20  # simulate a low-fuel reading after a permitted launch
    before=tuple(air.position)
    air.advance(1)
    assert air.status=='RETURNING' and air.diversions==1
    assert air.position==before and air.fuel==20
    for step in range(2,20):
        tick(fleet,air,step)
        assert air.fuel>=0
        if air.status=='READY':
            break
    assert air.status=='READY' and air.landed_node in network.reachable
    assert fleet.emergencies[0]['status']=='ABORTED'
    assert fleet.events.metrics.civilians_rescued==0


def test_runtime_landing_changes_never_turn_a_hospital_into_a_parking_pad(rescue):
    graph,network,fleet,air=rescue
    with pytest.raises(ValueError,match='road'):
        air.set_landings([8])
    with pytest.raises(ValueError,match='hospital'):
        air.set_landings([0])
    air.set_landings([6])
    emergency=air.dispatch(8,0)
    for step in range(1,20):
        tick(fleet,air,step)
        if air.carrying:
            break
    assert air.status=='TO_HOSPITAL' and air.target==0
    air.set_landings([5])
    assert air.target==0
    graph.block_road(3,4)
    for step in range(20,60):
        tick(fleet,air,step)
        if emergency['status']=='RESOLVED' and air.status=='READY':
            break
    assert emergency['status']=='RESOLVED'
    assert air.landed_node==1 and air.landed_node not in network.centers


def test_busy_ambulance_queues_handoff_and_later_picks_up_patient(rescue):
    _,_,fleet,air=rescue
    air.set_landings([7])
    fleet.dispatch(7,0)
    emergency=air.dispatch(8,0)
    for step in range(1,50):
        tick(fleet,air,step)
        if emergency['status']=='RESOLVED' and air.status=='READY':
            break
    assert emergency['status']=='RESOLVED'
    assert fleet.events.metrics.civilians_rescued==2


def test_road_loss_does_not_prevent_direct_air_delivery_to_hospital(rescue):
    graph,network,fleet,air=rescue
    emergency=air.dispatch(8,0)
    for step in range(1,20):
        tick(fleet,air,step)
        if air.status=='TO_HOSPITAL':
            break
    graph.block_road(3,4)
    for step in range(20,60):
        tick(fleet,air,step)
        if emergency['status']=='RESOLVED' and air.status=='READY':
            break
    assert emergency['hospital_id']==0 and emergency['status']=='RESOLVED'
    assert emergency['ambulance_id'] is None and air.landed_node==1


def test_active_air_mission_extends_simulation_horizon(monkeypatch):
    model=Simulation(seed=42,verbose=False)
    monkeypatch.setattr(SimConfig,'FLOOD_PROBABILITY',0)
    try:
        model.initialize()
        target=next(n for n in model.graph.nodes if n not in model.state.medical_network.centers)
        model.trigger_flood_at_node(target)
        model.state.air_rescue.dispatch(target,0)
        model.state.max_steps=1
        model.step_forward()
        assert not model.state.is_complete
        assert model.state.max_steps>1
    finally:
        model.events.close()


def test_aborted_air_attempt_is_not_reported_as_all_rescued(monkeypatch):
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        model.trigger_flood_at_node(224)
        model.state.air_rescue.dispatch(224,0)
        model.state.air_rescue.fuel=20
        model.state.air_rescue.advance(1)
        state=model.state.to_dict()
        assert state['mission_status']=='PARTIAL'
        assert state['router']['civilians_deferred']==[224]
        assert state['events']['metrics']['civilians_rescued']==0
        assert all(n.population==20 for n in model.graph.get_nodes_of_type(SimConfig.HOSPITAL))
        assert all(n.to_dict()['risk_features']['population_density']==round(n.population/200,6) for n in model.graph.nodes.values())
    finally:
        model.events.close()
