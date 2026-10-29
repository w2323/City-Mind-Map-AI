# visualization/graph_renderer.py — CityMind 2D: City Map Renderer
#
# Renders the city graph onto a Pygame surface with:
#   - Pan/zoom with mouse drag and scroll wheel
#   - Distinct colours for node types, risk, and edge states
#   - Route highlighting, ambulance/police/civilian markers
#   - Heatmap overlay
#   - Node and edge selection with hit testing
#   - Fit-to-view control

import pygame
import math
from app.theme import Colors, Fonts, Layout, NODE_TYPE_COLORS, NODE_TYPE_LABELS, RISK_COLORS, heat_color


class GraphRenderer:
    """
    Renders the CityGraph onto a Pygame Rect (the map viewport).

    Coordinate system:
        grid (row, col)  →  screen (sx, sy)
        sx = viewport.x + (col + 0.5) * cell_w * scale + offset_x
        sy = viewport.y + (row + 0.5) * cell_h * scale + offset_y

    The renderer never modifies AppState directly.
    It exposes hit_test_node() and hit_test_edge() for the screen layer.
    """

    def __init__(self, viewport: pygame.Rect):
        self.viewport    = viewport
        self._base_surface = None
        self._base_key = None
        self.cache_builds = 0
        self.fleet = []
        self.air_rescue = {}
        self.unserved_nodes = []
        self.gate_zones = []
        self.gate_preview = None
        self.police_service = {}
        self.show_coverage = True
        self.team_node = None
        self.hovered_node = None
        self._offset     = [0.0, 0.0]   # pan offset in screen pixels
        self._scale      = 1.0
        self._dragging   = False
        self._drag_start = None
        self._drag_offset_start = None

        # Base cell size at scale=1.0 (pixels per grid cell)
        self._base_cell  = 36.0

        # Display options
        self.show_labels      = True
        self.show_edge_costs  = False
        self.show_node_ids    = False
        self.heatmap_layer    = None   # None | "risk" | "population"

        # Highlighted sets
        self.highlighted_route: list = []   # ordered list of node ids
        self.highlighted_nodes: set  = set()
        self.selected_node: int      = None
        self.selected_edge: tuple    = None

        # Markers
        self.ambulance_nodes: list   = []
        self.civilian_nodes: list    = []
        self.police_nodes: list      = []

        # Active route paths: list of {path: [ids], color: (r,g,b)}
        self.route_paths: list       = []

    # ── Coordinate transforms ────────────────────────────────────────────────

    @property
    def cell(self) -> float:
        return self._base_cell * self._scale

    def grid_to_screen(self, row: float, col: float):
        sx = self.viewport.x + (col + 0.5) * self.cell + self._offset[0]
        sy = self.viewport.y + (row + 0.5) * self.cell + self._offset[1]
        return int(sx), int(sy)

    def screen_to_grid(self, sx: int, sy: int):
        col = (sx - self.viewport.x - self._offset[0]) / self.cell - 0.5
        row = (sy - self.viewport.y - self._offset[1]) / self.cell - 0.5
        return row, col

    def node_screen_pos(self, node: dict):
        return self.grid_to_screen(node["row"], node["col"])

    def fit_to_view(self, grid_rows: int = 15, grid_cols: int = 15):
        """Scale and center the grid to fill the viewport."""
        grid_rows, grid_cols = max(1, grid_rows), max(1, grid_cols)
        scale_x = (self.viewport.width  - 20) / (grid_cols * self._base_cell)
        scale_y = (self.viewport.height - 20) / (grid_rows * self._base_cell)
        self._scale  = max(0.1, min(scale_x, scale_y))
        # Center grid
        grid_pw = grid_cols * self.cell
        grid_ph = grid_rows * self.cell
        self._offset[0] = (self.viewport.width  - grid_pw) / 2
        self._offset[1] = (self.viewport.height - grid_ph) / 2

    # ── Hit testing ──────────────────────────────────────────────────────────

    def hit_test_node(self, sx: int, sy: int, nodes: dict) -> int:
        """Return node id at screen position, or None."""
        if not self.viewport.collidepoint(sx, sy):
            return None
        threshold = max(6, self.cell * 0.45)
        best_id = None
        best_d  = float("inf")
        for nid, node in nodes.items():
            nx, ny = self.node_screen_pos(node)
            d = math.hypot(sx - nx, sy - ny)
            if d < threshold and d < best_d:
                best_d  = d
                best_id = nid
        return best_id

    def hit_test_edge(self, sx: int, sy: int, nodes: dict, edges: list):
        """Return edge dict closest to screen position (within threshold), or None."""
        if not self.viewport.collidepoint(sx,sy):
            return None
        threshold = 6.0
        best_edge = None
        best_d    = float("inf")
        for e in edges:
            na = e.get("node_a", e.get("nodeA"))
            nb = e.get("node_b", e.get("nodeB"))
            if na not in nodes or nb not in nodes:
                continue
            ax, ay = self.node_screen_pos(nodes[na])
            bx, by = self.node_screen_pos(nodes[nb])
            d = _dist_point_segment(sx, sy, ax, ay, bx, by)
            if d < threshold and d < best_d:
                best_d    = d
                best_edge = e
        return best_edge

    # ── Pan / zoom input handling ────────────────────────────────────────────

    def handle_event(self, event) -> bool:
        """Return True if the event was consumed."""
        if event.type == pygame.MOUSEWHEEL:
            if self.viewport.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                mx, my = getattr(event, "pos", pygame.mouse.get_pos())
                old_scale = self._scale
                self._scale = max(0.25, min(4.0, self._scale * (1.12 ** event.y)))
                # Zoom towards mouse position
                factor = self._scale / old_scale
                self._offset[0] = mx - self.viewport.x - factor * (mx - self.viewport.x - self._offset[0])
                self._offset[1] = my - self.viewport.y - factor * (my - self.viewport.y - self._offset[1])
                return True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.viewport.collidepoint(event.pos):
                self._dragging = True
                self._drag_start = event.pos
                self._drag_offset_start = list(self._offset)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging:
                dx = event.pos[0] - self._drag_start[0]
                dy = event.pos[1] - self._drag_start[1]
                self._offset[0] = self._drag_offset_start[0] + dx
                self._offset[1] = self._drag_offset_start[1] + dy
                return True

        return False

    # ── Main draw ────────────────────────────────────────────────────────────

    def draw(self, surface, nodes: dict, edges: list, risk_predictions: dict = None,
             ambulance_nodes: list = None, civilian_nodes: list = None,
             police_nodes: list = None, route_paths: list = None):
        """Draw the complete city map onto `surface`."""
        if not nodes:
            return

        clip = surface.get_clip()
        surface.set_clip(self.viewport)

        # Cache the expensive static map; routes and selection remain live overlays.
        key = (
            tuple(self.viewport), self._scale, tuple(self._offset),
            self.show_labels, self.show_edge_costs, self.show_node_ids, self.heatmap_layer,
            self.selected_edge,
            tuple((nid, n.get("row"), n.get("col"), n.get("node_type"), n.get("population"),
                   n.get("risk_level"), n.get("accessible")) for nid, n in nodes.items()),
            tuple((e.get("node_a", e.get("nodeA")), e.get("node_b", e.get("nodeB")),
                     e.get("cost"), e.get("blocked"), e.get('temporarily_blocked',False)) for e in edges),
            tuple((risk_predictions or {}).items()),
        )
        if self._base_key != key:
            size = self.viewport.size
            if size[0] <= 0 or size[1] <= 0:
                surface.set_clip(clip)
                return
            self._base_surface = pygame.Surface(size)
            original_viewport = self.viewport
            try:
                self.viewport = pygame.Rect(0, 0, *size)
                self._base_surface.fill(Colors.BG_DEEP)
                self._draw_grid_bg(self._base_surface, nodes)
                self._draw_edges(self._base_surface, nodes, edges, [])
                self._draw_nodes(self._base_surface, nodes, risk_predictions or {})
            finally:
                self.viewport = original_viewport
            self._base_key = key
            self.cache_builds += 1
        surface.blit(self._base_surface, self.viewport.topleft)
        if self.gate_zones or self.gate_preview:
            self._draw_gate_zones(surface,nodes)
        if self.heatmap_layer=='risk' and self.police_service.get('crime_areas'):
            self._draw_crime_areas(surface,nodes)
        for rp in route_paths or []:
            self._draw_route_path(surface, nodes, rp["path"], rp.get("color", Colors.EDGE_ROUTE))
        for nid in self.highlighted_nodes:
            if nid in nodes:
                pygame.draw.circle(surface, Colors.ACCENT_AMBER, self.node_screen_pos(nodes[nid]),
                                   max(8, int(self.cell * .48)), 2)
        if self.team_node in nodes:
            sx, sy = self.node_screen_pos(nodes[self.team_node])
            pygame.draw.rect(surface, Colors.TEXT_BRIGHT, (sx-5, sy-5, 10, 10), border_radius=2)
            pygame.draw.line(surface, Colors.RED, (sx-3, sy), (sx+3, sy), 2)
            pygame.draw.line(surface, Colors.RED, (sx, sy-3), (sx, sy+3), 2)

        # Draw entity markers
        self._draw_markers(surface, nodes,
                           ambulance_nodes or [],
                           civilian_nodes  or [],
                           police_nodes    or [])

        # Draw selected node highlight
        if self.selected_node is not None and self.selected_node in nodes:
            nx, ny = self.node_screen_pos(nodes[self.selected_node])
            r = max(10, int(self.cell * 0.55))
            pygame.draw.circle(surface, Colors.ACCENT_CYAN, (nx, ny), r + 3, 2)

        if self.fleet:
            self._draw_fleet(surface, nodes)
        if self.air_rescue:
            self._draw_air_rescue(surface, nodes)
        if self.police_service:
            self._draw_police_service(surface,nodes)
        surface.set_clip(clip)

    # ── Private draw helpers ─────────────────────────────────────────────────

    def _draw_grid_bg(self, surface, nodes: dict):
        """Draw faint grid dots for spatial orientation."""
        if self._scale < 0.5:
            return
        for node in nodes.values():
            sx, sy = self.node_screen_pos(node)
            if (self.viewport.x <= sx <= self.viewport.right and
                    self.viewport.y <= sy <= self.viewport.bottom):
                pygame.draw.circle(surface, Colors.BG_HOVER, (sx, sy), 1)

    def _draw_edges(self, surface, nodes: dict, edges: list, route_paths: list):
        route_set = set()
        for rp in route_paths:
            path = rp["path"]
            for i in range(len(path) - 1):
                route_set.add((min(path[i], path[i + 1]), max(path[i], path[i + 1])))

        for e in edges:
            na = e.get("node_a", e.get("nodeA"))
            nb = e.get("node_b", e.get("nodeB"))
            if na not in nodes or nb not in nodes:
                continue
            ax, ay = self.node_screen_pos(nodes[na])
            bx, by = self.node_screen_pos(nodes[nb])

            # Clip to viewport
            if not _line_in_rect(ax, ay, bx, by, self.viewport):
                continue

            blocked = e.get("blocked", False)
            key = (min(na, nb), max(na, nb))
            is_route = key in route_set
            is_selected = self.selected_edge and (
                (min(self.selected_edge[0], self.selected_edge[1]) == key[0] and
                 max(self.selected_edge[0], self.selected_edge[1]) == key[1])
            )

            if blocked:
                color = Colors.EDGE_BLOCKED
                width = max(1, int(self._scale * 1.5))
            elif is_route:
                color = Colors.EDGE_ROUTE
                width = max(2, int(self._scale * 2.5))
            elif e.get('temporarily_blocked',False):
                color = Colors.ACCENT_AMBER
                width = max(3, int(self._scale * 2))
            else:
                color = Colors.EDGE_NORMAL
                width = max(1, int(self._scale * 1.2))

            if is_selected:
                pygame.draw.line(surface, Colors.ACCENT_CYAN, (ax,ay), (bx,by), max(7,width+5))
            pygame.draw.line(surface, color, (ax, ay), (bx, by), width)

            # Edge cost label
            if self.show_edge_costs and self._scale > 1.2:
                mx = (ax + bx) // 2
                my = (ay + by) // 2
                cost = e.get("cost", 1.0)
                f = Fonts.mono(8)
                t = f.render(f"{cost:.1f}", True, Colors.TEXT_MUTED)
                surface.blit(t, (mx - t.get_width() // 2, my - t.get_height() // 2))

    def _draw_crime_areas(self,surface,nodes):
        layer=pygame.Surface(self.viewport.size,pygame.SRCALPHA)
        for area in self.police_service.get('crime_areas',[]):
            node=nodes.get(area['node_id'])
            if node is None:
                continue
            x,y=self.node_screen_pos(node)
            center=(x-self.viewport.x,y-self.viewport.y)
            radius=max(1,round(area['radius']*self.cell))
            strength=max(0,min(1,area['peak_score']/100))
            color=Colors.RISK_HIGH if area['peak_score']>=60 else Colors.RISK_MEDIUM
            pygame.draw.circle(layer,(*color,round(22*strength)),center,radius)
            pygame.draw.circle(layer,(*color,round(200*strength)),center,radius,2)
            pygame.draw.circle(layer,(*color,220),center,4)
            label=Fonts.bold(10).render(f"Sector {area['label']} / {area['radius']:g} units",True,color)
            layer.blit(label,(center[0]-label.get_width()//2,center[1]-radius-15))
        surface.blit(layer,self.viewport.topleft)

    def _draw_gate_zones(self,surface,nodes):
        layer=pygame.Surface(self.viewport.size,pygame.SRCALPHA)
        for zone in self.gate_zones + ([self.gate_preview] if self.gate_preview else []):
            node=nodes.get(zone.get('node_id'))
            if node is None:
                continue
            x,y=self.node_screen_pos(node)
            center=(x-self.viewport.x,y-self.viewport.y)
            radius=max(1,round(zone.get('radius',0)*self.cell))
            preview=zone is self.gate_preview
            pygame.draw.circle(layer,(*Colors.PURPLE,12 if preview else 22),center,radius)
            pygame.draw.circle(layer,(*Colors.PURPLE,190),center,radius,2)
            pygame.draw.circle(layer,(*Colors.PURPLE,220),center,5)
        surface.blit(layer,self.viewport.topleft)

    def _draw_route_path(self, surface, nodes: dict, path: list, color):
        """Draw a thick highlighted route path."""
        if len(path) < 2:
            return
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if a not in nodes or b not in nodes:
                continue
            ax, ay = self.node_screen_pos(nodes[a])
            bx, by = self.node_screen_pos(nodes[b])
            w = max(3, int(self._scale * 3))
            pygame.draw.line(surface, color, (ax, ay), (bx, by), w)

    def _draw_nodes(self, surface, nodes, risk_predictions):
        radius = max(5,int(self.cell*.33))
        for nid,node in nodes.items():
            sx,sy = self.node_screen_pos(node)
            if not self.viewport.inflate(30,30).collidepoint(sx,sy):
                continue
            kind = node.get('node_type','EMPTY')
            color = NODE_TYPE_COLORS.get(kind,Colors.NODE_EMPTY)
            if self.heatmap_layer == 'risk':
                risk = risk_predictions.get(nid,risk_predictions.get(str(nid),node.get('risk_level','NONE')))
                color = RISK_COLORS.get(risk,Colors.RISK_NONE)
            elif self.heatmap_layer == 'population':
                color = heat_color(node.get('population',0),0,200)
            tile = pygame.Rect(sx-radius,sy-radius,radius*2,radius*2)
            pygame.draw.rect(surface,(255,255,255),tile,border_radius=5)
            pygame.draw.rect(surface,color,tile,1,border_radius=5)
            pygame.draw.rect(surface,color,(tile.x+3,tile.y+3,4,max(2,tile.height-6)),border_radius=2)
            if kind == 'HOSPITAL':
                pygame.draw.rect(surface,Colors.ACCENT_CYAN,tile.inflate(4,4),2,border_radius=5)
                pygame.draw.line(surface,Colors.RED,(tile.right-3,tile.y-6),(tile.right-3,tile.y+2),2)
                pygame.draw.line(surface,Colors.RED,(tile.right-7,tile.y-2),(tile.right+1,tile.y-2),2)
            if kind == 'BANK':
                bank_color=NODE_TYPE_COLORS['BANK']
                pygame.draw.rect(surface,bank_color,tile.inflate(4,4),2,border_radius=5)
                badge=Fonts.bold(9).render('FIN',True,bank_color)
                surface.blit(badge,(sx-badge.get_width()//2,tile.y-13))
            if self.show_labels and radius>8:
                label = node.get('label') or f"{chr(65+node.get('col',0))}{node.get('row',0)+1}"
                text = Fonts.sans(max(10,min(13,int(radius*.92)))).render(label,True,Colors.TEXT_SECONDARY)
                surface.blit(text,(sx-text.get_width()//2+2,sy-text.get_height()//2))
            if not node.get('accessible',True):
                pygame.draw.rect(surface,Colors.RED,tile,2,border_radius=5)

    def _draw_air_rescue(self,surface,nodes):
        air=self.air_rescue
        for site in air.get('landing_sites',[{'node_id':n,'available':True} for n in air.get('landing_nodes',[])]):
            nid=site['node_id']
            if nid in nodes:
                x,y=self.node_screen_pos(nodes[nid])
                pygame.draw.circle(surface,Colors.PURPLE if site.get('available') else Colors.RED,(x,y),max(8,round(self.cell*.36)),2)
                surface.blit(Fonts.bold(9).render('HP',True,Colors.PURPLE if site.get('available') else Colors.RED),(x-6,y-5))
        position=air.get('render_position') or air.get('position')
        if not position:
            return
        x,y=self.grid_to_screen(*position)
        target=nodes.get(air.get('target'))
        if target:
            end=self.node_screen_pos(target)
            pygame.draw.line(surface,Colors.PURPLE,(x,y),end,2)
        pygame.draw.circle(surface,(255,255,255),(x,y),17)
        pygame.draw.ellipse(surface,Colors.PURPLE,(x-6,y-9,12,20),2)
        pygame.draw.line(surface,Colors.PURPLE,(x-17,y-9),(x+17,y-9),3)
        pygame.draw.line(surface,Colors.PURPLE,(x,y+9),(x,y+19),3)
        pygame.draw.line(surface,Colors.PURPLE,(x-7,y+19),(x+7,y+19),2)
        label=Fonts.bold(10).render('AIR',True,Colors.PURPLE)
        surface.blit(label,(x+20,y-7))

    def _draw_fleet(self,surface,nodes):
        colors = [(38,100,220),(23,154,119),(185,123,42),(126,86,192)]
        for index,unit in enumerate(self.fleet):
            if unit['position'] not in nodes:
                continue
            x,y = self.grid_to_screen(*unit['render_position']) if unit.get('render_position') else self.node_screen_pos(nodes[unit['position']])
            color = Colors.RED if unit['status']=='OUT_OF_SERVICE' else colors[index%len(colors)]
            body=pygame.Rect(x-13,y-10,26,19)
            pygame.draw.rect(surface,(255,255,255),body,border_radius=5)
            pygame.draw.rect(surface,color,body,2,border_radius=5)
            pygame.draw.rect(surface,color,(x-12,y-8,7,15),border_radius=2)
            pygame.draw.line(surface,Colors.RED,(x+1,y-5),(x+1,y+4),2)
            pygame.draw.line(surface,Colors.RED,(x-3,y),(x+5,y),2)
            for dx in [-8,8]:
                pygame.draw.circle(surface,Colors.TEXT_PRIMARY,(x+dx,y+10),3)
            label=Fonts.bold(10).render(unit['id']+(' OFF' if unit['status']=='OUT_OF_SERVICE' else ''),True,color)
            pygame.draw.rect(surface,(255,255,255),(x-label.get_width()//2-4,y-31,label.get_width()+8,16),border_radius=4)
            surface.blit(label,(x-label.get_width()//2,y-29))

    def _draw_markers(self, surface, nodes, ambulance_nodes, civilian_nodes, police_nodes):
        marker_r = max(4, int(self.cell * 0.22))

        for nid in ambulance_nodes:
            if nid in nodes:
                sx, sy = self.node_screen_pos(nodes[nid])
                pygame.draw.circle(surface, Colors.AMBULANCE, (sx, sy - marker_r - 5), marker_r)
                f = Fonts.bold(max(7, int(marker_r * 1.2)))
                t = f.render("A", True, Colors.BG_DEEP)
                surface.blit(t, (sx - t.get_width() // 2, sy - marker_r - 5 - t.get_height() // 2))

        for nid in civilian_nodes:
            if nid in nodes:
                sx, sy = self.node_screen_pos(nodes[nid])
                pygame.draw.circle(surface, Colors.CIVILIAN, (sx + marker_r + 3, sy), marker_r)
                f = Fonts.bold(max(6, int(marker_r)))
                t = f.render("!", True, (255,255,255))
                surface.blit(t, (sx + marker_r + 3 - t.get_width() // 2,
                                  sy - t.get_height() // 2))

        for nid in police_nodes:
            if nid in nodes:
                sx, sy = self.node_screen_pos(nodes[nid])
                pygame.draw.circle(surface, Colors.POLICE, (sx - marker_r - 3, sy), marker_r)
                f = Fonts.bold(max(6, int(marker_r)))
                t = f.render("P", True, Colors.TEXT_BRIGHT)
                surface.blit(t, (sx - marker_r - 3 - t.get_width() // 2,
                                  sy - t.get_height() // 2))

    def _draw_police_service(self,surface,nodes):
        for station in self.police_service.get('stations',[]):
            if station['node_id'] in nodes:
                x,y=self.node_screen_pos(nodes[station['node_id']])
                box=pygame.Rect(x-18,y-18,36,36)
                pygame.draw.rect(surface,Colors.POLICE,box,2,border_radius=5)
                label=Fonts.bold(9).render(station['id'],True,Colors.POLICE)
                surface.blit(label,(x-label.get_width()//2,y+20))
        for unit in self.police_service.get('units',[]):
            node=nodes.get(unit['position'])
            if node is None:
                continue
            x,y=self.grid_to_screen(*unit['render_position']) if unit.get('render_position') else self.node_screen_pos(node)
            x+=(int(unit['id'][-2:])%3-1)*5
            pygame.draw.rect(surface,(250,252,255),(x-11,y-6,22,13),border_radius=4)
            pygame.draw.rect(surface,Colors.POLICE,(x-11,y-6,22,13),2,border_radius=4)
            pygame.draw.line(surface,Colors.RED,(x-6,y-8),(x,y-8),3)
            pygame.draw.line(surface,Colors.ACCENT_CYAN,(x,y-8),(x+6,y-8),3)
            if unit['status'] in ('RESPONDING','ON_SCENE','BLOCKED'):
                label=Fonts.bold(9).render(unit['id'],True,Colors.POLICE)
                surface.blit(label,(x-label.get_width()//2,y-24))
        for report in self.police_service.get('reports',[]):
            if report['status']!='RESOLVED' and report['node_id'] in nodes:
                x,y=self.node_screen_pos(nodes[report['node_id']])
                pygame.draw.circle(surface,Colors.RED,(x+12,y-12),8)
                label=Fonts.bold(10).render(str(report['severity']),True,(255,255,255))
                surface.blit(label,(x+12-label.get_width()//2,y-18))


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _dist_point_segment(px, py, ax, ay, bx, by) -> float:
    """Perpendicular distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _line_in_rect(ax, ay, bx, by, rect: pygame.Rect) -> bool:
    """Quick check: is any part of line (ax,ay)-(bx,by) inside rect?"""
    # Expand rect slightly for edge cases
    ex = rect.inflate(20, 20)
    return (ex.collidepoint(ax, ay) or ex.collidepoint(bx, by) or
            _segment_crosses_rect(ax, ay, bx, by, ex))


def _segment_crosses_rect(ax, ay, bx, by, rect: pygame.Rect) -> bool:
    """Liang-Barsky clipping test."""
    dx, dy = bx - ax, by - ay
    p = [-dx, dx, -dy, dy]
    q = [ax - rect.left, rect.right - ax, ay - rect.top, rect.bottom - ay]
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return False
        elif pi < 0:
            u1 = max(u1, qi / pi)
        else:
            u2 = min(u2, qi / pi)
    return u1 <= u2
