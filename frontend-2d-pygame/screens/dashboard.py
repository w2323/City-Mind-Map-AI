# screens/dashboard.py — Main Dashboard Screen

import pygame
import time
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout
from app.state import ConnectionStatus
from components.buttons import Button, draw_rect_rounded, draw_label, draw_section_header


class DashboardScreen(BaseScreen):
    """
    Dashboard: live summary of all simulation KPIs, quick actions,
    recent events, and backend health.
    """

    def __init__(self, app, rect):
        super().__init__(app, rect)
        self._btn_step    = Button("STEP", (rect.x + 12, rect.y + 8, 100, 30), style="primary", font_size=11)
        self._btn_restart = Button("RESTART", (rect.x + 118, rect.y + 8, 100, 30), style="danger", font_size=11)
        self._btn_refresh = Button("REFRESH", (rect.x + 224, rect.y + 8, 100, 30), style="neutral", font_size=11)
        self._btn_play = Button("PLAY", (rect.x + 330, rect.y + 8, 100, 30), style="success", font_size=11)
        self._scroll_y    = 0
        self._event_scroll = 0

    def handle_event(self, event):
        if self._btn_play.handle_event(event):
            if hasattr(self.app, "toggle_playback"):
                self.app.toggle_playback()
        if self._btn_step.handle_event(event):
            self.app.async_step()
        if self._btn_restart.handle_event(event):
            self.app.async_restart()
        if self._btn_refresh.handle_event(event):
            self.app.refresh_state()
        if event.type == pygame.MOUSEWHEEL:
            self._event_scroll = max(0, self._event_scroll - event.y * 16)

    def draw(self, surface):
        r = self.rect
        # Background
        pygame.draw.rect(surface, Colors.BG_DEEP, r)

        # Top action bar
        pygame.draw.rect(surface, Colors.BG_PANEL,
                         pygame.Rect(r.x, r.y, r.width, 48))
        self._btn_step.draw(surface)
        self._btn_restart.draw(surface)
        self._btn_refresh.draw(surface)
        self._btn_play.label = "PAUSE" if getattr(self.app, "playing", False) else "PLAY"
        self._btn_play.enabled = self.state.is_connected and not self.sim.is_complete
        self._btn_play.draw(surface)

        if not self.state.is_connected:
            self.draw_not_connected(surface)
            return

        y0 = r.y + 56
        x0 = r.x + 12
        col_w = (r.width - 24) // 3 - 8

        # ── Column 1: Simulation state ───────────────────────────────────────
        self._draw_sim_card(surface, x0, y0, col_w)

        # ── Column 2: Graph statistics ───────────────────────────────────────
        self._draw_graph_card(surface, x0 + col_w + 8, y0, col_w)

        # ── Column 3: Risk & resources ───────────────────────────────────────
        self._draw_risk_card(surface, x0 + (col_w + 8) * 2, y0, col_w)

        # ── Events feed ──────────────────────────────────────────────────────
        events_y = y0 + 280
        events_rect = pygame.Rect(x0, events_y, r.width - 24, r.height - (events_y - r.y) - 12)
        self._draw_events(surface, events_rect)

    def _draw_sim_card(self, surface, x, y, w):
        sim = self.sim
        card = pygame.Rect(x, y, w, 260)
        self.draw_panel(surface, card, "Simulation State")
        cy = y + 30

        status = "COMPLETE" if sim.is_complete else ("PLAYING" if getattr(self.app, "playing", False) else "READY" if sim.is_initialized else "OFFLINE")
        scol   = Colors.GREEN if sim.is_initialized and not sim.is_complete else (
                 Colors.YELLOW if sim.is_complete else Colors.RED)
        cy = self.draw_kv(surface, "Status:", status, x + 8, cy, val_color=scol)
        cy = self.draw_kv(surface, "Step:", f"{sim.step} / {sim.max_steps}", x + 8, cy)

        # Progress bar
        if sim.max_steps > 0:
            bar_w = w - 20
            pct = sim.step / sim.max_steps
            pygame.draw.rect(surface, Colors.BG_HOVER, (x + 10, cy, bar_w, 8), border_radius=4)
            pygame.draw.rect(surface, Colors.GREEN, (x + 10, cy, int(bar_w * pct), 8), border_radius=4)
            cy += 16

        cy = self.draw_kv(surface, "Ambulances:", str(len(sim.ambulances)), x + 8, cy)
        cy = self.draw_kv(surface, "Civilians left:", str(len(sim.civilians)), x + 8, cy)
        cy = self.draw_kv(surface, "Floods total:", str(sim.metrics.get("total_floods", 0)), x + 8, cy, val_color=Colors.YELLOW)

        router = sim.router
        rescued = len(router.get("civilians_rescued", []))
        reroutes = router.get("total_reroutes", 0)
        cy = self.draw_kv(surface, "Rescued:", str(rescued), x + 8, cy, val_color=Colors.GREEN)
        cy = self.draw_kv(surface, "Reroutes:", str(reroutes), x + 8, cy)

        # Active route length
        active_route = sim.active_routes
        cy = self.draw_kv(surface, "Active route:", f"{len(active_route)} sectors", x + 8, cy)

        # Metrics
        m = sim.metrics
        cy = self.draw_kv(surface, "GA fitness:", str(m.get("ga_best_fitness") if m.get("ga_best_fitness") is not None else "Infeasible / pending"), x + 8, cy)

    def _draw_graph_card(self, surface, x, y, w):
        g = self.graph
        card = pygame.Rect(x, y, w, 260)
        self.draw_panel(surface, card, "Graph Statistics")
        cy = y + 30

        cy = self.draw_kv(surface, "Total sectors:", str(len(g.nodes)), x + 8, cy)
        cy = self.draw_kv(surface, "Total edges:", str(len(g.edges)), x + 8, cy)
        cy = self.draw_kv(surface, "Active edges:", str(g.active_edges), x + 8, cy, val_color=Colors.GREEN)
        cy = self.draw_kv(surface, "Blocked edges:", str(g.blocked_edges), x + 8, cy, val_color=Colors.RED)

        # Node type distribution
        type_counts = {}
        for nd in g.nodes.values():
            t = nd.get("node_type", "EMPTY")
            type_counts[t] = type_counts.get(t, 0) + 1

        cy += 4
        for ntype, count in sorted(type_counts.items()):
            short = {"RESIDENTIAL":"Residential","HOSPITAL":"Hospital",
                     "SCHOOL":"School","INDUSTRIAL":"Industrial",
                     "POWER_PLANT":"Power Plant","AMBULANCE_DEPOT":"Depot",
                     "BANK":"Financial","EMPTY":"Open space"}.get(ntype, ntype)
            cy = self.draw_kv(surface, f"  {short}:", str(count), x + 8, cy)

        # Police deployments
        police = self.sim.police_deployments
        cy = self.draw_kv(surface, "Police officers:", str(len(police)), x + 8, cy,
                          val_color=Colors.POLICE)

    def _draw_risk_card(self, surface, x, y, w):
        card = pygame.Rect(x, y, w, 260)
        self.draw_panel(surface, card, "Risk & Coverage")
        cy = y + 30

        m = self.sim.metrics
        cy = self.draw_kv(surface, "High risk zones:", str(m.get("high_risk_zones", "?")), x + 8, cy,
                          val_color=Colors.RISK_HIGH)
        cy = self.draw_kv(surface, "Medium risk:", str(m.get("medium_risk_zones", "?")), x + 8, cy,
                          val_color=Colors.RISK_MEDIUM)
        cy = self.draw_kv(surface, "Low risk:", str(m.get("low_risk_zones", "?")), x + 8, cy,
                          val_color=Colors.RISK_LOW)

        analysis = self.sim.analysis
        cy += 6
        cy = self.draw_kv(surface, "Coverage:", f"{analysis.get('coveragePct', 0):.1f}%", x + 8, cy)
        cy = self.draw_kv(surface, "Dead zones:", str(analysis.get("deadZones", "?")), x + 8, cy, val_color=Colors.YELLOW)
        cy = self.draw_kv(surface, "Connectivity:", f"{analysis.get('connectivityPct', 0):.1f}%", x + 8, cy)
        cy = self.draw_kv(surface, "Avg response:", f"{m.get('avg_response_time', 0):.1f} steps", x + 8, cy)
        cy = self.draw_kv(surface, "Mission:", self.sim.mission_status, x + 8, cy)

        # Stale indicator
        age = time.time() - self.sim.fetched_at
        age_col = Colors.GREEN if age < 10 else (Colors.YELLOW if age < 30 else Colors.RED)
        cy += 8
        cy = self.draw_kv(surface, "Data age:", f"{age:.0f}s", x + 8, cy, val_color=age_col)
        cy = self.draw_kv(surface, "Sim duration:", f"{m.get('simulation_duration_sec', 0):.1f}s",
                          x + 8, cy)

    def _draw_events(self, surface, rect):
        self.draw_panel(surface, rect, "Recent Events - newest first")
        events = self.sim.event_log[-50:][::-1]  # Last 50

        if not events:
            f = Fonts.mono(10)
            t = f.render("No events yet.", True, Colors.TEXT_MUTED)
            surface.blit(t, (rect.x + 8, rect.y + 28))
            return

        clip = surface.get_clip()
        inner = pygame.Rect(rect.x + 4, rect.y + 24, rect.width - 8, rect.height - 28)
        surface.set_clip(inner)

        line_h = 15
        total_h = len(events) * line_h
        max_scroll = max(0, total_h - inner.height)
        self._event_scroll = min(self._event_scroll, max_scroll)

        f = Fonts.mono(9)
        for i, ev in enumerate(events):
            ey = inner.y + i * line_h - self._event_scroll
            if ey + line_h < inner.y or ey > inner.bottom:
                continue
            etype = ev.get("type", "")
            msg   = " ".join(str(ev.get("message", str(ev))).split())
            step  = ev.get("step", 0)

            color_map = {
                "FLOOD": Colors.YELLOW, "ROUTING": Colors.ACCENT_CYAN,
                "AMBULANCE": Colors.AMBULANCE, "ML": Colors.PURPLE,
                "SIMULATION": Colors.TEXT_SECONDARY
            }
            col = color_map.get(etype, Colors.TEXT_MUTED)
            line = f"[S{step:02d}] [{etype:<10}] {msg}"
            t = f.render(line[:140], True, col)
            surface.blit(t, (inner.x + 4, ey))

        surface.set_clip(clip)
