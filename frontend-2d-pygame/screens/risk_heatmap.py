# screens/risk_heatmap.py — Risk & Heatmap Screen

import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts, Layout, RISK_COLORS, heat_color
from components.buttons import Button
from visualization.graph_renderer import GraphRenderer
from presentation.sectors import sector_label,sector_description,sector_text


class RiskHeatmapScreen(BaseScreen):
    """
    Risk & Heatmap visualization:
    - Risk level heatmap (HIGH/MEDIUM/LOW/NONE per sector)
    - Population density heatmap
    - Ambulance coverage layer
    - Police coverage layer
    - Sector inspector (click to see details)
    """

    LAYERS = ["Crime Heatmap", "Sector Population", "Amb. Coverage", "Police Presence"]

    def __init__(self, app, rect):
        super().__init__(app, rect)
        panel_w = 240
        self._map_rect  = pygame.Rect(rect.x, rect.y, rect.width - panel_w, rect.height)
        self._ctrl_rect = pygame.Rect(rect.x + rect.width - panel_w, rect.y, panel_w, rect.height)
        self._renderer  = GraphRenderer(self._map_rect)

        bx = self._ctrl_rect.x + 8
        bw = self._ctrl_rect.width - 16
        self._layer_btns = []
        for i, name in enumerate(self.LAYERS):
            self._layer_btns.append(
                Button(name, (bx, 0, bw, 24), style="primary" if i == 0 else "neutral", font_size=10)
            )
        self._active_layer = 0
        self._renderer.heatmap_layer = "risk"
        self._selected_node = None
        self._scroll = 0

    def on_enter(self):
        self._renderer.fit_to_view(self.graph.grid_rows, self.graph.grid_cols)

    def handle_event(self, event):
        self._renderer.handle_event(event)

        bx = self._ctrl_rect.x + 8
        bw = self._ctrl_rect.width - 16

        for i, btn in enumerate(self._layer_btns):
            btn.rect = pygame.Rect(bx, self._ctrl_rect.y + 8 + i * 30, bw, 24)
            if btn.handle_event(event):
                self._active_layer = i
                layer_map = {0: "risk", 1: "population", 2: None, 3: None}
                self._renderer.heatmap_layer = layer_map.get(i)
                for j, b in enumerate(self._layer_btns):
                    b.style = "primary" if j == i else "neutral"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._map_rect.collidepoint(mx, my):
                nid = self._renderer.hit_test_node(mx, my, self.graph.nodes)
                if nid is not None:
                    self._selected_node = nid
                    self._renderer.selected_node = nid

        if event.type == pygame.MOUSEWHEEL:
            if self._ctrl_rect.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                self._scroll = max(0, self._scroll - event.y * 14)

    def draw(self, surface):
        self._renderer.police_service={'crime_areas':self.sim.police.get('crime_areas',[])}
        self._renderer.team_node = self.sim.router.get("current_pos")
        pygame.draw.rect(surface, Colors.BG_DEEP, self._map_rect)

        # For ambulance/police coverage layers, compute coverage nodes
        route_paths = []
        if self._active_layer == 2:
            # Highlight ambulance nodes prominently
            self._renderer.highlighted_nodes = set(self.sim.dispatch_summary.get("covered_nodes", self.sim.analysis.get("coveredNodes", [])))
        elif self._active_layer == 3:
            # Highlight police nodes
            police = self.sim.police_deployments
            self._renderer.highlighted_nodes = set(
                d[0] if isinstance(d, (list, tuple)) else d.get("node_id", 0)
                for d in police
            )
        else:
            self._renderer.highlighted_nodes = set()

        if self.graph.nodes:
            self._renderer.draw(
                surface, self.graph.nodes, self.graph.edges,
                risk_predictions=self.sim.risk_predictions,
                ambulance_nodes=self.sim.ambulances if self._active_layer == 2 else [],
                police_nodes=[d[0] if isinstance(d, (list, tuple)) else d.get("node_id", 0)
                              for d in self.sim.police_deployments] if self._active_layer == 3 else [],
                route_paths=[],
            )

        self._draw_panel(surface)
        self._draw_legend(surface)

    def _draw_panel(self, surface):
        rect = self._ctrl_rect
        pygame.draw.rect(surface, Colors.BG_PANEL, rect)
        pygame.draw.line(surface, Colors.BORDER, rect.topleft, rect.bottomleft)

        bx = rect.x + 8
        bw = rect.width - 16
        f  = Fonts.bold(10)
        t = f.render("HEATMAP LAYERS", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, rect.y + 8 - t.get_height() // 2 + 12))

        for i, btn in enumerate(self._layer_btns):
            btn.rect = pygame.Rect(bx, rect.y + 8 + i * 30, bw, 24)
            btn.draw(surface)

        y = rect.y + 8 + len(self.LAYERS) * 30 + 12
        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 8

        # Selected node details
        fb = Fonts.bold(10)
        fm = Fonts.mono(10)
        t = fb.render("SECTOR INSPECTOR", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, y)); y += t.get_height() + 4

        nid = self._selected_node
        if nid is not None and nid in self.graph.nodes:
            nd = self.graph.nodes[nid]
            col_n = nd.get("col", 0)
            row_n = nd.get("row", 0)
            lbl = f"{chr(65+col_n)}{row_n+1}"
            risk = self.sim.risk_predictions.get(nid, nd.get("risk_level", "NONE"))
            pop  = nd.get("population", 0)
            risk_col = RISK_COLORS.get(risk, Colors.TEXT_MUTED)

            y = self.draw_kv(surface, "Sector:", f"{lbl} (#{nid})", bx, y, lw=100)
            y = self.draw_kv(surface, "Land use:", sector_label(nd.get("node_type", "?")).removesuffix(' sector'), bx, y, lw=100)
            y = self.draw_kv(surface, "Sector people:", str(pop), bx, y, lw=100)
            y = self.draw_kv(surface, "Crime level:", risk, bx, y, lw=100, val_color=risk_col)
            y = self.draw_kv(surface, "Crime score:", f"{nd.get('crime_score') or 0:g}/100", bx, y, lw=100)
            y = self.draw_kv(surface, "Accessible:", "YES" if nd.get("accessible", True) else "NO",
                             bx, y, lw=100,
                             val_color=Colors.GREEN if nd.get("accessible", True) else Colors.RED)

            # Is it an ambulance/police node?
            if nid in self.sim.ambulances:
                t = fm.render("  ● Ambulance stationed here", True, Colors.AMBULANCE)
                surface.blit(t, (bx, y)); y += t.get_height() + 2
            police_nodes = [d[0] if isinstance(d, (list, tuple)) else d.get("node_id", 0)
                            for d in self.sim.police_deployments]
            if nid in police_nodes:
                t = fm.render("  ● Police deployed here", True, Colors.POLICE)
                surface.blit(t, (bx, y)); y += t.get_height() + 2
        else:
            t = fm.render("Click a sector on the map", True, Colors.TEXT_MUTED)
            surface.blit(t, (bx, y))

        # Risk distribution summary
        y = rect.y + 8 + len(self.LAYERS) * 30 + 12 + 200
        pygame.draw.line(surface, Colors.BORDER, (rect.x, y), (rect.right, y)); y += 8
        t = fb.render("CRIME SCORE DISTRIBUTION", True, Colors.TEXT_MUTED)
        surface.blit(t, (bx, y)); y += t.get_height() + 4

        m = self.sim.metrics
        total = (m.get("high_risk_zones", 0) + m.get("medium_risk_zones", 0) +
                 m.get("low_risk_zones", 0))
        for level, key, col in [
            ("HIGH", "high_risk_zones", Colors.RISK_HIGH),
            ("MEDIUM", "medium_risk_zones", Colors.RISK_MEDIUM),
            ("LOW", "low_risk_zones", Colors.RISK_LOW),
        ]:
            count = m.get(key, 0)
            pct = f"{100*count/total:.0f}%" if total > 0 else "?"
            y = self.draw_kv(surface, f"{level}:", f"{count} ({pct})", bx, y, lw=80, val_color=col)
        y+=18
        import textwrap
        reasons=['Each tile represents an urban sector.','Crime scores describe sector-wide opportunity.']
        if self._selected_node in self.graph.nodes:
            reasons.append(sector_description(self.graph.nodes[self._selected_node].get('node_type','EMPTY')))
            reasons+=self.graph.nodes[self._selected_node].get('crime_reasons',[])
        for reason in reasons:
            for line in textwrap.wrap(sector_text(reason),34):
                surface.blit(fm.render(line,True,Colors.TEXT_MUTED),(bx,y))
                y+=15

    def _draw_legend(self, surface):
        """Draw color legend on the map."""
        lx = self._map_rect.x + 8
        ly = self._map_rect.bottom - 90
        f  = Fonts.mono(9)
        fb = Fonts.bold(9)

        if self._active_layer == 0:
            t = fb.render("CRIME HEATMAP", True, Colors.TEXT_MUTED)
            surface.blit(t, (lx, ly)); ly += 14
            radius=self.sim.police.get('crime_report_radius',0)
            surface.blit(f.render(f'Radius: {radius:g} sector units',True,Colors.TEXT_SECONDARY),(lx,ly))
            ly+=14
            for risk, col in RISK_COLORS.items():
                pygame.draw.rect(surface, col, (lx, ly, 10, 10))
                t = f.render(risk, True, Colors.TEXT_SECONDARY)
                surface.blit(t, (lx + 14, ly)); ly += 13
        elif self._active_layer == 1:
            t = fb.render("SECTOR POPULATION", True, Colors.TEXT_MUTED)
            surface.blit(t, (lx, ly)); ly += 12
            for i in range(5):
                v = i / 4
                col = heat_color(v, 0, 1)
                pygame.draw.rect(surface, col, (lx, ly, 10, 10))
                t = f.render(f"{int(v*200)}", True, Colors.TEXT_SECONDARY)
                surface.blit(t, (lx + 14, ly)); ly += 12
