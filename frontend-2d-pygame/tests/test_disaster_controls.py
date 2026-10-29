"""Native road-link selection, eight intensity buttons and traffic mode routing."""
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
from screens.god_mode import GodModeScreen
from screens.dispatch import DispatchScreen
from screens.route_lab import RouteLabScreen
from core.simulation_engine import Simulation


def click(screen,point):
    for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
        screen.handle_event(pygame.event.Event(kind,button=1,pos=point))


def test_disaster_view_relocation_button_uses_real_action(controls):
    model,app,screen,surface,actions=controls
    app.async_rescue_action=lambda action:actions.append((action,))
    model.state.disasters.unleash(model.state.air_rescue.landed_node,1,0)
    app.state.update_sim(model.state.to_dict())
    screen.update(.016)
    screen.draw(surface)
    assert screen._relocate.enabled
    click(screen,screen._relocate.rect.center)
    assert actions[-1]==('relocate',)


def test_dispatch_has_no_radius_controls_and_relocates_through_button(controls):
    model,app,_,surface,actions=controls
    app.async_rescue_action=lambda action:actions.append((action,))
    screen=DispatchScreen(app,pygame.Rect(208,86,1352,846))
    screen.on_enter()
    screen.update(.016)
    screen.draw(surface)
    assert not hasattr(screen,'_sliders') and not screen._relocate.enabled
    model.state.disasters.unleash(model.state.air_rescue.landed_node,1,0)
    app.state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen.update(.016)
    screen.draw(surface)
    assert screen._relocate.enabled
    click(screen,screen._relocate.rect.center)
    assert actions[-1]==('relocate',)


@pytest.fixture
def controls():
    pygame.init()
    Fonts.init()
    model=Simulation(seed=42,verbose=False)
    model.initialize()
    state=AppState()
    state.connection=ConnectionStatus.CONNECTED
    state.update_sim(model.state.to_dict())
    actions=[]
    app=SimpleNamespace(state=state,op_runner=SimpleNamespace(is_running=False),
                        show_status=lambda *a,**k:None, async_block_road=lambda *a:actions.append(('block',a)),
                        async_unblock_road=lambda *a:actions.append(('unblock',a)),
                        async_gate=lambda *a,**k:actions.append(('gate',a,k)))
    screen=GodModeScreen(app,pygame.Rect(208,86,1352,846))
    screen.on_enter()
    screen.on_state_updated()
    surface=pygame.Surface((1560,960))
    screen.update(.016)
    screen.draw(surface)
    yield model,app,screen,surface,actions
    model.events.close()


def test_block_selects_link_instead_of_junction_and_unblock_uses_same_link(controls):
    model,app,screen,surface,actions=controls
    edge=next(e for e in app.state.backend_graph.edges if abs(e['node_a']-e['node_b'])==1)
    nodes=app.state.backend_graph.nodes
    a,b=edge['node_a'],edge['node_b']
    pa,pb=screen._renderer.node_screen_pos(nodes[a]),screen._renderer.node_screen_pos(nodes[b])
    click(screen,pa)
    assert screen._selected_edge is None
    midpoint=tuple((v+w)//2 for v,w in zip(pa,pb))
    click(screen,midpoint)
    assert screen._selected_edge==(a,b)
    screen.draw(surface)
    click(screen,screen._execute.rect.center)
    assert actions[-1][0]=='block' and actions[-1][1][:2]==(a,b)
    model.block_road_manually(a,b)
    app.state.update_sim(model.state.to_dict())
    click(screen,screen._mode_btns[1].rect.center)
    click(screen,midpoint)
    screen.draw(surface)
    click(screen,screen._execute.rect.center)
    assert actions[-1][0]=='unblock' and actions[-1][1][:2]==(a,b)
    assert not hasattr(screen,'_btn_flood')


def test_all_eight_gates_preview_correct_radius_and_keep_center(controls):
    _,app,screen,surface,actions=controls
    click(screen,screen._mode_btns[2].rect.center)
    point=screen._renderer.node_screen_pos(app.state.backend_graph.nodes[112])
    click(screen,point)
    for level,button in enumerate(screen._level_btns,1):
        click(screen,button.rect.center)
        screen.update(.016)
        screen.draw(surface)
        assert screen._intensity==level
        assert screen._renderer.gate_preview['radius']==level
        assert screen._selected_node==112
    click(screen,screen._execute.rect.center)
    assert actions[-1]==('gate',(112,8),{})


def test_route_lab_normal_mode_respects_restrictions_and_keeps_ambulance_reference(controls):
    model,app,_,surface,_=controls
    model.state.disasters.unleash(112,3,0)
    app.state.update_sim(model.state.to_dict())
    screen=RouteLabScreen(app,pygame.Rect(208,86,1352,846))
    screen.on_enter()
    screen.draw(surface)
    screen._inp_src.text,screen._inp_dst.text='H8','A1'
    app.state.backend_sim.active_routes=[0,1]
    screen._run_route()
    assert screen._travel_mode=='normal' and not screen._result['reachable']
    assert not screen._renderer.route_paths  # no unrelated ambulance overlay in a normal calculation
    click(screen,screen._mode_button.rect.center)
    screen._run_route()
    assert screen._travel_mode=='ambulance' and screen._result['reachable'] and screen._validation['valid']
    assert any(p['path']==[0,1] for p in screen._renderer.route_paths)
    click(screen,screen._mode_button.rect.center)
    screen._run_route()
    assert screen._travel_mode=='normal' and not screen._result['reachable']
    assert not screen._renderer.route_paths
