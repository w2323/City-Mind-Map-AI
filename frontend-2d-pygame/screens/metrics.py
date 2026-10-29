# screens/metrics.py — Metrics & Event Log Screen

import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout
from components.buttons import Button


class MetricsScreen(BaseScreen):
    """
    Full metrics dashboard + scrollable event log.
    Displays ALL metrics from SimulationMetrics.to_dict()
    and the backend event history.
    """

    def __init__(self, app, rect):
        super().__init__(app, rect)
        self._event_scroll  = 0
        self._log_scroll    = 0
        self._filter        = "ALL"  # ALL | FLOOD | ROUTING | AMBULANCE | ML
        self._btn_export = Button("EXPORT CSV", (rect.right-126, rect.y+8, 118, 22), style="primary", font_size=10)
        self._filter_btns = []
        for f_name in ["ALL", "FLOOD", "ROUTING", "AMBULANCE", "ML"]:
            self._filter_btns.append(Button(f_name, (0,0,60,20), style="primary" if f_name=="ALL" else "neutral", font_size=9))

    def handle_event(self, event):
        if self._btn_export.handle_event(event) and hasattr(self.app, "async_export_metrics"):
            self.app.async_export_metrics()
        bx = self.rect.x + 8
        for i, btn in enumerate(self._filter_btns):
            btn.rect = pygame.Rect(bx + i * 68, self.rect.y + 8, 64, 22)
            if btn.handle_event(event):
                self._filter = ["ALL", "FLOOD", "ROUTING", "AMBULANCE", "ML"][i]
                for j, b in enumerate(self._filter_btns):
                    b.style = "primary" if j == i else "neutral"

        if event.type == pygame.MOUSEWHEEL:
            mx, my = getattr(event, "pos", pygame.mouse.get_pos())
            mid = self.rect.centerx
            if mx > mid:
                self._event_scroll  = max(0, self._event_scroll  - event.y * 14)
            else:
                self._log_scroll    = max(0, self._log_scroll    - event.y * 14)

    def draw(self, surface):
        rect = self.rect
        pygame.draw.rect(surface, Colors.BG_DEEP, rect)

        self._btn_export.enabled = self.state.is_connected and not getattr(getattr(self.app, "query_runner", None), "is_running", False)
        self._btn_export.draw(surface)

        # Filter buttons
        bx = rect.x + 8
        for i, btn in enumerate(self._filter_btns):
            btn.rect = pygame.Rect(bx + i * 68, rect.y + 8, 64, 22)
            btn.draw(surface)

        y0 = rect.y + 38
        half = rect.width // 2

        # Left: KPI metrics
        self._draw_metrics(surface, pygame.Rect(rect.x, y0, half - 4, rect.height - (y0 - rect.y) - 4))

        # Right: Event log
        self._draw_event_log(surface, pygame.Rect(rect.x + half, y0, half - 4, rect.height - (y0 - rect.y) - 4))

    def _draw_metrics(self, surface, rect):
        self.draw_panel(surface, rect, "KPI Metrics")
        m = self.sim.metrics
        y = rect.y + 28
        x = rect.x + 8

        fb = Fonts.bold(10)
        fm = Fonts.mono(10)

        def kv(label, val, col=Colors.ACCENT_CYAN):
            nonlocal y
            tl = fm.render(label, True, Colors.TEXT_MUTED)
            tv = fm.render(str(val), True, col)
            surface.blit(tl, (x, y))
            surface.blit(tv, (x + 200, y))
            y += tl.get_height() + 4

        def section(title):
            nonlocal y
            y += 4
            t = fb.render(title, True, Colors.TEXT_SECONDARY)
            surface.blit(t, (x, y))
            y += t.get_height() + 4
            pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y))
            y += 4

        section("Simulation")
        kv("Total floods:",          m.get("total_floods", "?"),            Colors.YELLOW)
        kv("Total reroutes:",         m.get("total_reroutes", "?"))
        kv("Civilians rescued:",      m.get("civilians_rescued", "?"),       Colors.GREEN)
        kv("Civilians unreachable:",  m.get("civilians_unreachable", "?"),   Colors.RED)
        kv("Ambulance repositions:", m.get("ambulance_repositions", "?"))

        section("Performance")
        kv("Avg response time:",     m.get("avg_response_time", "?"))
        kv("Worst response time:",   m.get("worst_response_time", "?"),     Colors.RED)
        kv("GA best fitness:",       m.get("ga_best_fitness", "?"),         Colors.ACCENT_CYAN)
        kv("Sim duration (s):",      m.get("simulation_duration_sec", "?"))

        section("Graph")
        kv("Active edges:",          m.get("total_edges_active", "?"),      Colors.GREEN)
        kv("Blocked edges:",         m.get("total_edges_blocked", "?"),     Colors.RED)
        kv("Disconnected sectors:",    m.get("disconnected_nodes", "?"),      Colors.YELLOW)

        section("Risk Zones")
        kv("High risk:",             m.get("high_risk_zones", "?"),         Colors.RISK_HIGH)
        kv("Medium risk:",           m.get("medium_risk_zones", "?"),       Colors.RISK_MEDIUM)
        kv("Low risk:",              m.get("low_risk_zones", "?"),          Colors.RISK_LOW)

        # Local app log
        section("App Log (Local)")
        app_log = self.state.local_log.entries()
        for entry in app_log[-5:]:
            col_map = {"error": Colors.RED, "warning": Colors.YELLOW}
            col = col_map.get(entry["level"], Colors.TEXT_MUTED)
            t = Fonts.mono(9).render(f"[{entry['ts']}] {entry['msg'][:50]}", True, col)
            surface.blit(t, (x, y))
            y += t.get_height() + 2

    def _draw_event_log(self, surface, rect):
        self.draw_panel(surface, rect, "Backend Event Log")

        events = self.sim.event_log[::-1]
        if self._filter != "ALL":
            events = [e for e in events if e.get("type", "") == self._filter]

        clip = surface.get_clip()
        inner = pygame.Rect(rect.x + 4, rect.y + 28, rect.width - 8, rect.height - 32)
        surface.set_clip(inner)

        line_h = 14
        total_h = len(events) * line_h
        max_scroll = max(0, total_h - inner.height)
        self._event_scroll = min(self._event_scroll, max_scroll)

        f = Fonts.mono(9)
        color_map = {
            "FLOOD":      Colors.YELLOW,
            "ROUTING":    Colors.ACCENT_CYAN,
            "AMBULANCE":  Colors.AMBULANCE,
            "ML":         Colors.PURPLE,
            "LAYOUT":     Colors.TEXT_SECONDARY,
            "ROADS":      Colors.GREEN_D,
            "SIMULATION": Colors.TEXT_SECONDARY,
            "METRIC":     Colors.TEXT_MUTED,
        }

        for i, ev in enumerate(events):
            ey = inner.y + i * line_h - self._event_scroll
            if ey + line_h < inner.y or ey > inner.bottom:
                continue
            etype = ev.get("type", "")
            msg   = " ".join(str(ev.get("message", "")).split())
            step  = ev.get("step", 0)
            col   = color_map.get(etype, Colors.TEXT_MUTED)
            line  = f"[S{step:02d}][{etype[:8]:<8}] {msg}"
            t = f.render(line[:120], True, col)
            surface.blit(t, (inner.x + 2, ey))

        surface.set_clip(clip)

        # Event count
        fb = Fonts.mono(9)
        ct = fb.render(f"  {len(events)} events", True, Colors.TEXT_MUTED)
        surface.blit(ct, (rect.x + 4, rect.bottom - 18))
