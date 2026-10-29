# app/application.py — CityMind 2D: Main Application Controller
#
# Orchestrates:
#   - Pygame window lifecycle
#   - Screen navigation
#   - Background backend poller + async op runner
#   - Event dispatch to active screen
#   - Top bar, status bar, nav rail rendering
#
# The event loop NEVER blocks. Background threads update shared state;
# the main loop only reads snapshots and renders.

import pygame
import sys
import threading
import queue
import time
from typing import Optional

from app.theme import Colors, Fonts, Layout
from app.presentation import Presentation
from app.state import AppState, ActiveScreen, ConnectionStatus
from backend_client.api_client import CityMindClient, BackgroundPoller, AsyncOpRunner
from components.buttons import Button, draw_label, draw_rect_rounded, draw_badge


# ── Screen imports (lazy at runtime to avoid circular deps) ──────────────────

def _load_screens(app):
    from screens.dispatch     import DispatchScreen
    from screens.city_map     import CityMapScreen
    from screens.route_lab    import RouteLabScreen
    from screens.god_mode     import GodModeScreen
    from screens.ambulance    import AmbulanceScreen
    from screens.risk_heatmap import RiskHeatmapScreen
    from screens.police       import PoliceScreen
    from screens.metrics      import MetricsScreen
    from screens.diagnostics  import DiagnosticsScreen

    content_rect = pygame.Rect(
        Layout.LEFT_PANEL_W,
        Layout.TOPBAR_H,
        Layout.CONTENT_W + Layout.RIGHT_PANEL_W,   # screens own right area too
        Layout.CONTENT_H,
    )
    return {
        ActiveScreen.DASHBOARD:    DispatchScreen(app, content_rect),
        ActiveScreen.CITY_MAP:     CityMapScreen(app, content_rect),
        ActiveScreen.ROUTE_LAB:    RouteLabScreen(app, content_rect),
        ActiveScreen.GOD_MODE:     GodModeScreen(app, content_rect),
        ActiveScreen.AMBULANCE:    AmbulanceScreen(app, content_rect),
        ActiveScreen.RISK_HEATMAP: RiskHeatmapScreen(app, content_rect),
        ActiveScreen.POLICE:       PoliceScreen(app, content_rect),
        ActiveScreen.METRICS:      MetricsScreen(app, content_rect),
        ActiveScreen.DIAGNOSTICS:  DiagnosticsScreen(app, content_rect),
    }


