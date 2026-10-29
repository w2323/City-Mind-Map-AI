# screens/ambulance.py — Ambulance Center Screen

import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout
from components.buttons import Button, draw_rect_rounded
from visualization.graph_renderer import GraphRenderer
from algorithms.reference_dijkstra import dijkstra, validate_path


class AmbulanceScreen(BaseScreen):
    """
    Ambulance Center:
    - View current ambulance placements.
    - View active mission (router state).
    - View civilian targets.
    - Route validation: check each ambulance can reach each civilian.
    - Show GA fitness score and placement optimality context.
    - Validate active route after every state update.
    """

    def __init__(self, app, rect):
        super().__init__(app, rect)

        panel_w = 320
        self._map_rect  = pygame.Rect(rect.x, rect.y, rect.width - panel_w, rect.height)
        self._ctrl_rect = pygame.Rect(rect.x + rect.width - panel_w, rect.y, panel_w, rect.height)
        self._renderer  = GraphRenderer(self._map_rect)

        bx = self._ctrl_rect.x + 8
        bw = self._ctrl_rect.width - 16

        self._btn_validate = Button("VALIDATE ROUTES", (bx, 0, bw, 28), style="primary", font_size=11)
        self._btn_step     = Button("STEP", (bx, 0, bw // 2 - 4, 26), style="neutral", font_size=10)

        self._ga_start = Button("OPTIMIZE", (bx, self._ctrl_rect.y + 78, 98, 26), style="success", font_size=10)
        self._ga_pause = Button("PAUSE", (bx + 102, self._ctrl_rect.y + 78, 98, 26), font_size=10)
        self._ga_reset = Button("RESET", (bx + 204, self._ctrl_rect.y + 78, 98, 26), font_size=10)
        self._scroll = 0
        self._validation_results: list = []  # per-ambulance validation reports
        self._active_route_validation = None
        self._validation_key = None

    def on_enter(self):
        self._renderer.fit_to_view(self.graph.grid_rows, self.graph.grid_cols)
        self._run_validation()

    def on_state_updated(self):
        self._run_validation()

    def _run_validation(self):
        """Validate the active route and compute nearest ambulance to each civilian."""
        key = (id(self.graph.nodes), id(self.graph.edges), tuple(self.sim.ambulances),
               tuple(self.sim.civilians), tuple(self.sim.active_routes))
        if key == self._validation_key:
            return
        self._validation_key = key
        self._validation_results = []
        if not self.graph.nodes:
            return

        router = self.sim.router
        active_route = self.sim.active_routes
        ambulances   = self.sim.ambulances
        civilians    = self.sim.civilians

        # Validate active route
        if active_route:
            self._active_route_validation = validate_path(
                active_route, self.graph.nodes, self.graph.edges,
                check_optimality=True
            )
        else:
            self._active_route_validation = None

        distances = {amb: dijkstra(self.graph.nodes, self.graph.edges, amb) for amb in ambulances}

        # For each civilian, check reachability from each ambulance
        for civ_id in civilians[:5]:  # limit to 5 for performance
            civ_results = {"civ_id": civ_id, "from_ambulances": []}
            for amb_id in ambulances:
                tree = distances[amb_id]
                cost = tree["dist"].get(civ_id, float("inf"))
                hops, current = 0, civ_id
                while tree["prev"].get(current) is not None:
                    hops += 1
                    current = tree["prev"][current]
                ref = {"reachable": cost < float("inf"), "path_cost": cost, "hops": hops}
                civ_results["from_ambulances"].append({
                    "amb_id":    amb_id,
                    "reachable": ref["reachable"],
                    "cost":      ref["path_cost"],
                    "hops":      ref["hops"],
                })
            self._validation_results.append(civ_results)

    def handle_event(self, event):
        for button, action in ((self._ga_start, "start"), (self._ga_pause, "pause"), (self._ga_reset, "reset")):
            if button.handle_event(event) and hasattr(self.app, "async_optimization"):
                self.app.async_optimization(action)
                return
        self._renderer.handle_event(event)
        bx = self._ctrl_rect.x + 8
        bw = self._ctrl_rect.width - 16
        self._btn_validate.rect = pygame.Rect(bx, self._ctrl_rect.y + 8, bw, 28)
        self._btn_step.rect     = pygame.Rect(bx, self._ctrl_rect.y + 44, bw, 26)

        if self._btn_validate.handle_event(event):
            self._run_validation()
        if self._btn_step.handle_event(event):
            self.app.async_step()

        if event.type == pygame.MOUSEWHEEL:
            if self._ctrl_rect.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                self._scroll = max(0, self._scroll - event.y * 14)

    def update(self, dt: float):
        self._renderer.ambulance_nodes = self.sim.ambulances
        self._renderer.civilian_nodes  = self.sim.civilians
        ar = self.sim.active_routes
        self._renderer.route_paths = [{"path": ar, "color": Colors.EDGE_ROUTE}] if ar else []

    def draw(self, surface):
        self._renderer.team_node = self.sim.router.get("current_pos")
        pygame.draw.rect(surface, Colors.BG_DEEP, self._map_rect)
        if self.graph.nodes:
            self._renderer.draw(
                surface, self.graph.nodes, self.graph.edges,
                risk_predictions=self.sim.risk_predictions,
                ambulance_nodes=self.sim.ambulances,
                civilian_nodes=self.sim.civilians,
                route_paths=self._renderer.route_paths,
            )

        self._draw_panel(surface)

    def _draw_panel(self, surface):
        rect = self._ctrl_rect
        pygame.draw.rect(surface, Colors.BG_PANEL, rect)
        pygame.draw.line(surface, Colors.BORDER, rect.topleft, rect.bottomleft)

        bx = rect.x + 8
        bw = rect.width - 16
        self._btn_validate.rect = pygame.Rect(bx, rect.y + 8, bw, 28)
        self._btn_step.rect     = pygame.Rect(bx, rect.y + 44, bw // 2 - 4, 26)
        self._btn_validate.draw(surface)
        self._btn_step.draw(surface)
        status = self.sim.optimization.get("status", "idle")
        busy = getattr(getattr(self.app, "op_runner", None), "is_running", False)
        self._ga_start.label = "RESUME" if status == "paused" else "OPTIMIZE"
        self._ga_start.enabled = self.state.is_connected and status != "running" and not busy
        self._ga_pause.enabled = status == "running" and not busy
        self._ga_reset.enabled = status != "idle" and not busy
        for button in (self._ga_start, self._ga_pause, self._ga_reset):
            button.draw(surface)
        job = self.sim.optimization
        label = f"GA: {status} | generation {job.get('generation', 0)} / {self.sim.config.get('ga_generations', '?')}"
        surface.blit(Fonts.mono(10).render(label, True, Colors.ACCENT_CYAN), (bx, rect.y + 111))

        clip = surface.get_clip()
        content_rect = pygame.Rect(rect.x, rect.y + 138, rect.width, rect.height - 138)
        surface.set_clip(content_rect)

        y = content_rect.y - self._scroll
        f  = Fonts.mono(10)
        fb = Fonts.bold(10)

        # ── GA Placement Info ───────────────────────────────────────────────
        t = fb.render("LIVE MEDICAL-CENTER FLEET", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, y)); y += t.get_height() + 4
        t_note = f.render("Dispatch and radius controls: Dispatch tab", True, Colors.TEXT_MUTED)
        surface.blit(t_note, (bx, y)); y += t_note.get_height() + 4

        m = self.sim.metrics
        fitness = m.get("ga_best_fitness", None)
        fitness_str = f"{fitness:.4f}" if fitness is not None and fitness != float("inf") else "N/A"
        y = self.draw_kv(surface, "GA candidate cost:", fitness_str, bx, y, val_color=Colors.ACCENT_CYAN)
        y = self.draw_kv(surface, "GA evaluations:", str(m.get("ambulance_repositions", "?")), bx, y)
        sites=', '.join(self.graph.nodes[n].get('label',str(n)) for n in self.sim.optimized_placements if n in self.graph.nodes)
        y = self.draw_kv(surface, 'Proposed sites:', sites, bx, y, font_size=10)

        ambulances = self.sim.ambulances
        y = self.draw_kv(surface, "Ambulances placed:", str(len(ambulances)), bx, y)
        for i, amb_id in enumerate(ambulances):
            nd = self.graph.nodes.get(amb_id, {})
            col_n = nd.get("col", 0)
            row_n = nd.get("row", 0)
            lbl = f"{chr(65+col_n)}{row_n+1}"
            t = f.render(f"  #{i+1}: sector {amb_id}  ({lbl}  {nd.get('node_type','?')})",
                         True, Colors.AMBULANCE)
            surface.blit(t, (bx, y)); y += t.get_height() + 2

        y += 6
        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 6

        # ── Router Mission ──────────────────────────────────────────────────
        t = fb.render("CURRENT EMERGENCY ROUTE", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, y)); y += t.get_height() + 4
        t_rm = f.render("Nearest available unit by live road cost", True, Colors.TEXT_MUTED)
        surface.blit(t_rm, (bx, y)); y += t_rm.get_height() + 4

        router = self.sim.router
        cur_pos = router.get("current_pos")
        if cur_pos is not None:
            nd = self.graph.nodes.get(cur_pos, {})
            lbl = f"{chr(65+nd.get('col',0))}{nd.get('row',0)+1}"
            y = self.draw_kv(surface, "Current pos:", f"{lbl} (#{cur_pos})", bx, y)

        civs_rem = router.get("civilians_remaining", [])
        civs_res = router.get("civilians_rescued", [])
        reroutes  = router.get("total_reroutes", 0)
        y = self.draw_kv(surface, "Active emergencies:", str(len(civs_rem)), bx, y,
                         val_color=Colors.YELLOW)
        y = self.draw_kv(surface, "Rescued:", str(len(civs_res)), bx, y, val_color=Colors.GREEN)
        y = self.draw_kv(surface, "Reroutes:", str(reroutes), bx, y)

        ar = self.sim.active_routes
        y = self.draw_kv(surface, "Active route:", f"{len(ar)} sectors", bx, y)

        # Active route validation
        if self._active_route_validation:
            v = self._active_route_validation
            col = Colors.GREEN if v["valid"] else Colors.RED
            y = self.draw_kv(surface, "Route valid:", "YES" if v["valid"] else "NO", bx, y, val_color=col)
            opt = v.get("optimal")
            if opt is not None:
                col2 = Colors.GREEN if opt else Colors.RED
                y = self.draw_kv(surface, "Optimal:", "YES" if opt else "NO", bx, y, val_color=col2)
            if v.get("actual_cost", 0) < float("inf"):
                y = self.draw_kv(surface, "Route cost:", f"{v['actual_cost']:.4f}", bx, y)
            for issue in v.get("issues", []):
                ti = f.render(f"  ⚠ {issue[:50]}", True, Colors.YELLOW)
                surface.blit(ti, (bx, y)); y += ti.get_height() + 2

        y += 6
        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 6

        # ── Reachability matrix ─────────────────────────────────────────────
        t = fb.render("EMERGENCY REACHABILITY", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, y)); y += t.get_height() + 2
        t_sub = f.render("Road cost from current unit positions", True, Colors.TEXT_MUTED)
        surface.blit(t_sub, (bx, y)); y += t_sub.get_height() + 4

        if not self._validation_results:
            t = f.render("No active emergencies. Add one in Dispatch.", True, Colors.TEXT_MUTED)
            surface.blit(t, (bx, y)); y += t.get_height() + 4
        else:
            for cv in self._validation_results:
                cid = cv["civ_id"]
                cnd = self.graph.nodes.get(cid, {})
                clbl = f"{chr(65+cnd.get('col',0))}{cnd.get('row',0)+1}"
                th = fb.render(f"Civilian {clbl} (#{cid})", True, Colors.CIVILIAN)
                surface.blit(th, (bx, y)); y += th.get_height() + 2
                for ar_data in cv["from_ambulances"]:
                    aid = ar_data["amb_id"]
                    and_ = self.graph.nodes.get(aid, {})
                    albl = f"{chr(65+and_.get('col',0))}{and_.get('row',0)+1}"
                    ok = ar_data["reachable"]
                    cost = ar_data["cost"]
                    cost_str = f"{cost:.3f}" if ok else "∞"
                    col = Colors.GREEN if ok else Colors.RED
                    t = f.render(f"  Amb {albl}: {'OK' if ok else 'UNREACHABLE'}  cost={cost_str}",
                                 True, col)
                    surface.blit(t, (bx, y)); y += t.get_height() + 2
                y += 3

        surface.set_clip(clip)
        # Scroll bounds
        total_h = y + self._scroll - content_rect.y
        self._scroll = min(self._scroll, max(0, total_h - content_rect.height))
