"""Configured crime-map behavior, incident evidence and fixed medical locations."""
import json
from pathlib import Path
import pytest
from core.city_graph import CityGraph
from core.crime_heatmap import update_crime_heatmap
from core.simulation_engine import Simulation
from core.bank_placement import grid_distance,in_direction
from config.simulation_config import SimConfig


def world():
    graph=CityGraph()
    for node in graph.nodes.values():
        node.node_type=SimConfig.EMPTY
    return graph


def dense_center(graph):
    for row in range(6,9):
        for col in range(6,9):
            node=graph.nodes[row*15+col]
            node.node_type=SimConfig.RESIDENTIAL
            node.population=180
    return graph.nodes[112]


def test_crowded_residential_stays_low_without_nearby_reports():
    graph=world()
    node=dense_center(graph)
    graph.nodes[115].node_type=SimConfig.BANK
    update_crime_heatmap(graph)
    assert node.risk_level=='LOW'
    assert graph.nodes[115].risk_level=='HIGH'
    assert node.risk_features['dense_residential']==1


def test_bank_neighbors_hot_but_empty_distant_area_is_low():
    graph=world()
    graph.nodes[112].node_type=SimConfig.BANK
    update_crime_heatmap(graph)
    assert all(graph.nodes[n].risk_level=='HIGH' for n in (112,113,114))
    assert graph.nodes[0].risk_level=='LOW'


def test_industrial_residential_open_interface_is_high():
    graph=world()
    graph.nodes[112].node_type=SimConfig.INDUSTRIAL
    graph.nodes[114].node_type=SimConfig.RESIDENTIAL
    update_crime_heatmap(graph)
    assert graph.nodes[113].risk_level=='HIGH'
    assert 'interface' in ' '.join(graph.nodes[113].crime_reasons)


def test_report_overrides_crowded_area_and_resolved_evidence_fades():
    graph=world()
    node=dense_center(graph)
    report={'node_id':112,'severity':2,'created_step':0,'resolved_step':None,'status':'RESPONDING'}
    update_crime_heatmap(graph,[report],100)
    assert node.risk_level=='HIGH' and node.crime_score>=90
    assert graph.nodes[111].risk_level=='HIGH'
    assert graph.nodes[110].risk_level=='MEDIUM'
    assert graph.nodes[109].risk_level=='MEDIUM'
    assert graph.nodes[108].risk_level=='LOW'
    report.update(status='RESOLVED',resolved_step=100)
    update_crime_heatmap(graph,[report],100)
    assert node.risk_level=='HIGH'
    update_crime_heatmap(graph,[report],120)
    assert node.risk_level=='MEDIUM'
    update_crime_heatmap(graph,[report],200)
    assert node.risk_level=='LOW'
    assert graph.nodes[111].risk_level=='LOW'  # the whole area fades after resolution


def test_heatmap_does_not_change_just_because_roads_are_blocked():
    graph=world()
    graph.nodes[112].node_type=SimConfig.BANK
    graph.add_edge(112,113,1)
    update_crime_heatmap(graph)
    original={n.id:(n.risk_level,n.crime_score) for n in graph.nodes.values()}
    graph.block_road(112,113)
    update_crime_heatmap(graph)
    assert original=={n.id:(n.risk_level,n.crime_score) for n in graph.nodes.values()}


@pytest.mark.parametrize('seed',[0,1,2,3,7,11,19,42,99,2026])
def test_spacing_directions_and_original_medical_positions(seed):
    baseline={0:[6,56,77,142,162,169],1:[22,93,101,149,158,183],2:[36,42,47,175,181,192],
              3:[7,46,128,132,140,151],7:[8,61,116,142,152,190],11:[23,31,114,117,125,181],
              19:[24,61,142,145,167,193],42:[38,47,159,163,170,181],99:[54,62,88,141,153,160],2026:[37,43,63,147,158,166]}
    model=Simulation(seed=seed,verbose=False)
    try:
        model.initialize()
        graph=model.graph
        assert model.state.medical_network.centers==baseline[seed]
        banks=graph.get_nodes_of_type(SimConfig.BANK)
        hospitals=graph.get_nodes_of_type(SimConfig.HOSPITAL)
        assert all(grid_distance(b,h)>=4 for b in banks for h in hospitals)
        assert all(grid_distance(a,b)>=7 for i,a in enumerate(banks) for b in banks[i+1:])
        assert len({(b.row>=7,b.col>=7) for b in banks})==3
        protection=model.state.police.bank_protection()
        assert len({p['police_direction'] for p in protection})==3
        for item in protection:
            assert item['protected'] and 2<=item['grid_blocks']<=3
            station=next(s for s in model.state.police.stations if s['id']==item['station_id'])
            assert in_direction(graph.nodes[item['node_id']],graph.nodes[station['node_id']],item['police_direction'])
            assert all(grid_distance(graph.nodes[station['node_id']],h)>=2 for h in hospitals)
        cloned=CityGraph.from_dict(graph.to_dict())
        assert cloned.bank_directions==graph.bank_directions
        assert cloned.nodes[banks[0].id].crime_score==banks[0].crime_score
    finally:
        model.events.close()

def test_report_radius_is_circular_and_does_not_leak_outside_boundary():
    from core.crime_heatmap import incident_areas
    graph=world()
    report={'id':'CR-1','node_id':112,'severity':1,'created_step':0,'resolved_step':None,'status':'RESPONDING'}
    update_crime_heatmap(graph,[report],0)
    assert sum(n.risk_features['nearby_report_count']>0 for n in graph.nodes.values())==29
    assert graph.nodes[112].crime_score>graph.nodes[113].crime_score>graph.nodes[114].crime_score>graph.nodes[115].crime_score
    assert graph.nodes[115].risk_level=='MEDIUM'  # exactly three cells east
    assert graph.nodes[144].risk_level=='MEDIUM'  # two south and two east, distance sqrt(8)
    assert graph.nodes[130].risk_level=='LOW'  # one south and three east, distance sqrt(10)
    assert incident_areas(graph,[report],0)[0]['radius']==3


def test_overlapping_reports_strengthen_hotspot_and_are_order_independent():
    graph=world()
    reports=[{'id':str(n),'node_id':n,'severity':1,'created_step':0,'resolved_step':None,'status':'RESPONDING'} for n in (110,114)]
    update_crime_heatmap(graph,reports[:1],0)
    single=graph.nodes[112].crime_score
    update_crime_heatmap(graph,reports,0)
    overlap={n.id:n.crime_score for n in graph.nodes.values()}
    assert overlap[112]>single and overlap[112]==100
    update_crime_heatmap(graph,list(reversed(reports)),0)
    assert overlap=={n.id:n.crime_score for n in graph.nodes.values()}


def test_radius_uses_configuration_and_clips_at_city_boundary(monkeypatch):
    from core.crime_heatmap import incident_areas
    graph=world()
    report={'node_id':0,'severity':1,'created_step':0,'resolved_step':None,'status':'ON_SCENE'}
    monkeypatch.setattr(SimConfig,'CRIME_REPORT_RADIUS',1)
    update_crime_heatmap(graph,[report],0)
    assert sum(n.risk_features['nearby_report_count']>0 for n in graph.nodes.values())==3
    assert graph.nodes[1].risk_level=='HIGH' and graph.nodes[15].risk_level=='HIGH'
    assert graph.nodes[16].risk_level=='LOW'
    report.update(status='RESOLVED',resolved_step=0)
    update_crime_heatmap(graph,[report],100)
    assert incident_areas(graph,[report],100)==[]
    assert graph.nodes[0].risk_level==graph.nodes[1].risk_level=='LOW'
