import os
import sys
from pathlib import Path
from types import SimpleNamespace
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import pygame
import pytest
from app.state import AppState,ConnectionStatus
from app.theme import Fonts
from screens.police import PoliceScreen
from core.simulation_engine import Simulation


def click(screen,point):
    for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
        screen.handle_event(pygame.event.Event(kind,button=1,pos=point))


@pytest.fixture
def controls():
    pygame.init()
    Fonts.init()
    model=Simulation(seed=42,verbose=False)
    model.initialize()
    state=AppState()
    state.update_sim(model.state.to_dict())
    state.connection=ConnectionStatus.CONNECTED
    actions=[]
    def action(kind,payload=None,on_compare=None):
        actions.append((kind,payload))
        if on_compare:
            on_compare({'seed':1,'steps':20,'incident_count':4,'results':[]})
    app=SimpleNamespace(state=state,op_runner=SimpleNamespace(is_running=False),
                        show_status=lambda *a,**kw:None,async_police=action)
    screen=PoliceScreen(app,pygame.Rect(208,86,1352,846))
    surface=pygame.Surface((1560,960))
    screen.on_enter()
    screen.update(.016)
    screen.draw(surface)
    yield model,state,screen,surface,actions
    model.events.close()


def test_report_form_map_selection_severity_and_medical_task(controls):
    _,_,screen,surface,actions=controls
    click(screen,screen._renderer.node_screen_pos(screen.graph.nodes[47]))
    assert screen._node.text=='C4'
    click(screen,screen._severity_buttons[2].rect.center)
    click(screen,screen._medical_button.rect.center)
    click(screen,screen._kind_button.rect.center)
    screen.draw(surface)
    click(screen,screen._submit.rect.center)
    assert actions[-1]==('report',{'node':'C4','kind':'VANDALISM','severity':3,'medical_required':True})


def test_settings_station_planning_and_comparison_controls(controls):
    _,_,screen,surface,actions=controls
    click(screen,(screen._probability.rect.right,screen._probability.rect.centery))
    assert actions[-1]==('settings',{'auto_probability':1})
    click(screen,screen._patrol.rect.center)
    assert actions[-1]==('settings',{'patrol_enabled':False})
    click(screen,screen._auto.rect.center)
    assert actions[-1]==('settings',{'automatic_incidents':True})
    click(screen,screen._plan.rect.center)
    assert actions[-1]==('plan',None)
    click(screen,screen._benchmark.rect.center)
    assert screen._modal and not screen._compare_pending and screen._compare['seed']==1
    screen.draw(surface)
    screen._seed.text='19'
    click(screen,screen._rerun.rect.center)
    assert actions[-1]==('compare',{'seed':19})
    click(screen,screen._close.rect.center)
    assert not screen._modal


def test_unreachable_injury_report_exposes_helicopter_action(controls):
    model,state,screen,surface,actions=controls
    for neighbor in list(model.graph.get_neighbors(224)):
        model.block_road_manually(224,neighbor)
    report=model.state.police.report(224,'INJURY',2,0)
    state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen.update(.016)
    screen.draw(surface)
    assert report['medical_status']=='HELICOPTER_REQUIRED'
    click(screen,screen._rows[0][0].center)
    screen.draw(surface)
    assert screen._air.enabled
    click(screen,screen._air.rect.center)
    assert actions[-1]==('medical',{'report_id':report['id']})


def test_patrol_positions_interpolate_and_planning_does_not_move_units(controls):
    model,state,screen,surface,_=controls
    before=[u['position'] for u in model.state.police.units]
    for step in (1,2):
        model.step_forward()
    state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen.update(.016)
    screen.draw(surface)
    assert any(u['position']!=old for u,old in zip(model.state.police.units,before))
    assert any(u.get('render_position') for u in screen._renderer.police_service['units'])
    positions=[u['position'] for u in model.state.police.units]
    model.state.police.plan_stations()
    assert positions==[u['position'] for u in model.state.police.units]


def test_police_view_draws_real_ambulances_and_their_routes(controls):
    model,state,screen,surface,_=controls
    report=model.state.police.report(224,'INJURY',2,0)
    state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen.update(.016)
    captured=[]
    screen._renderer._draw_route_path=lambda surface,nodes,path,color:captured.append(path)
    screen.draw(surface)
    assert len(screen._renderer.fleet)==len(model.state.fleet.units)
    responding=next(u for u in screen._renderer.fleet if u['emergency_id']==report['medical_emergency_id'])
    assert responding['path'] in captured and responding.get('render_position')
    click(screen,screen._tabs[1].rect.center)
    screen.draw(surface)
    assert screen._tab=='fleet'
