"""Bank zoning and nearby, road-accessible police protection."""
import pytest
from core.simulation_engine import Simulation
from core.police_service import PoliceService,PoliceStationPlanner,compare_strategies
from core.city_graph import CityGraph
from core.event_manager import EventManager
from config.simulation_config import SimConfig


@pytest.mark.parametrize('seed',[0,1,2,3,7,11,19,42,99,2026])
def test_banks_survive_medical_planning_and_have_nearby_police(seed):
    model=Simulation(seed=seed,verbose=False)
    try:
        model.initialize()
        banks=model.graph.get_nodes_of_type(SimConfig.BANK)
        assert len(banks)==SimConfig.REQUIRED_COUNTS[SimConfig.BANK]==3
        assert all(b.population==SimConfig.POPULATION_MAP[SimConfig.BANK] for b in banks)
        assert len({b.id for b in banks})==3
        protection=model.state.police.bank_protection()
        assert all(b['protected'] and 1<=b['grid_blocks']<=3 for b in protection)
        assert all(model.graph.nodes[s['node_id']].node_type!=SimConfig.BANK for s in model.state.police.stations)
        payload=model.state.to_dict()
        assert len(payload['police']['banks'])==3
        assert sum(n['node_type']=='BANK' for n in payload['graph']['nodes'])==3
        assert all(b.id not in model.state.medical_network.centers for b in banks)
    finally:
        model.events.close()


def test_bank_protection_is_lost_on_road_closure_without_moving_station():
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        service=model.state.police
        bank=next(iter(model.graph.get_nodes_of_type(SimConfig.BANK)))
        positions=[s['node_id'] for s in service.stations]
        for neighbor in list(model.graph.get_neighbors(bank.id)):
            model.block_road_manually(bank.id,neighbor)
        assert not next(b for b in service.bank_protection() if b['node_id']==bank.id)['protected']
        assert positions==[s['node_id'] for s in service.stations]
        plan=service.plan_stations()
        assert plan['unserved_components']==1
        assert bank.id in plan['restore_road_nodes']
        assert bank.id not in [s['node_id'] for s in plan['additions']]
        with pytest.raises(ValueError,match='separate'):
            service.add_station(bank.id)
    finally:
        model.events.close()


def test_bank_accepts_existing_crime_report_and_resolves_with_patrols_off():
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        service=model.state.police
        service.configure(0,patrol_enabled=False)
        bank=model.graph.get_nodes_of_type(SimConfig.BANK)[0]
        report=service.report(bank.id,'THEFT',1,0)
        for _ in range(60):
            model.step_forward()
            if report['status']=='RESOLVED':
                break
        assert report['status']=='RESOLVED'
        assert bank.node_type==SimConfig.BANK
        assert not any(u['status']=='PATROLLING' for u in service.units)
    finally:
        model.events.close()


def test_comparison_handles_banks_cut_off_by_gate_without_crashing():
    model=Simulation(seed=42,verbose=False)
    try:
        model.initialize()
        model.state.disasters.unleash(112,8,0)
        result=compare_strategies(model.graph,seed=42,steps=20,incident_count=3)
        assert len(result['results'])==2
        assert all(r['reported']==3 for r in result['results'])
    finally:
        model.events.close()
