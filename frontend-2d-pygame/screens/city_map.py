# screens/city_map.py — Interactive 2D City Map Screen

import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout, NODE_TYPE_COLORS, RISK_COLORS
from components.buttons import Button, draw_rect_rounded, draw_label, draw_section_header
from visualization.graph_renderer import GraphRenderer
from presentation.sectors import sector_label,sector_description


class CityMapScreen(BaseScreen):
    """
    Main city map view with:
    - Pan/zoom (right-click drag + scroll)
    - Sector and edge selection
    - Sector/edge inspector sidebar
    - Layer selector (normal / risk / population)
    - Fit-to-view, label toggles
    """

    def __init__(self, app, rect):
        super().__init__(app, rect)

        # Map viewport (leaves room for right inspector panel)
        self._inspector_w = 260
        self._map_rect = pygame.Rect(
            rect.x, rect.y,
            rect.width - self._inspector_w, rect.height
        )
        self._insp_rect = pygame.Rect(
            rect.x + rect.width - self._inspector_w, rect.y,
            self._inspector_w, rect.height
        )

        self._renderer = GraphRenderer(pygame.Rect(self._map_rect.x, self._map_rect.y + 32, self._map_rect.width, self._map_rect.height - 32))

        # Toolbar buttons
        bx = rect.x + 4
        by = rect.y + 4
        self._btn_fit    = Button("FIT", (bx,      by, 50, 24), style="neutral", font_size=10)
        self._btn_labels = Button("LBL", (bx + 54, by, 50, 24), style="neutral", font_size=10)
        self._btn_costs  = Button("COST",(bx + 108,by, 50, 24), style="neutral", font_size=10)
        self._btn_ids    = Button("IDS", (bx + 162,by, 50, 24), style="neutral", font_size=10)

        # Layer selector
        self._layer_btns = [
            Button("NORMAL", (bx + 220, by, 70, 24), style="primary", font_size=10),
            Button("RISK",   (bx + 294, by, 60, 24), style="neutral", font_size=10),
            Button("POP",    (bx + 358, by, 50, 24), style="neutral", font_size=10),
        ]
        self._layer_names = [None, "risk", "population"]

        self._inspector_scroll = 0

    def on_enter(self):
        self._renderer.fit_to_view(
            self.graph.grid_rows, self.graph.grid_cols
        )

    def on_state_updated(self):
        pass

    def handle_event(self, event):
        # Map renderer handles pan/zoom
        if self._renderer.handle_event(event):
            return

        # Toolbar
        if self._btn_fit.handle_event(event):
            self._renderer.fit_to_view(self.graph.grid_rows, self.graph.grid_cols)
        if self._btn_labels.handle_event(event):
            self._renderer.show_labels = not self._renderer.show_labels
        if self._btn_costs.handle_event(event):
            self._renderer.show_edge_costs = not self._renderer.show_edge_costs
        if self._btn_ids.handle_event(event):
            self._renderer.show_node_ids = not self._renderer.show_node_ids

        for i, btn in enumerate(self._layer_btns):
            if btn.handle_event(event):
                self._renderer.heatmap_layer = self._layer_names[i]
                for j, b in enumerate(self._layer_btns):
                    b.style = "primary" if j == i else "neutral"

        # Node/edge selection on left-click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if self._map_rect.collidepoint(x, y) and y > self._map_rect.y + 32:
                nodes = self.graph.nodes
                edges = self.graph.edges
                nid = self._renderer.hit_test_node(x, y, nodes)
                if nid is not None:
                    self.state.selected_node = nid
                    self.state.selected_edge = None
                    self._renderer.selected_node = nid
                    self._renderer.selected_edge = None
                else:
                    edge = self._renderer.hit_test_edge(x, y, nodes, edges)
                    if edge:
                        na = edge.get("node_a")
                        nb = edge.get("node_b")
                        self.state.selected_edge = (na, nb)
                        self.state.selected_node = None
                        self._renderer.selected_edge = (na, nb)
                        self._renderer.selected_node = None

        # Inspector scroll
        if event.type == pygame.MOUSEWHEEL:
            if self._insp_rect.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                self._inspector_scroll = max(0, self._inspector_scroll - event.y * 16)

    def update(self, dt: float):
        # Keep renderer markers in sync with sim state
        self._renderer.ambulance_nodes = self.sim.ambulances
        self._renderer.civilian_nodes  = self.sim.civilians
        self._renderer.police_nodes    = [d[0] if isinstance(d, (list, tuple)) else d.get("node_id", 0)
                                          for d in self.sim.police_deployments]
        # Active route
        ar = self.sim.active_routes
        if ar:
            self._renderer.route_paths = [{"path": ar, "color": Colors.EDGE_ROUTE}]
        else:
            self._renderer.route_paths = []

    def draw(self, surface):
        self._renderer.team_node = self.sim.router.get("current_pos")
        # Toolbar strip
        pygame.draw.rect(surface, Colors.BG_PANEL,
                         pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 32))
        self._btn_fit.draw(surface)
        self._btn_labels.draw(surface)
        self._btn_costs.draw(surface)
        self._btn_ids.draw(surface)
        for btn in self._layer_btns:
            btn.draw(surface)

        # Map
        map_area = pygame.Rect(self._map_rect.x, self._map_rect.y + 32,
                               self._map_rect.width, self._map_rect.height - 32)
        self._renderer.viewport = map_area

        if not self.graph.nodes:
            pygame.draw.rect(surface, Colors.BG_DEEP, map_area)
            self.draw_not_connected(surface)
        else:
            self._renderer.draw(
                surface, self.graph.nodes, self.graph.edges,
                risk_predictions  = self.sim.risk_predictions,
                ambulance_nodes   = self.sim.ambulances,
                civilian_nodes    = self.sim.civilians,
                police_nodes      = self._renderer.police_nodes,
                route_paths       = self._renderer.route_paths,
            )

        # Inspector panel
        self._draw_inspector(surface)

        # Legend
        self._draw_legend(surface, map_area)

    def _draw_inspector(self, surface):
        rect = self._insp_rect
        pygame.draw.rect(surface, Colors.BG_PANEL, rect)
        pygame.draw.line(surface, Colors.BORDER, rect.topleft, rect.bottomleft)

        f_title = Fonts.bold(10)
        f_body  = Fonts.mono(10)

        y = rect.y + 8
        t = f_title.render("INSPECTOR", True, Colors.TEXT_MUTED)
        surface.blit(t, (rect.x + 8, y))
        y += t.get_height() + 6
        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y))
        y += 4

        content = pygame.Rect(rect.x, y, rect.width, max(1, rect.bottom-y))
        clip = surface.get_clip()
        surface.set_clip(content.clip(clip))
        start_y = y
        y -= self._inspector_scroll
        nid = self.state.selected_node
        eid = self.state.selected_edge

        if nid is not None:
            nd = self.graph.nodes.get(nid)
            if nd:
                y = self._draw_node_inspector(surface, nd, rect, y, f_title, f_body)
        elif eid is not None:
            ed = self.state.get_edge(eid[0], eid[1])
            if ed:
                y = self._draw_edge_inspector(surface, ed, rect, y, f_title, f_body)
        else:
            t = f_body.render("Click a sector or edge", True, Colors.TEXT_MUTED)
            surface.blit(t, (rect.x + 8, y))
        surface.set_clip(clip)
        self._inspector_scroll = min(self._inspector_scroll, max(0, y + self._inspector_scroll - start_y - content.height))

    def _draw_node_inspector(self, surface, nd, rect, y, f_title, f_body):
        col_id  = nd.get("col", 0)
        row_id  = nd.get("row", 0)
        label   = f"{chr(65+col_id)}{row_id+1}"
        ntype   = nd.get("node_type", "?")
        ncolor  = NODE_TYPE_COLORS.get(ntype, Colors.TEXT_SECONDARY)

        t = f_title.render(f"SECTOR  {label}  (#{nd['id']})", True, Colors.ACCENT_CYAN)
        surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 6

        def row(label, val, col=Colors.TEXT_PRIMARY):
            nonlocal y
            tl = f_body.render(label, True, Colors.TEXT_MUTED)
            tv = f_body.render(str(val), True, col)
            surface.blit(tl, (rect.x + 8, y))
            surface.blit(tv, (rect.x + 130, y))
            y += tl.get_height() + 3

        row("Land use:", sector_label(ntype).removesuffix(' sector'), ncolor)
        import textwrap
        for line in textwrap.wrap(sector_description(ntype),max(20,(rect.width-16)//6)):
            surface.blit(f_body.render(line,True,Colors.TEXT_MUTED),(rect.x+8,y))
            y+=f_body.get_height()+3
        row("Grid pos:", f"row={row_id}, col={col_id}")
        row("Sector people:", nd.get("population", "?"), Colors.TEXT_PRIMARY)
        row("Crime level:", nd.get("risk_level", "?"),
            RISK_COLORS.get(nd.get("risk_level", "NONE"), Colors.TEXT_MUTED))
        row("Risk index:", f"{nd.get('risk_index', 0):.3f}")
        row("Accessible:", "YES" if nd.get("accessible", True) else "NO",
            Colors.GREEN if nd.get("accessible", True) else Colors.RED)

        # Neighbors
        y += 4
        t = f_title.render("Neighbors:", True, Colors.TEXT_MUTED)
        surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 3
        nid = nd["id"]
        for e in self.graph.edges:
            na = e.get("node_a")
            nb = e.get("node_b")
            if na == nid or nb == nid:
                other = nb if na == nid else na
                onode = self.graph.nodes.get(other, {})
                oc = onode.get("col", 0)
                or_ = onode.get("row", 0)
                olabel = f"{chr(65+oc)}{or_+1}"
                cost   = e.get("cost", 1.0)
                blocked= e.get("blocked", False)
                bcol   = Colors.RED if blocked else Colors.TEXT_SECONDARY
                t = f_body.render(f"  → {olabel}  (cost={cost:.1f}{'  BLOCKED' if blocked else ''})",
                                  True, bcol)
                surface.blit(t, (rect.x + 4, y))
                y += t.get_height() + 2
        return y

    def _draw_edge_inspector(self, surface, ed, rect, y, f_title, f_body):
        na = ed.get("node_a")
        nb = ed.get("node_b")
        nd_a = self.graph.nodes.get(na, {})
        nd_b = self.graph.nodes.get(nb, {})

        def lbl(n): return f"{chr(65+n.get('col',0))}{n.get('row',0)+1}"

        t = f_title.render(f"EDGE  {lbl(nd_a)} ↔ {lbl(nd_b)}", True, Colors.ACCENT_AMBER)
        surface.blit(t, (rect.x + 8, y)); y += t.get_height() + 6

        def row(label, val, col=Colors.TEXT_PRIMARY):
            nonlocal y
            tl = f_body.render(label, True, Colors.TEXT_MUTED)
            tv = f_body.render(str(val), True, col)
            surface.blit(tl, (rect.x + 8, y))
            surface.blit(tv, (rect.x + 130, y))
            y += tl.get_height() + 3

        row("Sector A ID:", na)
        row("Sector B ID:", nb)
        row("Base cost:", f"{ed.get('cost', 1.0):.3f}")
        blocked = ed.get("blocked", False)
        row("Blocked:", "YES" if blocked else "NO",
            Colors.RED if blocked else Colors.GREEN)

        # Effective cost with risk
        if not blocked:
            from algorithms.reference_dijkstra import effective_cost
            eff_ab = effective_cost(ed, self.graph.nodes)
            # Flipped direction
            ed_flip = dict(ed)
            ed_flip["node_b"] = na
            ed_flip["node_a"] = nb
            eff_ba = effective_cost(ed_flip, self.graph.nodes)
            row("Effective (→B):", f"{eff_ab:.3f}", Colors.ACCENT_CYAN)
            row("Effective (→A):", f"{eff_ba:.3f}", Colors.ACCENT_CYAN)
        return y

    def _draw_legend(self, surface, map_area):
        """Draw a compact sector-type legend on the map."""
        from app.theme import NODE_TYPE_COLORS, NODE_TYPE_LABELS
        lx = map_area.x + 8
        ly = map_area.bottom - 12 - len(NODE_TYPE_COLORS) * 14
        f = Fonts.mono(8)
        for ntype, col in NODE_TYPE_COLORS.items():
            if ntype == "EMPTY":
                continue
            pygame.draw.circle(surface, col, (lx + 5, ly + 5), 5)
            t = f.render(sector_label(ntype), True, Colors.TEXT_MUTED)
            surface.blit(t, (lx + 14, ly))
            ly += 14
