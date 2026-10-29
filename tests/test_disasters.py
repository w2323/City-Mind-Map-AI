"""Gate geometry, traffic permissions, overlapping restrictions and live routing."""
import math
import pytest
from core.city_graph import CityGraph
from core.disasters import DisasterManager
from core.event_manager import EventManager
from core.simulation_engine import Simulation
from core.analytics import route
from challenges.challenge4 import AStarRouter
from config.simulation_config import SimConfig


@pytest.fixture
def disaster():
    graph=CityGraph()
    for node in graph.nodes.values():
        node.risk_level='LOW'
    for a,b in [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)]:
        graph.add_edge(a,b,1)
    events=EventManager(verbose=False)
    manager=DisasterManager(graph,events)
    yield graph,manager
    events.close()


def test_all_eight_levels_have_strictly_increasing_radii(disaster):
    graph,manager=disaster
    previews=[manager.preview(0,i) for i in range(1,9)]
    assert [p['radius'] for p in previews]==list(range(1,9))
    for small,big in zip(previews,previews[1:]):
        assert set(map(tuple,small['affected_roads'])) <= set(map(tuple,big['affected_roads']))
    assert previews[0]['road_count'] < previews[-1]['road_count']
    assert not any(e.temporarily_blocked for e in graph.edges.values())  # preview is read-only


def test_whole_segment_intersection_includes_crossing_and_tangent_roads(disaster):
    graph,manager=disaster
    graph.add_edge(105,119,1)  # A8--O8 crosses H8, although both endpoints lie outside radius 1
    graph.add_edge(90,104,1)   # A7--O7 is tangent to H8's radius 1
    graph.add_edge(75,89,1)    # A6--O6 is outside
    preview=manager.preview(112,1)
    assert [105,119] in preview['affected_roads']
    assert [90,104] in preview['affected_roads']
    assert [75,89] not in preview['affected_roads']


def test_gate_allows_ambulances_and_prohibits_both_normal_and_commercial(disaster):
    graph,manager=disaster
    gate=manager.unleash(1,1,0)
    assert graph.edges[(0,1)].temporarily_blocked
    assert not graph.edges[(0,1)].blocked
    assert route(graph,0,3,'ambulance')['reachable']
    for mode in ('normal','commercial'):
        assert not route(graph,0,3,mode)['reachable']
        assert graph.dijkstra(0,mode)[3]==math.inf
        assert graph.get_edge_cost(0,1,mode)==math.inf
    assert graph.dijkstra(0,'ambulance')[3]==3
    assert graph.nodes[1].accessible


def test_normal_traffic_takes_a_real_detour_while_ambulance_uses_shortest_path(disaster):
    graph,manager=disaster
    # Both endpoints lie outside H8's radius, but the direct road crosses it.
    for a,b in [(109,115),(109,79),(79,85),(85,115)]:
        graph.add_edge(a,b,1)
    graph.nodes[109].node_type=graph.nodes[115].node_type=SimConfig.RESIDENTIAL
    manager.unleash(112,1,0)
    assert route(graph,109,115,'ambulance')['path']==[109,115]
    assert route(graph,109,115)['travel_mode']=='normal'
    assert route(graph,109,115)['path']==[109,79,85,115]
    assert route(graph,109,115,'normal')['path']==[109,79,85,115]
    assert route(graph,109,115,'commercial')['path']==[109,79,85,115]
    graph.block_road(79,85)
    assert not route(graph,109,115)['reachable']
    assert route(graph,109,115,'ambulance')['reachable']


def test_full_block_overrides_gate_permission_and_unblock_opens_only_selected_link(disaster):
    graph,manager=disaster
    manager.unleash(1,1,0)
    graph.block_road(1,2)
    assert not route(graph,0,3,'ambulance')['reachable']
    assert graph.unblock_road(1,2)
    assert not graph.edges[(1,2)].temporarily_blocked
    assert graph.edges[(0,1)].temporarily_blocked
    assert route(graph,1,3,'normal')['reachable'] is False  # 2--3 still restricted
    manager.clear(0)
    assert route(graph,0,3,'normal')['reachable']


def test_overlap_and_clear_preserve_full_closures_and_serialized_access(disaster):
    graph,manager=disaster
    one=manager.unleash(1,2,0)
    two=manager.unleash(2,2,0)
    assert graph.edges[(1,2)].gate_ids=={one['id'],two['id']}
    graph.block_road(3,4)
    restored=CityGraph.from_dict(graph.to_dict())
    assert restored.edges[(1,2)].temporarily_blocked
    assert restored.edges[(1,2)].gate_ids=={one['id'],two['id']}
    assert not restored.edges[(1,2)].allows('normal')
    assert graph.unblock_road(1,2)  # explicit road exception clears both gate sources
    assert not graph.edges[(1,2)].gate_ids
    assert graph.edges[(2,3)].temporarily_blocked
    manager.clear(1)
    assert graph.edges[(3,4)].blocked
    assert not any(e.temporarily_blocked for e in graph.edges.values())


def test_normal_mission_replans_on_gate_and_resumes_after_clear(disaster):
    graph,manager=disaster
    normal=AStarRouter(graph,travel_mode='normal')
    normal.set_mission(0,[3])
    ambulance=AStarRouter(graph)
    ambulance.set_mission(0,[3])
    manager.unleash(1,1,0)
    assert not normal.current_path and normal.deferred==[3]
    ambulance.advance_one_step(1)
    assert ambulance.current_pos==1
    manager.clear(1)
    assert normal.current_path==[0,1,2,3]


@pytest.mark.parametrize('intensity',[0,9,-1,True,1.0,'1'])
def test_intensity_validation(disaster,intensity):
    with pytest.raises(ValueError):
        disaster[1].unleash(0,intensity,0)


def test_gate_preserves_roads_but_disables_exposed_ambulances():
    model=Simulation(seed=42,verbose=False,automatic_events=False)
    try:
        model.initialize()
        network=model.state.medical_network
        before=set(network.reachable)
        model.state.disasters.unleash(112,8,0)
        data=model.state.to_dict()
        assert network.reachable==before
        assert any('out of service' in n['message'] for n in data['medical_network']['notifications'])
        assert model.state.air_rescue.eligibility(112)['required']
        assert data['analysis']['ambulanceOnlyRoads']>0
        assert data['graph']['normal_active_edges']<data['graph']['active_edges']
        for _ in range(12):
            model.step_forward()
        assert not any(e.blocked for e in model.graph.edges.values())  # no random flooding
    finally:
        model.events.close()
