"""Exercise medical-center construction and air-rescue rules through HTTP."""
import pytest
from fastapi.testclient import TestClient
from backend.api import main as api
from core.simulation_engine import Simulation
from config.simulation_config import SimConfig


def test_gate_outages_and_assisted_relocation_through_http(client):
    initial=client.get('/state').json()
    home=initial['air_rescue']['landed_node']
    assert len(initial['air_rescue']['landing_sites'])>1
    assert all('radius' not in u for u in initial['fleet'])
    assert client.post('/simulation/ambulances/AMB-01/radius',json={'radius':3}).status_code==404
    assert client.post('/simulation/helicopter/relocate').status_code==409
    result=client.post('/simulation/disasters/gate',json={'node_id':home,'intensity':1})
    assert result.status_code==200
    state=result.json()['state']
    assert state['air_rescue']['relocation']['can_relocate']
    assert any('Assistant required' in n['message'] for n in state['medical_network']['notifications'])
    relocated=client.post('/simulation/helicopter/relocate')
    assert relocated.status_code==200
    flight=relocated.json()['state']['air_rescue']
    assert flight['status']=='RELOCATING' and flight['position']==initial['air_rescue']['position']
    for _ in range(25):
        state=client.post('/simulation/step').json()['state']
        if state['air_rescue']['status']=='READY':
            break
    assert state['air_rescue']['landed_node']!=home
    assert 0<state['air_rescue']['fuel']<100
    depot=state['fleet'][0]['depot']
    state=client.post('/simulation/disasters/gate',json={'node_id':depot,'intensity':1}).json()['state']
    assert state['fleet'][0]['status']=='OUT_OF_SERVICE'
    assert any('AMB-01 is out of service' in n['message'] for n in state['medical_network']['notifications'])
    restored=client.post('/simulation/disasters/gates/clear').json()['state']
    assert restored['fleet'][0]['status']=='AVAILABLE'
    assert not restored['air_rescue']['relocation_required']


def test_all_services_exposed_returns_json_and_blocks_unsafe_takeoff(client):
    state=client.post('/simulation/disasters/gate',json={'node_id':112,'intensity':8}).json()['state']
    assert state['dispatch_summary']['out_of_service']==len(state['fleet'])
    # Independent building pads may survive even when every hospital is affected.
    assert not state['air_rescue']['hospital_nodes']
    assert client.post('/simulation/helicopter/dispatch',json={'node':'H8'}).status_code==409
    assert client.get('/state').status_code==200


@pytest.fixture
def client(monkeypatch):
    api._cancel.set()
    api._resume.set()
    if api._worker:
        api._worker.join(3)
    model=Simulation(seed=42,verbose=False,automatic_events=False)
    model.initialize()
    monkeypatch.setattr(api,'sim',model)
    monkeypatch.setattr(api,'_revision',0)
    monkeypatch.setattr(api,'_job',{'status':'idle'})
    monkeypatch.setattr(SimConfig,'FLOOD_PROBABILITY',0)
    with TestClient(api.app) as connection:
        yield connection


def isolate(client):
    target=next(n for n in api.sim.graph.nodes if n not in api.sim.state.medical_network.centers)
    label=api.sim.graph.nodes[target].label
    state=client.post(f'/simulation/flood_node/{target}').json()['state']
    assert target in state['medical_network']['unreachable_nodes']
    return target,label,state


def test_road_reachability_controls_air_dispatch_and_emergency_message(client):
    first=client.get('/state').json()
    assert first['medical_network']['coverage_pct']==100
    assert first['air_rescue']['fuel_pct']==100
    assert len(first['fleet'])==len(first['medical_network']['centers'])==6
    assert not first['emergencies']
    assert client.post('/simulation/helicopter/dispatch',json={'node':'O15'}).status_code==409
    target,label,_=isolate(client)
    road=client.post('/simulation/emergencies',json={'node':label})
    assert road.status_code==409 and 'Helicopter depot required' in road.json()['detail']
    assert client.get(f'/simulation/helicopter/eligibility/{target}').json()['can_dispatch']
    flight=client.post('/simulation/helicopter/dispatch',json={'node':label})
    assert flight.status_code==200
    assert flight.json()['state']['air_rescue']['status']=='OUTBOUND'
    assert client.post('/simulation/helicopter/dispatch',json={'node':label}).status_code==409
    assert client.post('/simulation/helicopter/refuel').status_code==409
    for _ in range(80):
        state=client.post('/simulation/step').json()['state']
        assert state['air_rescue']['fuel']>=0
        if state['emergencies'][0]['status']=='RESOLVED' and state['air_rescue']['status']=='READY':
            break
    assert state['emergencies'][0]['status']=='RESOLVED'
    assert state['events']['metrics']['civilians_rescued']==1
    assert state['air_rescue']['landed_node'] in state['medical_network']['reachable_nodes']
    assert client.post('/simulation/helicopter/refuel').json()['state']['air_rescue']['fuel_pct']==100


def test_new_center_is_constructed_from_current_recommendation(client):
    target,label,state=isolate(client)
    assert state['medical_network']['recommendations'][0]['node_id']==target
    centers=len(state['fleet'])
    created=client.post('/simulation/medical_centers',json={'node':label})
    assert created.status_code==200
    state=created.json()['state']
    assert len(state['fleet'])==centers+1
    assert state['fleet'][-1]['depot']==target
    assert state['medical_network']['coverage_pct']==100
    assert not state['medical_network']['recommendations']
    assert not client.get(f'/simulation/helicopter/eligibility/{target}').json()['required']
    assert client.post('/simulation/medical_centers',json={'node':label}).status_code==409


def test_landing_edit_validation_and_snapshot_revision(client):
    target,label,state=isolate(client)
    assert client.post('/simulation/helicopter/landings',json={'nodes':[label]}).status_code==422
    assert client.post('/simulation/helicopter/landings',json={'nodes':[]}).status_code==422
    assert client.post('/simulation/helicopter/landings',json={'nodes':['Z99']}).status_code==404
    assert client.post('/simulation/helicopter/landings',json={'nodes':[True]}).status_code==422
    centers=state['medical_network']['center_labels'][:2]
    assert client.post('/simulation/helicopter/landings',json={'nodes':centers}).status_code==422
    pads=[p['label'] for p in state['air_rescue']['landing_sites'][:2]]
    updated=client.post('/simulation/helicopter/landings',json={'nodes':pads}).json()['state']
    assert updated['revision']>state['revision']
    assert len(updated['air_rescue']['permanent_landings'])==6
    assert len(updated['air_rescue']['custom_landings'])==2


def test_busy_road_fleet_does_not_unlock_helicopter(client):
    state=api.sim.state
    for unit in state.fleet.units:
        unit['status']='RETURNING'
    target=next(iter(api.sim.graph.nodes))
    label=api.sim.graph.nodes[target].label
    assert client.post('/simulation/emergencies',json={'node':label}).status_code==409
    assert not client.get(f'/simulation/helicopter/eligibility/{target}').json()['required']
    assert client.post('/simulation/helicopter/dispatch',json={'node':label}).status_code==409
