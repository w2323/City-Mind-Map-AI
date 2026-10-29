import pytest
from fastapi.testclient import TestClient
from backend.api import main as api
from core.simulation_engine import Simulation
from config.simulation_config import SimConfig


@pytest.fixture
def client(monkeypatch):
    api._cancel.set()
    api._resume.set()
    if api._worker:
        api._worker.join(3)
    model=Simulation(seed=42,verbose=False)
    model.initialize()
    monkeypatch.setattr(api,'sim',model)
    monkeypatch.setattr(api,'_revision',0)
    monkeypatch.setattr(api,'_job',{'status':'idle'})
    with TestClient(api.app) as connection:
        yield connection


def test_gate_preview_then_ambulance_only_routes_and_recovery(client):
    initial=client.get('/state').json()
    preview=client.post('/simulation/disasters/gate/preview',json={'node_id':112,'intensity':4}).json()
    assert preview['radius']==4 and preview['road_count']>0
    assert client.get('/state').json()['revision']==initial['revision']
    result=client.post('/simulation/disasters/gate',json={'node_id':112,'intensity':4})
    assert result.status_code==200
    state=result.json()['state']
    assert state['revision']>initial['revision']
    assert state['disasters']['ambulance_only_roads']>0
    assert state['medical_network']['coverage_pct']==100
    assert not state['medical_network']['unreachable_nodes']
    assert any('out of service' in n['message'] for n in state['medical_network']['notifications'])
    assert not client.get('/simulation/helicopter/eligibility/112').json()['required']
    default_route=client.post('/simulation/route',json={'src':112,'dst':0}).json()
    assert default_route['travel_mode']=='normal'
    assert not default_route['reachable'] and default_route['path_cost'] is None
    for mode in ('normal','commercial'):
        route=client.post('/simulation/route',json={'src':112,'dst':0,'travel_mode':mode}).json()
        assert not route['reachable'] and route['path_cost'] is None and route['travel_mode']==mode
    assert client.post('/simulation/route',json={'src':112,'dst':0,'travel_mode':'ambulance'}).json()['reachable']
    rankings=client.get('/simulation/ambulance_routes/112').json()
    assert all(r['travel_mode']=='ambulance' for r in rankings['candidates'])
    # Opening a single link removes only its temporary restriction.
    a,b=preview['affected_roads'][0]
    reopened=client.post(f'/simulation/unblock_road/{a}/{b}').json()
    assert reopened['changed']
    road=next(e for e in reopened['state']['graph']['edges'] if (e['node_a'],e['node_b'])==(a,b))
    assert not road['blocked'] and not road['temporarily_blocked']
    client.post(f'/simulation/block_road/{a}/{b}')
    cleared=client.post('/simulation/disasters/gates/clear').json()['state']
    assert not cleared['disasters']['gates'] and cleared['disasters']['fully_blocked_roads']==1
    assert all(not e['temporarily_blocked'] for e in cleared['graph']['edges'])
    assert client.post('/simulation/route',json={'src':112,'dst':0,'travel_mode':'normal'}).json()['reachable']


def test_only_explicit_ambulance_routing_can_use_gate_roads(client):
    client.post('/simulation/disasters/gate',json={'node_id':112,'intensity':8})
    # Road privileges remain unchanged, but actual exposed units cannot dispatch.
    assert client.post('/simulation/emergencies',json={'node':'H8'}).status_code==409
    assert client.get('/simulation/ambulance_routes/112').json()['best'] is None
    ordinary=client.post('/simulation/route',json={'src':0,'dst':112}).json()
    ambulance=client.post('/simulation/route',json={'src':0,'dst':112,'travel_mode':'ambulance'}).json()
    assert ordinary['travel_mode']=='normal' and not ordinary['reachable']
    assert ambulance['reachable']


@pytest.mark.parametrize('payload',[{'node_id':112,'intensity':0},{'node_id':112,'intensity':9},
                                  {'node_id':True,'intensity':1},{'node_id':112,'intensity':True},
                                  {'node_id':112,'intensity':'2'},{'node_id':112,'intensity':1,'radius':99}])
def test_gate_input_validation(client,payload):
    assert client.post('/simulation/disasters/gate',json=payload).status_code==422
    assert not client.get('/state').json()['disasters']['gates']


def test_missing_nodes_and_gate_limit_do_not_mutate_state(client,monkeypatch):
    assert client.post('/simulation/disasters/gate',json={'node_id':9999,'intensity':1}).status_code==404
    monkeypatch.setattr(SimConfig,'MAX_ACTIVE_GATES',1)
    first=client.post('/simulation/disasters/gate',json={'node_id':112,'intensity':1}).json()['state']
    assert client.post('/simulation/disasters/gate',json={'node_id':0,'intensity':8}).status_code==409
    after=client.get('/state').json()
    assert after['revision']==first['revision'] and after['graph']==first['graph']
    assert client.post('/simulation/route',json={'src':0,'dst':1,'travel_mode':'car'}).status_code==422
