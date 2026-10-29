"""Gate exposure, medical dispatch and patient-preserving physical relocation."""
import math
import pytest
from core.city_graph import CityGraph
from core.event_manager import EventManager
from core.disasters import DisasterManager
from core.medical_network import MedicalNetwork
from core.ambulance_fleet import AmbulanceFleet
from core.air_rescue import AirRescue
from core.police_service import PoliceService
from config.simulation_config import SimConfig


@pytest.fixture
def world():
    graph=CityGraph()
    graph.nodes={n:graph.nodes[n] for n in [*range(15),22]}
    graph.adj={n:[] for n in graph.nodes}
    for n in graph.nodes.values():
        n.risk_level='LOW'
        n.node_type=SimConfig.RESIDENTIAL
    for n in range(14):
        graph.add_edge(n,n+1,1)
    events=EventManager(verbose=False)
    network=MedicalNetwork(graph,[0,14],events)
    fleet=AmbulanceFleet(graph,events,[0,14])
    fleet.network=network
    fleet.disasters=DisasterManager(graph,events)
    air=AirRescue(graph,network,fleet)
    yield graph,network,fleet,air
    events.close()


@pytest.mark.parametrize('kind,medical',[('INJURY',False),('THEFT',True)])
def test_police_and_real_ambulance_dispatched_together(world,kind,medical):
    graph,network,fleet,air=world
    police=PoliceService(graph,fleet.events,fleet,network,air,stations=[3,11],unit_count=2)
    police.configure(0,patrol_enabled=False)
    report=police.report(5,kind,2,0,medical=medical)
    assert report['police_status']=='RESPONDING'
    assert report['medical_status']=='RESPONDING'
    assert report['medical_emergency_id']==fleet.emergencies[0]['id']
    assert any(u['path'] and u['target']==5 for u in fleet.units)
    for step in range(1,30):
        fleet.advance(step)
        police.advance(step)
        if report['status']=='RESOLVED':
            break
    assert report['police_status']=='COMPLETE' and report['medical_status']=='RESOLVED'
    assert fleet.events.metrics.civilians_rescued==1


@pytest.mark.parametrize('exposure',[0,5])
def test_depot_or_vehicle_exposure_disables_and_clear_restores(world,exposure):
    _,network,fleet,_=world
    unit=fleet.units[0]
    unit['position']=5
    fleet.disasters.unleash(exposure,1,0)
    fleet.replan()
    assert unit['status']=='OUT_OF_SERVICE'
    assert fleet.units[1]['status']=='AVAILABLE'
    assert fleet.dispatch(6,0)['ambulance_id']=='AMB-02'
    notices=len(network.notifications)
    for _ in range(3):
        fleet.to_dict()
    assert len(network.notifications)==notices
    assert any('AMB-01 is out of service' in n['message'] for n in network.notifications)
    fleet.disasters.clear(1)
    fleet.replan()
    assert unit['status']=='AVAILABLE' and unit['position']==5


def test_active_assignment_survives_outage_without_false_rescue(world):
    _,_,fleet,_=world
    emergency=fleet.dispatch(4,0)
    fleet.advance(1)
    unit=fleet.units[0]
    fleet.disasters.unleash(0,1,1)
    for step in range(2,5):
        fleet.advance(step)
    assert unit['status']=='OUT_OF_SERVICE' and unit['position']==1
    assert emergency['status']=='RESPONDING' and unit['emergency_id']==emergency['id']
    assert fleet.events.metrics.civilians_rescued==0
    fleet.disasters.clear(5)
    for step in range(5,15):
        fleet.advance(step)
    assert emergency['status']=='RESOLVED' and fleet.events.metrics.civilians_rescued==1


def test_unaffected_ambulance_keeps_gate_road_privilege(world):
    _,_,fleet,_=world
    fleet.disasters.unleash(7,1,0)
    fleet.replan()
    emergency=fleet.dispatch(7,0)
    for step in range(1,25):
        fleet.advance(step)
    assert emergency['status']=='RESOLVED'
    assert all(u['status']=='AVAILABLE' for u in fleet.units)


def test_overlapping_gates_do_not_reenable_disabled_unit(world):
    _,_,fleet,_=world
    fleet.disasters.unleash(0,1,0)
    fleet.replan()
    fleet.disasters.unleash(1,1,0)
    fleet.replan()
    assert len(fleet.units[0]['gate_ids'])==2
    fleet.advance(1)
    assert fleet.units[0]['status']=='OUT_OF_SERVICE'
    fleet.disasters.clear(2)
    fleet.replan()
    assert fleet.units[0]['status']=='AVAILABLE'


def test_airborne_loss_of_every_medical_center_lands_without_losing_patient(world):
    _,_,fleet,air=world
    emergency=air.dispatch(22,0)
    for step in range(1,10):
        air.advance(step)
        if air.carrying:
            break
    assert air.carrying
    fleet.disasters.unleash(air.home,8,step)
    for tick in range(step+1,step+10):
        fleet.advance(tick)
        air.advance(tick)
        assert air.fuel>=0
        if air.landed_node is not None:
            break
    assert air.landed_node is not None and air.carrying
    assert emergency['status']=='WAITING_HOSPITAL'
    assert fleet.events.metrics.civilians_rescued==0
    for tick in range(20,23):
        air.advance(tick)
    fleet.disasters.clear(23)
    for tick in range(23,80):
        fleet.advance(tick)
        air.advance(tick)
        if emergency['status']=='RESOLVED':
            break
    assert emergency['status']=='RESOLVED' and fleet.events.metrics.civilians_rescued==1


