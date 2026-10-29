"""Physical heatmap patrol circuits, revisit cadence and emergency preemption."""
import pytest
from core.city_graph import CityGraph
from core.event_manager import EventManager
from core.police_service import PoliceService
from core.disasters import DisasterManager


@pytest.fixture
def patrol():
    graph=CityGraph()
    graph.nodes={n:graph.nodes[n] for n in range(4)}
    graph.adj={n:[] for n in graph.nodes}
    for node in graph.nodes.values():
        node.risk_level='LOW'
    graph.nodes[1].risk_level='HIGH'
    graph.nodes[2].risk_level='MEDIUM'
    for n in (1,2,3):
        graph.add_edge(0,n,1)
    events=EventManager(verbose=False)
    service=PoliceService(graph,events,stations=[0],unit_count=3)
    yield graph,events,service
    events.close()


def test_high_has_continuous_circuit_medium_more_often_than_low(patrol):
    graph,_,service=patrol
    for step in range(1,161):
        before={u['id']:u['position'] for u in service.units}
        service.advance(step)
        zones=service.patrol_coverage()
        assert len(zones)==1 and zones[0]['assigned_units']
        for unit in service.units:
            if unit['position']!=before[unit['id']]:
                assert unit['position'] in graph.get_neighbors(before[unit['id']],'normal')
        assert service.units[0]['reserve'] and service.units[0]['status']=='AVAILABLE'
    visits=service.patrol_destination_visits
    assert visits[1]>visits[2]>visits[3]>0
    assert visits[2]>=2*visits[3]
    assert service.to_dict(160)['patrol_policy']['revisit_steps']=={'HIGH':1,'MEDIUM':8,'LOW':24,'NONE':24}


def test_hotspot_assignment_changes_when_heatmap_changes(patrol):
    graph,_,service=patrol
    service.advance(1)
    graph.nodes[1].risk_level='LOW'
    graph.nodes[2].risk_level='HIGH'
    service.advance(2)
    zones=service.patrol_coverage()
    assert zones[0]['nodes']==[2] and zones[0]['assigned_units']
    assigned=next(u for u in service.units if u['id'] in zones[0]['assigned_units'])
    assert assigned['target']==2 or assigned['position']==2


def test_off_parks_circuits_but_does_not_prevent_manual_crime_response(patrol):
    _,_,service=patrol
    for step in range(1,5):
        service.advance(step)
    service.configure(4,patrol_enabled=False)
    positions={u['id']:u['position'] for u in service.units}
    assert not service.patrol_coverage()[0]['assigned_units']
    report=service.report(3,'THEFT',1,4)
    for step in range(5,15):
        service.advance(step)
        assert all(u['position']==positions[u['id']] for u in service.units if u['id']!=report['unit_id'])
        assert not any(u['status']=='PATROLLING' for u in service.units)
    assert report['status']=='RESOLVED'


def test_unreachable_high_area_is_reported_without_illegal_police_route(patrol):
    graph,events,service=patrol
    DisasterManager(graph,events).unleash(1,1,0)
    for step in range(1,8):
        service.advance(step)
    assert not service.patrol_coverage()[0]['assigned_units']
    assert all(graph.edges[(min(a,b),max(a,b))].allows('normal') for u in service.units for a,b in zip(u['path'],u['path'][1:]))


def test_report_can_preempt_high_patrol_and_another_car_can_cover(patrol):
    _,_,service=patrol
    service.advance(1)
    service.advance(2)
    high=next(u for u in service.units if u['patrol_zone'])
    report=service.report(high['position'],'THEFT',1,2)
    assert report['unit_id']==high['id'] and high['phase']=='ON_SCENE'
    service.advance(3)
    assert service.patrol_coverage()[0]['assigned_units']
    assert high['id'] not in service.patrol_coverage()[0]['assigned_units']
