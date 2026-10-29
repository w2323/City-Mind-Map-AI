import pytest
from fastapi.testclient import TestClient
from backend.api import main as api
from core.simulation_engine import Simulation


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
    with TestClient(api.app) as connection:
        yield connection


def test_report_dispatch_and_actual_step_progress(client):
    initial=client.get('/state').json()
    assert len(initial['police']['stations'])==3 and len(initial['police']['units'])==10
    assert not initial['police']['reports'] and not initial['police']['settings']['automatic_incidents']
    result=client.post('/simulation/police/reports',json={'node':'C4','kind':'THEFT','severity':1})
    assert result.status_code==200
    state=result.json()['state']
    assert state['revision']>initial['revision']
    assert result.json()['report']['police_status'] in ('RESPONDING','ON_SCENE')
    for _ in range(50):
        state=client.post('/simulation/step').json()['state']
        if state['police']['reports'][0]['status']=='RESOLVED':
            break
    assert state['police']['summary']['police_handled']==1
    assert state['police']['summary']['resolved']==1
    assert state['police']['summary']['arrivals_measured']==1
    csv=client.get('/metrics/export').text
    assert 'police_reported,1' in csv and 'police_handled,1' in csv


def test_gate_blocks_police_but_unaffected_ambulance_can_still_respond(client):
    client.post('/simulation/disasters/gate',json={'node_id':112,'intensity':3})
    result=client.post('/simulation/police/reports',json={'node':'H8','kind':'INJURY','severity':1}).json()
    report=result['report']
    assert report['police_status']=='UNREACHABLE' and report['medical_status']=='RESPONDING'
    for _ in range(40):
        state=client.post('/simulation/step').json()['state']
        if state['police']['reports'][0]['medical_status']=='RESOLVED':
            break
    assert state['police']['reports'][0]['status']=='UNREACHABLE'
    assert state['events']['metrics']['civilians_rescued']==1
    restored=client.post('/simulation/disasters/gates/clear').json()['state']
    assert restored['police']['reports'][0]['police_status'] in ('RESPONDING','ON_SCENE')


def test_station_recommendation_construction_and_stale_protection(client):
    graph=api.sim.graph
    old_positions=[u['position'] for u in api.sim.state.police.units]
    for neighbor in list(graph.get_neighbors(224)):
        client.post(f'/simulation/block_road/224/{neighbor}')
    plan=client.post('/simulation/police/stations/plan').json()['state']['police']['recommendations']
    assert plan['additions'][0]['label']=='O15' and not plan['stale']
    result=client.post('/simulation/police/stations',json={'node':'O15'})
    assert result.status_code==200
    service=result.json()['state']['police']
    assert len(service['stations'])==4 and len(service['units'])==12
    assert old_positions==[u['position'] for u in service['units'][:10]]
    assert service['summary']['coverage_pct']==100
    assert client.post('/simulation/police/stations',json={'node':'A1'}).status_code==409


def test_settings_comparison_and_unknown_report(client):
    assert client.post('/simulation/police/settings',json={'automatic_incidents':True,'auto_probability':1,'patrol_enabled':False}).status_code==200
    state=client.post('/simulation/step').json()['state']
    assert state['police']['reports'][0]['source']=='AUTOMATIC'
    before=client.get('/state').json()
    compared=client.post('/simulation/police/compare',json={'seed':3,'steps':20,'incident_count':4})
    assert compared.status_code==200
    assert len(compared.json()['schedule'])==4
    assert all(r['reported']==4 for r in compared.json()['results'])
    after=client.get('/state').json()
    assert after['revision']==before['revision'] and after['police']['units']==before['police']['units']
    assert after['police']['reports']==before['police']['reports']
    assert client.post('/simulation/police/reports/missing/medical_rescue').status_code==404


@pytest.mark.parametrize('payload',[{'node':'Z99'},{'node':'C4','severity':True},{'node':'C4','severity':4},
                                  {'node':'C4','kind':'INVALID'},{'node':'C4','medical_required':'yes'},
                                  {'node':'C4','extra':'invalid'}])
def test_invalid_reports_do_not_create_cases(client,payload):
    assert client.post('/simulation/police/reports',json=payload).status_code in (404,422)
    assert not client.get('/state').json()['police']['reports']


def test_duplicate_report_and_settings_bounds(client):
    assert client.post('/simulation/police/reports',json={'node':'C4'}).status_code==200
    assert client.post('/simulation/police/reports',json={'node':'C4'}).status_code==409
    assert client.post('/simulation/police/settings',json={'auto_probability':2}).status_code==422
    assert client.post('/simulation/police/settings',json={'patrol_enabled':'yes'}).status_code==422
    assert client.post('/simulation/police/compare',json={'steps':100000}).status_code==422

def test_patrol_off_persists_across_reporting_settings_and_simulation_steps(client):
    for _ in range(3):
        client.post('/simulation/step')
    assert any(u['status']=='PATROLLING' for u in client.get('/state').json()['police']['units'])
    changed=client.post('/simulation/police/settings',json={'patrol_enabled':False}).json()['state']
    cars=changed['police']['units']
    parked={u['id']:u['position'] for u in cars}
    assert all(u['status']=='AVAILABLE' and not u['path'] for u in cars)
    assert client.post('/simulation/police/settings',json={'auto_probability':.2}).json()['state']['police']['settings']['patrol_enabled'] is False
    target=next(n['label'] for n in changed['graph']['nodes'] if n['id'] not in parked.values())
    response=client.post('/simulation/police/reports',json={'node':target,'kind':'THEFT','severity':1}).json()
    assigned=response['report']['unit_id']
    for _ in range(45):
        state=client.post('/simulation/step').json()['state']
        assert state['police']['settings']['patrol_enabled'] is False
        assert not any(u['status']=='PATROLLING' for u in state['police']['units'])
        assert all(u['position']==parked[u['id']] and not u['path'] for u in state['police']['units'] if u['id']!=assigned)
    assert state['police']['reports'][0]['status']=='RESOLVED'

def test_report_immediately_updates_crime_heatmap_and_surrounding_area(client):
    initial=client.get('/state').json()
    target=next(n for n in initial['graph']['nodes'] if n['node_type']=='RESIDENTIAL' and n['risk_features']['dense_residential'] and n['risk_level']=='LOW')
    changed=client.post('/simulation/police/reports',json={'node':target['label'],'kind':'THEFT','severity':2}).json()['state']
    node=next(n for n in changed['graph']['nodes'] if n['id']==target['id'])
    assert node['crime_score']>=90 and node['risk_level']=='HIGH'
    assert changed['risk_predictions'][str(node['id'])]=='HIGH'
    assert 'Active crime report' in node['crime_reasons']
    assert changed['crime_heatmap']['simulation_assumptions'] is True
    assert changed['crime_heatmap']['report_radius']==3
    area=changed['police']['crime_areas'][0]
    assert area['node_id']==node['id'] and area['radius']==3 and area['peak_score']>=90
    neighbor=next(n for n in changed['graph']['nodes'] if abs(n['row']-node['row'])+abs(n['col']-node['col'])==1)
    assert neighbor['risk_level']=='HIGH'
    assert neighbor['risk_features']['nearby_report_count']==1
