"""Regression tests for desktop rendering, async requests, and lifecycle."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import sys
import threading
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import pygame
from app.state import AppState, ActiveScreen, ConnectionStatus
from app.presentation import Presentation
from app.theme import Fonts, _CachedFont
from visualization.graph_renderer import GraphRenderer
from backend_client.api_client import AsyncOpRunner, BackgroundPoller


@pytest.fixture(autouse=True)
def pygame_runtime():
    pygame.init()
    Fonts.init()
    yield
    pygame.quit()


def graph_data():
    return {'nodes': [{'id': 0, 'row': 0, 'col': 0, 'node_type': 'HOSPITAL', 'risk_level': 'LOW', 'accessible': True},
                      {'id': 1, 'row': 0, 'col': 1, 'node_type': 'RESIDENTIAL', 'risk_level': 'LOW', 'accessible': True}],
            'edges': [{'node_a': 0, 'node_b': 1, 'cost': 1, 'blocked': False}]}


def test_revisions_prevent_stale_flood_and_reset_responses():
    state = AppState()
    state.update_sim({'sim_id': 'old', 'step': 2, 'revision': 8, 'graph': graph_data()})
    assert state.update_sim({'sim_id': 'old', 'step': 2, 'revision': 7, 'ambulances': [99]}) is False
    assert state.backend_sim.ambulances == []
    state.update_sim({'sim_id': 'new', 'step': 0, 'revision': 9})
    assert state.update_sim({'sim_id': 'old', 'step': 3, 'revision': 8}) is False
    assert state.backend_sim.sim_id == 'new'


def test_unchanged_poll_preserves_graph_and_suppresses_validation():
    state = AppState()
    payload = {'sim_id': 'same', 'step': 0, 'graph': graph_data()}
    assert state.update_sim(payload)
    nodes, edges = state.backend_graph.nodes, state.backend_graph.edges
    assert not state.update_sim(copy.deepcopy(payload))
    assert state.backend_graph.nodes is nodes
    assert state.backend_graph.edges is edges
    assert state.get_edge(1, 0) is edges[0]


def test_static_cache_invalidates_for_graph_and_view_changes():
    data = graph_data()
    nodes = {n['id']: n for n in data['nodes']}
    renderer = GraphRenderer(pygame.Rect(10, 10, 400, 300))
    surface = pygame.Surface((500, 400))
    renderer.draw(surface, nodes, data['edges'])
    renderer.draw(surface, nodes, data['edges'])
    assert renderer.cache_builds == 1
    data['edges'][0]['blocked'] = True
    renderer.draw(surface, nodes, data['edges'])
    assert renderer.cache_builds == 2
    renderer.heatmap_layer = 'risk'
    renderer.draw(surface, nodes, data['edges'], {'0': 'HIGH'})
    assert renderer.cache_builds == 3
    renderer._scale = 2
    renderer.draw(surface, nodes, data['edges'])
    assert renderer.cache_builds == 4


def test_zoom_uses_translated_pointer_and_preserves_anchor():
    renderer = GraphRenderer(pygame.Rect(260, 48, 900, 800))
    position = (700, 400)
    before = renderer.screen_to_grid(*position)
    assert renderer.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=2, x=0, pos=position))
    assert renderer.screen_to_grid(*position) == pytest.approx(before)
    assert renderer.hit_test_node(0, 0, {}) is None


@pytest.mark.parametrize('size', [(900, 600), (1920, 1080), (1440, 900), (600, 900)])
def test_resized_pointer_maps_to_original_control(size):
    presentation = Presentation((1440, 900))
    presentation.resize(size)
    point = (895, 24)
    physical = (presentation.rect.x + point[0] * presentation.rect.width / 1440,
                presentation.rect.y + point[1] * presentation.rect.height / 900)
    event = presentation.event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=physical))
    assert event.pos == point


def test_text_cache_is_bounded():
    font = Fonts.mono(10)
    assert font.render('Label', True, (255,255,255)) is font.render('Label', True, (255,255,255))
    for i in range(2200):
        font.render(str(i), True, (255,255,255))
    assert len(_CachedFont._surfaces) <= _CachedFont.MAX_ENTRIES
    assert _CachedFont._bytes <= _CachedFont.MAX_BYTES


def test_worker_reports_exceptions_and_becomes_available():
    runner = AsyncOpRunner()
    finished = threading.Event()
    errors = []
    def fail():
        raise ValueError('failed task')
    runner.run(fail, lambda data: None, lambda error: (errors.append(error), finished.set()))
    assert finished.wait(1)
    runner._thread.join(1)
    assert errors == ['failed task'] and not runner.is_running
    runner.close()


def test_reconnect_after_failed_first_request():
    received = threading.Event()
    class Client:
        count = 0
        def get_state(self):
            self.count += 1
            return (None, 'Offline') if self.count == 1 else ({'step': 0}, None)
    errors = []
    poller = BackgroundPoller(Client(), lambda data: received.set(), errors.append, interval=.01)
    poller.start()
    try:
        assert received.wait(1)
        assert errors == ['Offline']
    finally:
        poller.stop()
    assert not poller._thread.is_alive()


@pytest.fixture
def desktop(monkeypatch):
    from app import application
    monkeypatch.setattr(application.BackgroundPoller, 'start', lambda self: None)
    app = application.Application()
    app.state.connection = ConnectionStatus.CONNECTED
    app.state.update_sim({'sim_id': 'test', 'revision': 1, 'is_initialized': True, 'graph': graph_data(),
                          'router': {'current_pos': 0}, 'max_steps': 10})
    yield app
    app.close()


def test_all_desktop_screens_and_scaled_presentation(desktop):
    for screen in ActiveScreen:
        desktop.navigate(screen)
        desktop._active_screen.update(.016)
        desktop.draw_frame()
        assert desktop.state.god_mode == (screen == ActiveScreen.GOD_MODE)
    desktop.presentation.resize((1000, 700))
    desktop.draw_frame()
    desktop._help_visible = True
    desktop.draw_frame()


def test_route_request_returns_without_waiting_and_ignores_cleared_result(desktop, monkeypatch):
    screen = desktop.screens[ActiveScreen.ROUTE_LAB]
    screen._inp_src.text, screen._inp_dst.text = 'A1', 'B1'
    entered, release = threading.Event(), threading.Event()
    requests=[]
    def request(*args):
        requests.append(args)
        entered.set()
        release.wait(2)
        return {'src': 0, 'dst': 1, 'reachable': True, 'path': [0,1], 'path_cost': 1, 'hops': 1}, None
    monkeypatch.setattr(desktop.client, 'calculate_route', request)
    try:
        screen._run_route()
        assert entered.wait(1)
        assert requests==[(0,1,'normal')]
        assert screen._pending
        screen._clear()
        release.set()
        desktop.query_runner._thread.join(1)
        desktop._drain_updates()
        assert screen._result is None and screen._backend_route is None
        assert not screen._pending
    finally:
        release.set()


def test_keyboard_playback_does_not_steal_text_input(desktop):
    desktop.navigate(ActiveScreen.ROUTE_LAB)
    screen = desktop._active_screen
    screen._inp_src.focused = True
    desktop._handle_global_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
    assert not desktop.playing
    screen._inp_src.focused = False
    desktop._handle_global_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
    assert desktop.playing
    desktop._handle_global_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    assert not desktop.playing


def test_city_changes_invalidate_route_without_sending_extra_requests(desktop):
    screen = desktop.screens[ActiveScreen.ROUTE_LAB]
    screen._src_id, screen._dst_id = 0, 1
    screen._result = {"path": [0, 1]}
    screen._route_graph = (desktop.state.backend_graph.nodes, desktop.state.backend_graph.edges, "test", 1)
    desktop.state.update_sim({"sim_id": "test", "revision": 2, "graph": graph_data()})
    screen.on_state_updated()
    assert screen._result is None
    assert not desktop.query_runner.is_running
    assert "City changed" in screen._error_msg
