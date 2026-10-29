"""Native control gating, outage dropdown, and runtime landing form events."""
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
from screens.dispatch import DispatchScreen
from core.simulation_engine import Simulation


def click(screen,button):
    for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
        screen.handle_event(pygame.event.Event(kind,button=1,pos=button.rect.center))


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
    app=SimpleNamespace(state=state,op_runner=SimpleNamespace(is_running=False),
                        async_rescue_action=lambda *a:actions.append(a))
    screen=DispatchScreen(app,pygame.Rect(208,86,1352,846))
    surface=pygame.Surface((1560,960))
    screen.on_enter()
    screen.on_state_updated()
    screen.draw(surface)
    yield model,state,screen,surface,actions
    model.events.close()


def test_helicopter_button_unlocks_only_for_cut_off_target(controls):
    model,state,screen,surface,actions=controls
    screen._inp_node.text='O15'
    screen.draw(surface)
    assert not screen._air.enabled
    click(screen,screen._air)
    assert not actions
    model.trigger_flood_at_node(224)
    state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    assert screen._modal=='network'  # outage automatically drops the detailed notice
    screen.draw(surface)
    click(screen,screen._close)
    screen.draw(surface)
    assert screen._air.enabled
    click(screen,screen._air)
    assert actions==[('dispatch','O15')]
    screen._inp_node.text='H8'
    screen.draw(surface)
    assert not screen._air.enabled


def test_landing_form_and_recommended_center_action(controls):
    model,state,screen,surface,actions=controls
    click(screen,screen._landings)
    assert screen._modal=='landings'
    screen._landing_input.text='A1, H8'
    screen.draw(surface)
    click(screen,screen._apply_landings)
    assert actions[-1]==('landings',['A1','H8'])
    click(screen,screen._close)
    model.trigger_flood_at_node(224)
    state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen.draw(surface)
    assert screen._build_center.enabled
    click(screen,screen._build_center)
    assert actions[-1]==('center','O15')
