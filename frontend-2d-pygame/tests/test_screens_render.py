# tests/test_screens_render.py — Headless Smoke Test for All 9 Screens
# Verifies that every screen initializes, updates, and draws to a Pygame surface
# without exceptions, broken attribute references, or rendering crashes.

import os
import sys
import pytest

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pygame
pygame.init()
pygame.font.init()

from core.city_graph import CityGraph
from core.simulation_engine import Simulation
from app.state import AppState, ConnectionStatus, ActiveScreen
from screens.dashboard import DashboardScreen
from screens.city_map import CityMapScreen
from screens.route_lab import RouteLabScreen
from screens.god_mode import GodModeScreen
from screens.ambulance import AmbulanceScreen
from screens.risk_heatmap import RiskHeatmapScreen
from screens.police import PoliceScreen
from screens.metrics import MetricsScreen
from screens.diagnostics import DiagnosticsScreen


class DummyApp:
    """Mock Application providing necessary attributes for screen testing."""
    def __init__(self, state):
        self.state = state
        self.screen_rect = pygame.Rect(0, 0, 1280, 800)
        self.active_screen_name = "Dashboard"

    def async_step(self):
        pass

    def async_restart(self):
        pass

    def refresh_state(self):
        pass

    def show_status(self, msg, level="info"):
        pass

    def switch_screen(self, screen_enum):
        pass


class TestScreensRender:
    """Smoke tests for all screens to guarantee crash-free rendering."""

    @pytest.fixture
    def setup_app(self):
        sim = Simulation(seed=42)
        sim.initialize()
        state = AppState()
        state.connection = ConnectionStatus.CONNECTED
        state.update_sim(sim.state.to_dict())
        state.update_graph(sim.graph.to_dict())

        app = DummyApp(state)
        surface = pygame.Surface((1280, 800))
        return app, surface

    def test_dashboard_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = DashboardScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_city_map_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = CityMapScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_route_lab_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = RouteLabScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_god_mode_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = GodModeScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_ambulance_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = AmbulanceScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_risk_heatmap_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = RiskHeatmapScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_police_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = PoliceScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_metrics_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = MetricsScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)

    def test_diagnostics_screen_renders(self, setup_app):
        app, surface = setup_app
        rect = pygame.Rect(72, 32, 1208, 768)
        screen = DiagnosticsScreen(app, rect)
        screen.on_enter()
        screen.update(0.016)
        screen.draw(surface)