def test_relocation_requires_operator_and_charges_every_distance(world):
    _,network,fleet,air=world
    start=air.home
    fleet.disasters.unleash(start,1,0)
    plan=air.to_dict()['relocation']
    assert plan['required'] and plan['can_relocate']
    assert len(air.to_dict()['landing_sites'])>=3
    before=air.position
    air.advance(1)
    assert air.position==before and air.fuel==air.capacity
    notices=len(network.notifications)
    air.to_dict(); air.to_dict()
    assert len(network.notifications)==notices
    target=air.relocate(1)
    assert target!=start and air.position==before and air.landed_node is None
    travelled=0
    for step in range(2,30):
        old=air.position
        air.advance(step)
        travelled+=air.distance(old,air.position)
        assert air.fuel>=0
        if air.status=='READY':
            break
    assert air.landed_node==target and not air.unsafe(target)
    assert math.isclose(air.capacity-air.fuel,travelled*air.burn,abs_tol=1e-8)


def test_no_safe_pad_or_insufficient_fuel_blocks_relocation_cleanly(world):
    _,_,fleet,air=world
    fleet.disasters.unleash(air.home,8,0)
    data=air.to_dict()
    assert data['relocation_required'] and not data['relocation']['can_relocate']
    assert not data['landing_nodes'] and data['required_landing_fuel'] is None
    with pytest.raises(ValueError,match='No safe'):
        air.relocate(0)
    assert air.landed_node==air.home and air.fuel==air.capacity
    fleet.disasters.clear(0)
    fleet.disasters.unleash(air.home,1,0)
    air.fuel=1
    assert not air.to_dict()['relocation']['can_relocate']
    air.refuel()
    assert air.to_dict()['relocation']['can_relocate']


def test_relocation_retains_patient_until_direct_hospital_delivery_is_possible(world):
    _,_,fleet,air=world
    emergency=air.dispatch(22,0)
    air.advance(1)
    assert air.carrying
    fleet.disasters.unleash(0,1,1)
    fleet.disasters.unleash(14,1,1)
    for step in range(2,15):
        air.advance(step)
        if air.status=='WAITING_HOSPITAL':
            break
    assert air.carrying and emergency['status']=='WAITING_HOSPITAL'
    fleet.disasters.unleash(air.landed_node,1,step)
    before=air.position
    air.relocate(step)
    assert air.position==before and air.carrying
    for tick in range(step+1,30):
        air.advance(tick)
        if air.landed_node is not None:
            break
    assert air.carrying and emergency['status']!='RESOLVED'
    assert fleet.events.metrics.civilians_rescued==0
    fleet.disasters.clear(30)
    for tick in range(30,80):
        fleet.advance(tick)
        air.advance(tick)
        if emergency['status']=='RESOLVED' and air.status=='READY':
            break
    assert emergency['status']=='RESOLVED' and fleet.events.metrics.civilians_rescued==1
    assert not air.carrying and air.landed_node not in air.network.centers


def test_new_gate_during_relocation_retargets_without_teleporting(world):
    _,_,fleet,air=world
    fleet.disasters.unleash(air.home,1,0)
    target=air.relocate(0)
    air.advance(1)
    before=air.position
    fleet.disasters.unleash(target,1,1)
    air.advance(2)
    assert air.target!=target
    assert air.distance(before,air.position)<=2.01
    for step in range(3,35):
        air.advance(step)
        if air.status=='READY':
            break
    assert air.status=='READY' and not air.unsafe(air.landed_node) and air.fuel>=0


def test_all_bases_are_real_buildings_and_never_hospitals(world):
    graph,network,_,air=world
    before={n:nod.node_type for n,nod in graph.nodes.items()}
    assert len(air.default_landings)==SimConfig.HELICOPTER_PAD_COUNT
    assert all(air.is_building(n) for n in air.to_dict()['permanent_landings'])
    assert not set(air.to_dict()['landing_nodes']) & set(network.centers)
    with pytest.raises(ValueError,match='hospital'):
        air.set_landings([network.centers[0]])
    assert before=={n:nod.node_type for n,nod in graph.nodes.items()}


def test_relocation_chooses_closest_safe_building_even_when_ambulances_are_disabled(world):
    _,_,fleet,air=world
    fleet.disasters.unleash(air.home,1,0)
    for center in fleet.network.centers:
        fleet.disasters.unleash(center,1,0)
    fleet.replan()
    assert all(u['status']=='OUT_OF_SERVICE' for u in fleet.units)
    expected=min(air.landing_nodes(),key=lambda n:(air.distance(air.position,air.point(n)),n))
    assert air.relocate(0)==expected and expected not in air.network.centers


def test_nearest_hospital_destroyed_after_pickup_causes_delivery_to_next_safe_hospital(world):
    graph,_,fleet,air=world
    graph.nodes[22].col=2
    emergency=air.dispatch(22,0)
    assert emergency['hospital_id']==0
    for step in range(1,20):
        air.advance(step)
        if air.carrying:
            break
    fleet.disasters.unleash(0,1,step)
    air.advance(step+1)
    assert air.status=='TO_HOSPITAL' and air.target==14
    for tick in range(step+2,60):
        air.advance(tick)
        if air.status=='READY':
            break
    assert emergency['hospital_id']==14 and emergency['status']=='RESOLVED'
    assert fleet.events.metrics.civilians_rescued==1 and air.landed_node not in air.network.centers


def test_takeoff_budgets_the_final_hospital_to_building_leg(world):
    _,_,_,air=world
    air.low_pct=0
    plan=air.hospital_plan(air.point(22))
    outbound=air.distance(air.position,air.point(22))*air.burn
    air.fuel=outbound+plan[0]*air.burn+air.reserve
    assert not air.eligibility(22)['can_dispatch']
    with pytest.raises(ValueError,match='Refuel'):
        air.dispatch(22,0)
    assert not air.fleet.emergencies