class Application:
    """
    Top-level application. Instantiate and call .run().
    """

    NAV_ITEMS = [
        (ActiveScreen.DASHBOARD,    "01", "Dispatch"),
        (ActiveScreen.CITY_MAP,     "MAP", "City Map"),
        (ActiveScreen.ROUTE_LAB,    "LAB", "Route Lab"),
        (ActiveScreen.GOD_MODE,     "GOD", "Disasters"),
        (ActiveScreen.AMBULANCE,    "AMB", "Ambulance"),
        (ActiveScreen.RISK_HEATMAP, "RSK", "Heatmap"),
        (ActiveScreen.POLICE,       "POL", "Police"),
        (ActiveScreen.METRICS,      "MET", "Metrics"),
        (ActiveScreen.DIAGNOSTICS,  "DIA", "Diagnostics"),
    ]

    def __init__(self, backend_url: str = "http://127.0.0.1:8000"):
        pygame.init()
        pygame.display.set_caption("CityMind — 2D Operations Center")

        self.display = pygame.display.set_mode(
            (Layout.WIN_W, Layout.WIN_H),
            pygame.RESIZABLE
        )
        self.window = pygame.Surface((Layout.WIN_W, Layout.WIN_H)).convert()
        self.presentation = Presentation(self.window.get_size())
        self.presentation.resize(self.display.get_size())
        self.clock = pygame.time.Clock()
        self._closed = False
        self.playing = False
        self._dispatch_playback = False
        self._focused = True
        self._minimized = False
        self.playback_interval = 0.42
        self._next_step_at = 0.0
        self._help_visible = False
        self.query_runner = AsyncOpRunner()

        Fonts.init()
        self._play_button = Button("PLAY", (1102, 27, 94, 34), style="success", font_size=11)
        self._step_button = Button("STEP", (1206, 27, 84, 34), style="primary", font_size=11)
        self._help_button = Button("F1 HELP", (1300, 27, 90, 34), font_size=10)

        self.state  = AppState()
        self.client = CityMindClient(base_url=backend_url)
        self.op_runner = AsyncOpRunner()

        # Thread-safe update queue: background threads push updates here;
        # main loop drains and applies them.
        self._update_queue: queue.Queue = queue.Queue(maxsize=128)

        # Load screens
        self.screens = _load_screens(self)
        self._active_screen = self.screens[ActiveScreen.DASHBOARD]

        # Tooltips
        self._tooltip_text  = ""
        self._tooltip_pos   = (0, 0)
        self._tooltip_timer = 0.0

        # Status messages (transient)
        self._status_msg    = ""
        self._status_level  = "info"
        self._status_expire = 0.0

        # Background poller
        self._poller = BackgroundPoller(
            client     = self.client,
            on_update  = self._on_backend_update,
            on_error   = self._on_backend_error,
            interval   = 1.0,
        )

        # Initial connection attempt in background
        self.state.connection = ConnectionStatus.CONNECTING
        self._poller.start()

    # ── Backend callbacks (called from background threads) ───────────────────

    def _on_backend_update(self, data: dict):
        self._post_update(("state", data))

    def _on_backend_error(self, err: str):
        self._post_update(("error", err))

    def _post_update(self, item):
        if self._closed:
            return
        try:
            self._update_queue.put_nowait(item)
        except queue.Full:
            # This mailbox is bounded even if the window is paused by the OS.
            try:
                self._update_queue.get_nowait()
            except queue.Empty:
                pass
            self._update_queue.put_nowait(item)

    def run_query(self, fn, on_done, on_error):
        return self.query_runner.run(fn,
            lambda data: self._post_update(("callback", lambda: on_done(data))),
            lambda error: self._post_update(("callback", lambda: on_error(error))))

    # ── Async operation helpers (called from UI, execute in background) ──────

    def async_step(self):
        """Advance one simulation step."""
        if self.op_runner.is_running:
            self.show_status("Operation in progress — please wait.", level="warning")
            return

        def fn():
            return self.client.step()

        def on_done(data):
            self._post_update(("state", data.get("state", data)))
            self._post_update(("status_ok", "Step complete."))

        def on_err(err):
            self._post_update(("operation_error", err))

        self.op_runner.run(fn, on_done, on_err)
        self.show_status("Stepping simulation...", level="info")

    def async_restart(self):
        """Restart the simulation."""
        self.playing = False
        if self.op_runner.is_running:
            self.show_status("Operation in progress.", level="warning")
            return

        def fn():
            return self.client.restart()

        def on_done(data):
            self._post_update(("state", data.get("state", data)))
            self._post_update(("status_ok", "Simulation restarted."))

        def on_err(err):
            self._post_update(("operation_error", err))

        self.op_runner.run(fn, on_done, on_err)
        self.show_status("Restarting simulation...", level="info")

    def async_flood_node(self, node_id: int, label: str = ""):
        """God Mode: flood a sector."""
        if self.op_runner.is_running:
            self.show_status("Operation in progress.", level="warning")
            return

        def fn():
            return self.client.flood_node(node_id)

        def on_done(data):
            self._post_update(("state", data.get("state", data)))
            msg = f"Flood at {label or node_id} complete. Routes recalculated."
            self._post_update(("status_ok", msg))
            self.state.local_log.add(msg, level="warning", category="FLOOD")

        def on_err(err):
            self._post_update(("operation_error", err))

        self.op_runner.run(fn, on_done, on_err)
        self.show_status(f"Flooding sector {label or node_id}...", level="warning")

    def async_block_road(self, node_a: int, node_b: int, label_a: str = "", label_b: str = ""):
        """God Mode: block a road between two sectors."""
        if self.op_runner.is_running:
            self.show_status("Operation in progress.", level="warning")
            return

        def fn():
            return self.client.block_road(node_a, node_b)

        def on_done(data):
            changed = data.get("changed", False) if isinstance(data, dict) else False
            state_d = data.get("state", data) if isinstance(data, dict) else data
            self._post_update(("state", state_d))
            la = label_a or str(node_a)
            lb = label_b or str(node_b)
            if changed:
                msg = f"Road {la}\u2194{lb} blocked. Routes recalculated."
            else:
                msg = f"Road {la}\u2194{lb}: no change (already blocked or invalid)."
            self._post_update(("status_ok", msg))
            self.state.local_log.add(msg, level="warning", category="ROADS")

        def on_err(err):
            self._post_update(("operation_error", err))

        self.op_runner.run(fn, on_done, on_err)
        la = label_a or str(node_a)
        lb = label_b or str(node_b)
        self.show_status(f"Blocking road {la}\u2194{lb}...", level="warning")

    def async_gate(self, node_id=None, intensity=None, clear=False):
        self.op_runner.run(lambda: self.client.clear_gates() if clear else self.client.unleash_gate(node_id,intensity),
                           lambda data: (self._post_update(('state',data['state'])),
                                         self._post_update(('status_ok',data.get('message','Gate updated')))),
                           lambda error: self._post_update(('operation_error',error)))

    def async_unblock_road(self, node_a: int, node_b: int, label_a: str = "", label_b: str = ""):
        """God Mode: unblock a road between two sectors."""
        if self.op_runner.is_running:
            self.show_status("Operation in progress.", level="warning")
            return

        def fn():
            return self.client.unblock_road(node_a, node_b)

        def on_done(data):
            changed = data.get("changed", False) if isinstance(data, dict) else False
            state_d = data.get("state", data) if isinstance(data, dict) else data
            self._post_update(("state", state_d))
            la = label_a or str(node_a)
            lb = label_b or str(node_b)
            if changed:
                msg = f"Road {la}\u2194{lb} unblocked. Routes recalculated."
            else:
                msg = f"Road {la}\u2194{lb}: no change (already open or invalid)."
            self._post_update(("status_ok", msg))
            self.state.local_log.add(msg, level="info", category="ROADS")

        def on_err(err):
            self._post_update(("operation_error", err))

        self.op_runner.run(fn, on_done, on_err)
        la = label_a or str(node_a)
        lb = label_b or str(node_b)
        self.show_status(f"Unblocking road {la}\u2194{lb}...", level="info")

    def async_dispatch(self, label):
        def done(data):
            def apply():
                self.state.update_sim(data['state'])
                self._active_screen.on_state_updated()
                self.show_status(data.get('message', 'Ambulance dispatched'), duration=6)
                if data.get('emergency', {}).get('status') == 'RESPONDING':
                    self.playing = True
                    self._dispatch_playback = True
                    self._next_step_at = time.monotonic()+self.playback_interval
            self._post_update(('callback', apply))
        self.op_runner.run(lambda: self.client.dispatch_emergency(label), done,
                           lambda error: self._post_update(('operation_error', error)))

    def async_police(self, action, payload=None, on_compare=None):
        if action=='compare':
            self.run_query(lambda:self.client.police_action(action,payload or {}),on_compare,
                           lambda error:(on_compare({'error':error}),self.show_status(error,level='error',duration=8)))
            return
        def done(data):
            def apply():
                self.state.update_sim(data['state'])
                self._active_screen.on_state_updated()
                self.show_status(data.get('message','Police updated'),duration=7)
                if action in ('report','medical'):
                    self.playing=self._dispatch_playback=True
                    self._next_step_at=time.monotonic()+self.playback_interval
                elif action=='settings' and payload and (payload.get('automatic_incidents') or payload.get('patrol_enabled')):
                    self.playing=True
                    self._dispatch_playback=False
                    self._next_step_at=time.monotonic()+self.playback_interval
            self._post_update(('callback',apply))
        self.op_runner.run(lambda:self.client.police_action(action,payload),done,
                           lambda error:self._post_update(('operation_error',error)))

    def async_city_events(self, settings):
        def done(data):
            def apply():
                self.state.update_sim(data['state'])
                self._active_screen.on_state_updated()
                self.show_status(data.get('message','City events updated'),duration=7)
                if any(settings.get(k) is True for k in ('enabled','medical_enabled','crime_enabled','roads_enabled')):
                    self.playing=True
                    self._dispatch_playback=False
                    self._next_step_at=time.monotonic()+self.playback_interval
            self._post_update(('callback',apply))
        self.op_runner.run(lambda:self.client.city_event_settings(settings),done,
                           lambda error:self._post_update(('operation_error',error)))

    def async_rescue_action(self, action, value=None):
        def operation():
            if action == 'dispatch':
                return self.client.dispatch_helicopter(value)
            if action == 'relocate':
                return self.client.relocate_helicopter()
            if action == 'landings':
                return self.client.set_landings(value)
            if action == 'center':
                return self.client.add_medical_center(value)
            return self.client.refuel_helicopter()
        def done(data):
            def apply():
                self.state.update_sim(data['state'])
                self._active_screen.on_state_updated()
                self.show_status(data.get('message', 'Rescue controls updated'), duration=7)
                if action in ('dispatch','relocate'):
                    self.playing = self._dispatch_playback = True
                    self._next_step_at = time.monotonic()+self.playback_interval
            self._post_update(('callback', apply))
        self.op_runner.run(operation, done, lambda error: self._post_update(('operation_error', error)))

    def async_optimization(self, action):
        if action == "start":
            self.playing = False
        self.op_runner.run(lambda: self.client.optimization(action),
            lambda data: self._post_update(("state", data.get("state", data))),
            lambda error: self._post_update(("operation_error", error)))

    def async_export_metrics(self):
        from pathlib import Path
        from datetime import datetime
        def export():
            content, error = self.client.export_metrics()
            if error:
                return None, error
            folder = Path(__file__).resolve().parents[2] / "exports"
            folder.mkdir(exist_ok=True)
            target = folder / f"citymind_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
            target.write_text(content, encoding="utf-8")
            return str(target), None
        self.run_query(export,
            lambda path: self.show_status(f"Metrics exported: {path}", duration=8.0),
            lambda error: self.show_status(error, level="error"))

    # ── State update helpers ─────────────────────────────────────────────────

    def refresh_state(self):
        """Force a background state refresh."""
        self._poller.request_refresh()

    # ── Status bar helpers ───────────────────────────────────────────────────

    def show_status(self, msg: str, level: str = "info", duration: float = 4.0):
        from presentation.sectors import sector_text
        self._status_msg    = sector_text(msg)
        self._status_level  = level
        self._status_expire = time.monotonic() + duration

    def _drain_updates(self):
        while True:
            try:
                tag, payload = self._update_queue.get_nowait()
            except queue.Empty:
                break

            if tag == "state":
                changed = self.state.update_sim(payload)
                self.state.last_error = None
                self.state.connection = ConnectionStatus.CONNECTED
                # Notify active screen
                if changed and hasattr(self._active_screen, "on_state_updated"):
                    self._active_screen.on_state_updated()
            elif tag == "callback":
                payload()
            elif tag == "operation_error":
                dispatch = self.screens[ActiveScreen.DASHBOARD]
                dispatch.on_state_updated()
                self.show_status(payload, level="error", duration=8.0)
                self.state.local_log.add(payload, level="error", category="API")
            elif tag == "connected":
                self.state.connection = ConnectionStatus.CONNECTED
            elif tag == "connecting":
                self.state.connection = ConnectionStatus.CONNECTING
            elif tag == "error":
                self.state.connection = ConnectionStatus.ERROR
                self.state.last_error = payload
                self.show_status(payload, level="error", duration=8.0)
                self.state.local_log.add(payload, level="error", category="API")
            elif tag == "status_ok":
                self.show_status(payload, level="info")
                self.state.local_log.add(payload, level="info", category="APP")

        identity = self.state.backend_sim.sim_id
        if getattr(self, '_notice_identity', None) != identity:
            self._notice_identity, self._notice_id = identity, 0
        notices = self.state.backend_sim.medical_network.get('notifications', [])
        fresh = [n for n in notices if n['id'] > self._notice_id]
        if fresh:
            self._notice_id = fresh[-1]['id']
            relocation = next((n for n in reversed(fresh) if n['message'].startswith('Assistant required')), None)
            self.show_status((relocation or fresh[-1])['message'], level='warning', duration=12)


    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        running = True
        prev_time = time.monotonic()

        while running:
            now = time.monotonic()
            dt  = min(now - prev_time, 0.05)
            prev_time = now

            self._drain_updates()

            # ── Events ──
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                if event.type == pygame.WINDOWFOCUSLOST:
                    self._focused = False
                elif event.type == pygame.WINDOWFOCUSGAINED:
                    self._focused = True
                elif event.type == pygame.WINDOWMINIMIZED:
                    self._minimized = True
                elif event.type == pygame.WINDOWRESTORED:
                    self._minimized = False
                if event.type == pygame.KEYDOWN:
                    self._handle_global_key(event)
                if event.type == pygame.VIDEORESIZE:
                    self.presentation.resize((event.w, event.h))
                event = self.presentation.event(event)
                if self._help_visible:
                    continue
                if self._help_button.handle_event(event):
                    self._help_visible = True
                    continue
                if self._play_button.handle_event(event):
                    self.toggle_playback()
                    continue
                if self._step_button.handle_event(event):
                    self.async_step()
                    continue

                # Nav rail click
                nav_consumed = self._handle_nav_event(event)
                if not nav_consumed:
                    self._active_screen.handle_event(event)

                # Tooltip hover
                if event.type == pygame.MOUSEMOTION:
                    self._tooltip_pos  = event.pos
                    self._tooltip_timer = 0.0

            # ── Update ──
            fleet=self.state.backend_sim.fleet
            if (self._dispatch_playback and fleet and all(unit['status'] in ('AVAILABLE','OUT_OF_SERVICE') for unit in fleet)
                    and self.state.backend_sim.air_rescue.get('status', 'READY') == 'READY'
                    and not self.state.backend_sim.police.get('summary',{}).get('response_in_progress')
                    and not self.state.backend_sim.police.get('settings',{}).get('automatic_incidents')
                    and not self.state.backend_sim.city_events.get('enabled',False)
                    and not self.state.backend_sim.city_events.get('active_road_closures')):
                self.playing=False
                self._dispatch_playback=False
                pending=(self.state.backend_sim.police.get('summary',{}).get('unresolved',0)
                         or self.state.backend_sim.dispatch_summary.get('active',0))
                outages=any(unit['status']=='OUT_OF_SERVICE' for unit in fleet)
                self.show_status('Active movement finished. Pending cases remain listed; restore access or service.' if pending else
                                 'Movement complete. Out-of-service units remain disabled.' if outages else 'Responses complete. Vehicles ready.')
            if self.playing and now >= self._next_step_at:
                if not self.state.is_connected or self.state.backend_sim.is_complete:
                    self.playing = False
                elif self.state.backend_sim.optimization.get("status") in ("running", "paused"):
                    self._next_step_at = now + self.playback_interval
                elif not self.op_runner.is_running:
                    self.async_step()
                    self._next_step_at = now + self.playback_interval
            self._active_screen.update(dt)

            if not self._minimized:
                self.draw_frame()
            self.clock.tick(60 if self._focused and not self._minimized else 15)

        self.close()

    def draw_frame(self):
        self.window.set_clip(None)
        self.window.fill(Colors.BG_DEEP)
        self._draw_top_bar()
        self._draw_nav_rail()
        self._active_screen.draw(self.window)
        self._draw_status_bar()
        self._draw_loading_indicator()

        self._draw_help()
        self.presentation.draw(self.window, self.display)
        pygame.display.flip()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._poller.stop()
        self.op_runner.close()
        self.query_runner.close()
        self.client.close()
        pygame.quit()

    # ── Navigation ───────────────────────────────────────────────────────────

    def navigate(self, screen: ActiveScreen):
        if self.state.god_mode and screen != ActiveScreen.GOD_MODE:
            self.show_status("God Mode disabled.")
        self.state.god_mode = screen == ActiveScreen.GOD_MODE
        self.state.active_screen = screen
        self._active_screen = self.screens[screen]
        self._active_screen.on_state_updated()
        if hasattr(self._active_screen, "on_enter"):
            self._active_screen.on_enter()

    def switch_screen(self, screen: ActiveScreen):
        """Alias for navigate."""
        self.navigate(screen)

    def _handle_nav_event(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        x, y = event.pos
        if x > Layout.LEFT_PANEL_W:
            return False
        # Nav items start at y=TOPBAR_H + 16
        nav_y = 146
        for screen_enum, icon, label in self.NAV_ITEMS:
            item_rect = pygame.Rect(14, nav_y, 180, 43)
            if item_rect.collidepoint(x, y):
                self.navigate(screen_enum)
                return True
            nav_y += 52
        return False

    def _handle_global_key(self, event):
        """Global keyboard shortcuts."""
        mods = getattr(event, "mod", pygame.key.get_mods())
        if event.key == pygame.K_F1:
            self._help_visible = not self._help_visible
            return
        focused = any(getattr(value, "focused", False) for value in vars(self._active_screen).values())
        if focused:
            return
        if event.key == pygame.K_SPACE:
            self.toggle_playback()
        elif event.key == pygame.K_n:
            self.async_step()
        elif event.key == pygame.K_f and hasattr(self._active_screen, "_renderer"):
            self._active_screen._renderer.fit_to_view(self.state.backend_graph.grid_rows, self.state.backend_graph.grid_cols)
        elif pygame.K_1 <= event.key <= pygame.K_9:
            self.navigate(self.NAV_ITEMS[event.key-pygame.K_1][0])
        elif event.key == pygame.K_F5 or (event.key == pygame.K_r and mods & pygame.KMOD_CTRL):
            self.refresh_state()
        elif event.key == pygame.K_ESCAPE:
            self._help_visible = False
            self.playing = False

    def toggle_playback(self):
        self._dispatch_playback = False
        if self.state.is_connected and not self.state.backend_sim.is_complete:
            self.playing = not self.playing
            self._next_step_at = time.monotonic() + self.playback_interval
            self.show_status("Playback running" if self.playing else "Playback paused")

    def _draw_help(self):
        if not self._help_visible:
            return
        panel = pygame.Rect(450, 230, 650, 350)
        pygame.draw.rect(self.window, Colors.BG_CARD, panel, border_radius=12)
        pygame.draw.rect(self.window, Colors.ACCENT_CYAN, panel, 1, border_radius=12)
        lines = ["KEYBOARD & MAP CONTROLS", "Space  Play / pause     N  Next step",
                 "1-9  Switch screen     F  Fit map", "F5 / Ctrl+R  Refresh    Esc  Pause / close help",
                 "Mouse wheel  Zoom at pointer", "Right-drag  Pan the map",
                 "Route Lab: click sectors to choose source and destination", "F1  Close this help"]
        for i, line in enumerate(lines):
            text = Fonts.bold(16).render(line, True, Colors.TEXT_BRIGHT if i == 0 else Colors.TEXT_SECONDARY)
            self.window.blit(text, (panel.x+24, panel.y+24+i*37))

    # ── Top bar ──────────────────────────────────────────────────────────────

    def _draw_top_bar(self):
        surface = self.window
        pygame.draw.rect(surface, Colors.BG_PANEL, (Layout.LEFT_PANEL_W,0,Layout.WIN_W-Layout.LEFT_PANEL_W,Layout.TOPBAR_H))
        pygame.draw.line(surface, Colors.BORDER, (Layout.LEFT_PANEL_W,Layout.TOPBAR_H-1),(Layout.WIN_W,Layout.TOPBAR_H-1))
        x = Layout.LEFT_PANEL_W+26
        small = Fonts.bold(10).render("CITY OPERATIONS  /  LIVE WORKSPACE",True,Colors.TEXT_MUTED)
        surface.blit(small,(x,16))
        title = Fonts.bold(25).render(self.state.active_screen.value,True,Colors.TEXT_PRIMARY)
        surface.blit(title,(x,34))
        sim = self.state.backend_sim
        text = Fonts.mono(12).render(f"STEP {sim.step:03d} / {sim.max_steps}",True,Colors.TEXT_SECONDARY)
        surface.blit(text,(920,38))
        enabled = self.state.is_connected and not sim.is_complete
        self._play_button.enabled = enabled
        self._step_button.enabled = enabled and not self.op_runner.is_running
        self._play_button.label = "PAUSE" if self.playing else "PLAY"
        for button in (self._play_button,self._step_button,self._help_button):
            button.draw(surface)
        color = Colors.GREEN if self.state.is_connected else Colors.ACCENT_AMBER
        pygame.draw.circle(surface,color,(1423,43),4)
        surface.blit(Fonts.bold(11).render("CONNECTED" if self.state.is_connected else "CONNECTING",True,color),(1435,36))

    def _draw_nav_rail(self):
        surface = self.window
        navy = (20,32,53)
        pygame.draw.rect(surface,navy,(0,0,Layout.LEFT_PANEL_W,Layout.WIN_H))
        pygame.draw.rect(surface,(48,111,227),(23,27,30,30),border_radius=8)
        pygame.draw.line(surface,(255,255,255),(31,42),(45,42),3)
        pygame.draw.line(surface,(255,255,255),(38,35),(38,49),3)
        surface.blit(Fonts.bold(20).render("citymind",True,(255,255,255)),(65,26))
        surface.blit(Fonts.sans(11).render("Emergency operations",True,(144,163,189)),(24,69))
        pygame.draw.line(surface,(43,58,81),(24,104),(184,104))
        surface.blit(Fonts.bold(10).render("WORKSPACE",True,(119,141,171)),(24,119))
        labels = {ActiveScreen.DASHBOARD:"Dispatch",ActiveScreen.CITY_MAP:"City explorer",
                  ActiveScreen.ROUTE_LAB:"Route laboratory",ActiveScreen.GOD_MODE:"Disasters",
                  ActiveScreen.AMBULANCE:"Fleet analytics",ActiveScreen.RISK_HEATMAP:"Crime heatmap",
                  ActiveScreen.POLICE:"Police operations",ActiveScreen.METRICS:"Metrics & export",
                  ActiveScreen.DIAGNOSTICS:"Diagnostics"}
        for index,(screen,_,_) in enumerate(self.NAV_ITEMS):
            y = 146+index*52
            active = screen == self.state.active_screen
            if active:
                pygame.draw.rect(surface,(43,86,156),(14,y,180,43),border_radius=9)
                pygame.draw.rect(surface,(109,169,255),(14,y+12,3,19),border_radius=2)
            color = (255,255,255) if active else (162,179,203)
            surface.blit(Fonts.mono(10).render(f"{index+1:02d}",True,(118,151,198)),(28,y+14))
            surface.blit(Fonts.sans(13).render(labels[screen],True,color),(59,y+12))
        box = pygame.Rect(20,Layout.WIN_H-176,168,106)
        pygame.draw.rect(surface,(30,46,70),box,border_radius=10)
        surface.blit(Fonts.bold(10).render("LOCAL PROTOTYPE",True,(139,170,211)),(32,box.y+15))
        surface.blit(Fonts.sans(13).render("Python simulation",True,(234,240,250)),(32,box.y+36))
        surface.blit(Fonts.sans(11).render("15 x 15 urban sectors",True,(152,173,202)),(32,box.y+61))
        surface.blit(Fonts.sans(10).render("1-9 Navigate  /  F1 Help",True,(139,159,187)),(24,Layout.WIN_H-43))

    def _draw_status_bar(self):
        surface = self.window
        y = Layout.WIN_H-Layout.STATUSBAR_H
        pygame.draw.rect(surface,Colors.BG_PANEL,(Layout.LEFT_PANEL_W,y,Layout.WIN_W-Layout.LEFT_PANEL_W,Layout.STATUSBAR_H))
        pygame.draw.line(surface,Colors.BORDER,(Layout.LEFT_PANEL_W,y),(Layout.WIN_W,y))
        message = self._status_msg if time.monotonic()<self._status_expire else "Dispatch uses the nearest operational available ambulance. HP marks helicopter building bases; hospitals receive patients."
        color = Colors.RED if self._status_level == 'error' and time.monotonic()<self._status_expire else Colors.TEXT_MUTED
        text = Fonts.sans(11).render(message,True,color)
        clip = surface.get_clip()
        surface.set_clip((Layout.LEFT_PANEL_W+18,y,Layout.WIN_W-Layout.LEFT_PANEL_W-120,Layout.STATUSBAR_H))
        surface.blit(text,(Layout.LEFT_PANEL_W+18,y+6))
        surface.set_clip(clip)
        surface.blit(Fonts.mono(10).render(f"{self.clock.get_fps():.0f} FPS",True,Colors.TEXT_MUTED),(Layout.WIN_W-70,y+7))

    def _draw_loading_indicator(self):
        if self.op_runner.is_running:
            self.window.blit(Fonts.sans(11).render("Syncing...",True,Colors.ACCENT_CYAN),(790,39))
