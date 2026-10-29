# screens/route_lab.py — Route Lab Screen
# Allows: select src/dst, run backend A*, run reference Dijkstra,
# compare results on identical endpoints, visualize path, inspect per-edge costs.

import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout
from components.buttons import Button, draw_rect_rounded, TextInput
from visualization.graph_renderer import GraphRenderer
from algorithms.reference_dijkstra import dijkstra, validate_path, compute_path_breakdown


class RouteLabScreen(BaseScreen):

    def __init__(self, app, rect):
        super().__init__(app, rect)

        panel_w = 340
        self._map_rect  = pygame.Rect(rect.x, rect.y, rect.width - panel_w, rect.height)
        self._ctrl_rect = pygame.Rect(rect.x + rect.width - panel_w, rect.y, panel_w, rect.height)

        self._renderer = GraphRenderer(self._map_rect)
        self._renderer.show_labels = True

        by = rect.y + 8
        bx = self._ctrl_rect.x + 8
        bw = panel_w - 20

        self._inp_src = TextInput((bx, by + 20, bw, 24), placeholder="Source label e.g. A1", font_size=11)
        self._inp_dst = TextInput((bx, by + 60, bw, 24), placeholder="Dest label  e.g. O15", font_size=11)
        self._btn_run = Button("CALCULATE ROUTE", (bx, by + 96, bw, 28), style="primary", font_size=11)
        self._btn_clear = Button("CLEAR", (bx, by + 132, bw // 2 - 4, 24), style="neutral", font_size=10)
        self._btn_fit   = Button("FIT MAP", (bx + bw // 2, by + 132, bw // 2 - 4, 24), style="neutral", font_size=10)

        self._result: dict = None               # reference Dijkstra result
        self._backend_route: dict = None        # F16: Backend A* route result for same endpoints
        self._validation: dict = None           # reference Dijkstra validation
        self._backend_validation: dict = None   # backend A* validation vs Dijkstra
        self._breakdown: list = []
        self._scroll  = 0
        self._src_id  = None
        self._dst_id  = None
        self._error_msg = ""
        self._request_id = 0
        self._pending = False
        self._route_graph = None
        self._travel_mode='normal'
        self._validation_edges=[]
        self._mode_button=Button('ROUTING: NORMAL / COMMERCIAL',(bx,by+90,bw,28),font_size=11)

    def _label_to_id(self, label: str):
        """Convert grid label (e.g. 'A1') to sector id."""
        label = label.strip().upper()
        if len(label) < 2:
            return None
        try:
            col = ord(label[0]) - 65
            row = int(label[1:]) - 1
            for nid, nd in self.graph.nodes.items():
                if nd["col"] == col and nd["row"] == row:
                    return nid
        except (ValueError, IndexError):
            pass
        return None

    def _id_to_label(self, nid: int) -> str:
        nd = self.graph.nodes.get(nid, {})
        if not nd:
            return f"#{nid}"
        return f"{chr(65+nd.get('col',0))}{nd.get('row',0)+1}"

    def handle_event(self, event):
        self._inp_src.handle_event(event)
        self._inp_dst.handle_event(event)

        if self._renderer.handle_event(event):
            return
        if self._mode_button.handle_event(event):
            self._travel_mode='normal' if self._travel_mode=='ambulance' else 'ambulance'
            self._invalidate_route()
            self._error_msg=''
            return

        if self._btn_run.handle_event(event):
            self._run_route()
        if self._btn_clear.handle_event(event):
            self._clear()
        if self._btn_fit.handle_event(event):
            self._renderer.fit_to_view(self.graph.grid_rows, self.graph.grid_cols)

        if event.type == pygame.MOUSEWHEEL:
            if self._ctrl_rect.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                self._scroll = max(0, self._scroll - event.y * 16)

        # Node click on map → auto-fill src/dst
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._map_rect.collidepoint(mx, my):
                nid = self._renderer.hit_test_node(mx, my, self.graph.nodes)
                if nid is not None:
                    lbl = self._id_to_label(nid)
                    if self._inp_src.focused or not self._inp_src.text:
                        self._inp_src.text = lbl
                    else:
                        self._inp_dst.text = lbl

    def update(self, dt: float):
        self._inp_src.update(dt)
        self._inp_dst.update(dt)

    def _run_route(self):
        self._error_msg = ""
        # F25: Cleanly clear old visual and validation state before computing
        self._result = None
        self._backend_route = None
        self._validation = None
        self._backend_validation = None
        self._breakdown = []
        self._renderer.route_paths = []
        self._renderer.highlighted_nodes = set()
        self.state.route_validation = None

        src_id = self._label_to_id(self._inp_src.text)
        dst_id = self._label_to_id(self._inp_dst.text)

        if src_id is None:
            self._error_msg = f"Unknown source: '{self._inp_src.text}'"
            return
        if dst_id is None:
            self._error_msg = f"Unknown destination: '{self._inp_dst.text}'"
            return

        self._src_id = src_id
        self._dst_id = dst_id

        # 1. Run reference Dijkstra
        self._validation_edges=([{**e,'blocked':e.get('blocked',False) or e.get('temporarily_blocked',False)} for e in self.graph.edges]
                                if self._travel_mode=='normal' else self.graph.edges)
        self._result = dijkstra(self.graph.nodes, self._validation_edges, src_id, dst_id)

        self._request_id += 1
        ticket = self._request_id
        self._route_graph = (self.graph.nodes, self.graph.edges, self.sim.sim_id, self.sim.revision)
        if hasattr(self.app, "client") and hasattr(self.app, "run_query"):
            self._pending = True
            self._btn_run.enabled = False
            self._btn_run.label = "CALCULATING..."
            identity = (self.sim.sim_id, self.sim.revision)
            def done(data):
                if ticket != self._request_id:
                    return
                if identity != (self.sim.sim_id, self.sim.revision):
                    self._invalidate_route()
                    return
                self._pending = False
                self._btn_run.enabled = True
                self._btn_run.label = "CALCULATE ROUTE"
                if data.get("sim_id", identity[0]) != identity[0] or data.get("revision", identity[1]) != identity[1]:
                    self._invalidate_route()
                    return
                self._backend_route = data
                self._finish_route(src_id, dst_id)
            def failed(error):
                if ticket == self._request_id:
                    self._pending = False
                    self._btn_run.enabled = True
                    self._btn_run.label = "CALCULATE ROUTE"
                    self._error_msg = str(error)
                    self._finish_route(src_id, dst_id)
            mode=self._travel_mode
            self.app.run_query(lambda: self.app.client.calculate_route(src_id,dst_id,mode), done, failed)
            return
        self._finish_route(src_id, dst_id)

    def _finish_route(self, src_id, dst_id):
        # 3. Validate reference path (F18, F22)
        self._validation = validate_path(
            self._result["path"],
            self.graph.nodes,
            self._validation_edges,
            claimed_cost     = self._result["path_cost"],
            check_optimality = False,
            expected_source  = src_id,
            expected_target  = dst_id,
        )

        # 4. Validate backend A* route against reference Dijkstra (F22)
        if self._backend_route and self._backend_route.get("reachable"):
            b_path = self._backend_route.get("path", [])
            b_cost = self._backend_route.get("path_cost")
            self._backend_validation = validate_path(
                b_path,
                self.graph.nodes,
                self._validation_edges,
                claimed_cost     = b_cost,
                check_optimality = True,
                expected_source  = src_id,
                expected_target  = dst_id,
            )
            self.state.route_validation = self._backend_validation

        # 5. Per-edge breakdown for reference path
        self._breakdown = compute_path_breakdown(
            self._result["path"], self.graph.nodes, self._validation_edges
        )

        # 6. F15: Highlight distinct routes on map without confusing endpoints
        paths = []
        if self._result.get("reachable") and self._result["path"]:
            paths.append({"path": self._result["path"], "color": Colors.ACCENT_CYAN})

        if self._backend_route and self._backend_route.get("reachable") and self._backend_route["path"]:
            b_path = self._backend_route["path"]
            if b_path != self._result["path"]:
                paths.append({"path": b_path, "color": (200, 100, 255)})

        # Separate active simulation mission (if present)
        active_sim_route = self.sim.active_routes
        if active_sim_route and self._travel_mode=='ambulance':
            paths.append({"path": active_sim_route, "color": Colors.ACCENT_AMBER})

        self._renderer.route_paths = paths
        self._renderer.selected_node = None
        self._renderer.highlighted_nodes = {src_id, dst_id}

        self.state.local_log.add(
            f"Route Lab: {self._inp_src.text}→{self._inp_dst.text} "
            f"Dijkstra={self._result['path_cost']:.3f} "
            f"A*={self._backend_route.get('path_cost', 'N/A') if self._backend_route else 'N/A'}",
            category="ROUTE"
        )

    def _invalidate_route(self):
        self._request_id += 1
        self._pending = False
        self._btn_run.enabled = True
        self._btn_run.label = "CALCULATE ROUTE"
        self._result = self._backend_route = self._validation = self._backend_validation = None
        self._breakdown = []
        self._renderer.route_paths = []
        self._renderer.highlighted_nodes = set()
        self._error_msg = "City changed. Calculate the route again."
        self.state.route_validation = None

    def on_state_updated(self):
        if self._route_graph:
            nodes, edges, identity, revision = self._route_graph
            if nodes is not self.graph.nodes or edges is not self.graph.edges or identity != self.sim.sim_id or revision != self.sim.revision:
                self._invalidate_route()
                self._route_graph = None

    def _clear(self):
        self._request_id += 1
        self._pending = False
        self._btn_run.enabled = True
        self._btn_run.label = "CALCULATE ROUTE"
        self._route_graph = None
        self._result = None
        self._backend_route = None
        self._validation = None
        self._backend_validation = None
        self._breakdown = []
        self._renderer.route_paths = []
        self._renderer.highlighted_nodes = set()
        self._error_msg = ""
        self._inp_src.text = ""
        self._inp_dst.text = ""
        self._src_id = None
        self._dst_id = None
        self.state.route_validation = None

    def on_enter(self):
        self._renderer.fit_to_view(self.graph.grid_rows, self.graph.grid_cols)

    def draw(self, surface):
        self._renderer.team_node = self.sim.router.get("current_pos") if self._travel_mode=='ambulance' else None
        self._renderer.gate_zones=self.sim.disasters.get('gates',[])
        # Map area
        pygame.draw.rect(surface, Colors.BG_DEEP, self._map_rect)
        if self.graph.nodes:
            self._renderer.draw(
                surface, self.graph.nodes, self.graph.edges,
                risk_predictions=self.sim.risk_predictions,
                ambulance_nodes=self.sim.ambulances,
                route_paths=self._renderer.route_paths,
            )
        else:
            self.draw_not_connected(surface)

        # Control panel
        self._draw_control_panel(surface)

    def _draw_control_panel(self, surface):
        rect = self._ctrl_rect
        pygame.draw.rect(surface, Colors.BG_PANEL, rect)
        pygame.draw.line(surface, Colors.BORDER, rect.topleft, rect.bottomleft)

        y = rect.y + 8
        f_title = Fonts.bold(11)
        t = f_title.render("ROUTE LAB — DUAL ALGORITHM", True, Colors.ACCENT_CYAN)
        surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 6

        # Legend / instructions
        f = Fonts.mono(9)
        t2 = f.render("Compare Dijkstra & A* on same endpoints", True, Colors.TEXT_MUTED)
        surface.blit(t2, (rect.x + 8, y)); y += t2.get_height() + 4
        self._mode_button.label='ROUTING: AMBULANCE' if self._travel_mode=='ambulance' else 'ROUTING: NORMAL / COMMERCIAL'
        self._mode_button.rect.y=y
        self._mode_button.draw(surface)
        y+=38

        # Inputs
        t = Fonts.mono(10).render("Source sector:", True, Colors.TEXT_MUTED)
        surface.blit(t, (rect.x + 8, y + 6))
        self._inp_src.rect.y = y + 20
        self._inp_src.draw(surface)
        y += 50

        t = Fonts.mono(10).render("Destination sector:", True, Colors.TEXT_MUTED)
        surface.blit(t, (rect.x + 8, y))
        self._inp_dst.rect.y = y + 14
        self._inp_dst.draw(surface)
        y += 50

        self._btn_run.rect.y   = y
        self._btn_clear.rect.y = y + 34
        self._btn_fit.rect.y   = y + 34
        self._btn_run.draw(surface)
        self._btn_clear.draw(surface)
        self._btn_fit.draw(surface)
        y += 68

        if self._error_msg:
            fe = Fonts.mono(9)
            te = fe.render(self._error_msg, True, Colors.RED)
            surface.blit(te, (rect.x + 8, y)); y += te.get_height() + 4

        # Results
        if self._result:
            y = self._draw_results(surface, rect, y)

    def _draw_results(self, surface, rect, y):
        res = self._result
        f   = Fonts.mono(10)
        fb  = Fonts.bold(10)

        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 6

        def kv(label, val, col=Colors.TEXT_PRIMARY):
            nonlocal y
            tl = f.render(label, True, Colors.TEXT_MUTED)
            tv = f.render(str(val), True, col)
            surface.blit(tl, (rect.x + 8, y))
            surface.blit(tv, (rect.x + 160, y))
            y += tl.get_height() + 3

        # ── 1. Reference Dijkstra ──
        reachable = res["reachable"]
        t = fb.render("1. REFERENCE DIJKSTRA (CYAN)", True, Colors.ACCENT_CYAN)
        surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 4

        kv("Reachable:", "YES" if reachable else "NO",
           Colors.GREEN if reachable else Colors.RED)
        if reachable:
            kv("Total cost:", f"{res['path_cost']:.4f}", Colors.ACCENT_CYAN)
            kv("Hops:", str(res["hops"]))
            kv("Sectors in path:", str(len(res["path"])))

        if self._validation:
            v = self._validation
            kv("Path valid:", "YES" if v["valid"] else "NO",
               Colors.GREEN if v["valid"] else Colors.RED)
            for issue in v.get("issues", []):
                ti = f.render(f"  ⚠ {issue[:42]}", True, Colors.YELLOW)
                surface.blit(ti, (rect.x + 8, y)); y += ti.get_height() + 2

        # ── 2. Backend A* (Same Endpoints) ──
        if self._backend_route:
            pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 4
            t = fb.render("2. BACKEND A* SEARCH (PURPLE)", True, (200, 100, 255))
            surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 4

            b_reach = self._backend_route.get("reachable", False)
            kv("Reachable:", "YES" if b_reach else "NO",
               Colors.GREEN if b_reach else Colors.RED)
            if b_reach:
                kv("A* path cost:", f"{self._backend_route.get('path_cost', 0):.4f}")
                kv("A* hops:", str(self._backend_route.get("hops", 0)))
                bv = self._backend_validation
                if bv:
                    kv("A* optimal:", "YES" if bv.get("optimal") else "NO",
                       Colors.GREEN if bv.get("optimal") else Colors.RED)

        # ── 3. Active Emergency Mission ──
        backend_route = self.sim.active_routes
        if backend_route and self._travel_mode=='ambulance':
            pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 4
            t = fb.render("ACTIVE RESCUE MISSION (AMBER)", True, Colors.ACCENT_AMBER)
            surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 4
            src_lbl = self._id_to_label(backend_route[0])
            dst_lbl = self._id_to_label(backend_route[-1])
            kv("Mission route:", f"{src_lbl} → {dst_lbl}")
            kv("Sectors left:", str(len(backend_route)))

        # ── 4. Per-edge breakdown (scrollable) ──
        if self._breakdown:
            pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 4
            t = fb.render("PER-EDGE BREAKDOWN", True, Colors.TEXT_MUTED)
            surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 4

            clip = surface.get_clip()
            breakdown_rect = pygame.Rect(rect.x, y, rect.width, rect.bottom - y - 4)
            surface.set_clip(breakdown_rect)

            line_h = 14
            total_h = len(self._breakdown) * line_h * 2
            max_scroll = max(0, total_h - breakdown_rect.height)
            self._scroll = min(self._scroll, max_scroll)

            fy = y - self._scroll
            for bd in self._breakdown:
                if fy + line_h * 2 < y or fy > rect.bottom:
                    fy += line_h * 2
                    continue
                t1 = f.render(f"  {bd['from_label']} → {bd['to_label']}", True, Colors.TEXT_SECONDARY)
                surface.blit(t1, (rect.x + 4, fy)); fy += line_h
                cost_col = Colors.RED if bd["blocked"] else Colors.ACCENT_CYAN
                t2 = f.render(f"    base={bd['base_cost']:.2f}  ×{bd['risk_mult']}  "
                              f"eff={bd['effective_cost']:.3f}  [{bd['risk_level']}]",
                              True, cost_col)
                surface.blit(t2, (rect.x + 4, fy)); fy += line_h

            surface.set_clip(clip)

        return y

