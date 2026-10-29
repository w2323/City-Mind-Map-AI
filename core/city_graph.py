# city_graph.py — CityMind shared city graph
# This is the foundation of the entire project. Every module imports from here.
# Contains: Node, Edge, CityGraph — kept together intentionally (no unnecessary fragmentation).
#
# DESIGN NOTE (F31): The graph is structurally undirected, but effective traversal cost
# is directional — cost A→B uses node B's risk multiplier, while cost B→A uses node A's.
# API serialization returns base `cost` only; callers must compute effective cost with
# the correct destination node. The reference_dijkstra.py module handles this correctly.
#
# DESIGN NOTE (F30): Diagonal edges are added between diagonal grid cells without checking
# orthogonal neighbor passability. Every node is treated as a traversable road junction.
# Diagonal edges model road shortcuts. This is a deliberate modeling choice.

import heapq
import math
import random
from collections import deque
from config.simulation_config import SimConfig


# ──────────────────────────────────────────────────────────
# Node — represents a single cell/location in the city grid
# ──────────────────────────────────────────────────────────
class Node:
    """A single grid cell in the city. Stores zone type, population, and risk data."""

    def __init__(self, row: int, col: int):
        self.id: int = row * SimConfig.GRID_COLS + col
        self.row: int = row
        self.col: int = col
        self.node_type: str = SimConfig.EMPTY        # Assigned by CSP solver
        self.population: int = 0                     # Set after layout (synthetic range)
        self.risk_index: float = 0.0                 # Numeric risk score from ML
        self.risk_level: str = "NONE"                # "HIGH", "MEDIUM", "LOW", "NONE"
        self.accessible: bool = False                # True if node has at least one active neighbor
                                                     # Updated by CityGraph after block/unblock ops (F27/F48)

    def __repr__(self) -> str:
        return f"Node({self.row},{self.col}, {self.node_type})"

    @property
    def label(self) -> str:
        """Alphanumeric label (e.g. A1, B2) where col=A..O, row=1..15."""
        return f"{chr(65 + self.col)}{self.row + 1}"

    def to_dict(self) -> dict:
        """Serialize node state for API / frontend consumption."""
        return {
            "id": self.id,
            "row": self.row,
            "col": self.col,
            "label": self.label,
            "node_type": self.node_type,
            "population": self.population,
            "risk_features": getattr(self, "risk_features", {}),
            "crime_score": getattr(self, "crime_score", None),
            "crime_reasons": getattr(self, "crime_reasons", []),
            "cluster_id": getattr(self, "cluster_id", None),
            "risk_index": round(self.risk_index, 3),
            "risk_level": self.risk_level,
            "accessible": self.accessible,
        }


# ──────────────────────────────────────────────────────────
# Edge — represents a road between two nodes
# ──────────────────────────────────────────────────────────
class Edge:
    """A road connecting two nodes. Tracks base cost and blocked status."""

    def __init__(self, node_a_id: int, node_b_id: int, base_cost: float = SimConfig.COST_STANDARD):
        self.node_a: int = node_a_id
        self.node_b: int = node_b_id
        self.cost: float = base_cost          # Base travel cost
        self.blocked: bool = False            # True = road is impassable
        self.temporarily_blocked: bool = False  # Ambulances only; normal traffic prohibited
        self.gate_ids: set = set()

    def effective_cost(self, graph: "CityGraph", to_node_id: int = None, travel_mode: str = 'ambulance') -> float:
        """
        Compute actual traversal cost factoring in risk multipliers.
        Returns infinity if the road is blocked.
        If to_node_id is specified, uses that destination node's risk level.

        NOTE (F31): Cost is directional. cost A→B != cost B→A when risk levels differ.
        """
        if not self.allows(travel_mode):
            return float("inf")
        dest_id = to_node_id if to_node_id is not None else self.node_b
        risk = graph.nodes[dest_id].risk_level
        return self.cost * SimConfig.RISK_MULTIPLIER.get(risk, 1.0)

    def allows(self, travel_mode='ambulance'):
        if travel_mode not in ('ambulance', 'normal', 'commercial'):
            raise ValueError('Unknown travel mode')
        return not self.blocked and (travel_mode == 'ambulance' or not self.temporarily_blocked)

    def other(self, node_id: int) -> int:
        """Return the other endpoint of this edge."""
        return self.node_b if node_id == self.node_a else self.node_a

    def to_dict(self) -> dict:
        """Serialize edge state for API / frontend consumption.
        NOTE: 'cost' is the base cost. Effective traversal cost depends on
        the destination node's risk level (directional). See F31."""
        return {
            "node_a": self.node_a,
            "node_b": self.node_b,
            "cost": self.cost,
            "blocked": self.blocked,
            "temporarily_blocked": self.temporarily_blocked,
            "gate_ids": sorted(self.gate_ids),
        }


# ──────────────────────────────────────────────────────────
# CityGraph — the entire city's graph structure
# This is the SINGLE SHARED GRAPH for the whole system.
# No module may maintain its own copy.
# ──────────────────────────────────────────────────────────
class CityGraph:
    """
    Centralized city graph. All modules share ONE instance.

    - Nodes are created on init (15x15 = 225 nodes, all EMPTY)
    - Edges are added by Challenge 2 (road network)
    - Observers are notified when roads are blocked or unblocked (F26)
    - Dijkstra and BFS use effective_cost which respects risk multipliers
    - Node accessible flags are kept in sync with actual connectivity (F27/F48)
    """

    def __init__(self):
        self.nodes: dict = {}       # id -> Node
        self.edges: dict = {}       # (min_id, max_id) -> Edge (canonical key)
        self.adj: dict = {}         # id -> list of neighbor node IDs
        self._block_observers: list = []   # Callbacks notified when a road is blocked: cb(id_a, id_b)
        self._unblock_observers: list = [] # Callbacks notified when a road is unblocked: cb(id_a, id_b) [F26]
        self._risk_observers: list = []    # Callbacks notified when risk changes: cb(node_id) [F2]
        self._access_observers: list = []  # Normal/commercial access changes; ambulance topology unchanged
        self._init_grid()

    def _init_grid(self):
        """Create the grid of GRID_ROWS x GRID_COLS nodes, all EMPTY."""
        for row in range(SimConfig.GRID_ROWS):
            for col in range(SimConfig.GRID_COLS):
                node = Node(row, col)
                self.nodes[node.id] = node
                self.adj[node.id] = []

    # ── Node access ─────────────────────────────────────────

    def get_node(self, row: int, col: int) -> Node:
        """Get a node by its grid coordinates."""
        return self.nodes[row * SimConfig.GRID_COLS + col]

    def get_nodes_of_type(self, node_type: str) -> list:
        """Return all nodes matching the given type."""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    # ── Edge management ─────────────────────────────────────

    def add_edge(self, id_a: int, id_b: int, cost: float = SimConfig.COST_STANDARD):
        """
        Add an edge between two nodes. Ignores duplicates.

        F28: Validates that both node IDs exist in the graph and rejects self-loops.
        Raises ValueError for invalid inputs rather than crashing with KeyError.
        """
        # F28: Validate endpoints
        if id_a not in self.nodes:
            raise ValueError(f"add_edge: node {id_a} does not exist in graph.")
        if id_b not in self.nodes:
            raise ValueError(f"add_edge: node {id_b} does not exist in graph.")
        if id_a == id_b:
            raise ValueError(f"add_edge: self-loop on node {id_a} is not allowed.")
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError("Road cost must be finite and positive.")

        key = (min(id_a, id_b), max(id_a, id_b))
        if key in self.edges:
            return
        edge = Edge(id_a, id_b, cost)
        self.edges[key] = edge
        self.adj[id_a].append(id_b)
        self.adj[id_b].append(id_a)

        # F27/F48: Update accessible flags for both nodes after adding edge
        self._update_accessible(id_a)
        self._update_accessible(id_b)

    def remove_edge(self, id_a: int, id_b: int):
        """
        Mark an edge as blocked and remove from adjacency lists.
        The Edge object is kept (with blocked=True) for logging and history.
        Notifies all registered block observers.
        Returns True if the edge was actually blocked, False if no-op.
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        if key not in self.edges:
            return False
        edge = self.edges[key]
        if edge.blocked:
            return False  # Already blocked — prevent double processing
        edge.blocked = True
        # Remove from adjacency lists safely
        if id_b in self.adj[id_a]:
            self.adj[id_a].remove(id_b)
        if id_a in self.adj[id_b]:
            self.adj[id_b].remove(id_a)

        # F27/F48: Update accessible flags for both endpoints
        self._update_accessible(id_a)
        self._update_accessible(id_b)

        # Notify observers (A* router listens here)
        self._notify_blocked(id_a, id_b)
        return True

    def block_road(self, id_a: int, id_b: int) -> bool:
        """
        Alias for remove_edge. Called by simulation during flood events.
        Returns True if the road was actually blocked (was active), False if no-op.
        """
        return self.remove_edge(id_a, id_b)

    def unblock_road(self, id_a: int, id_b: int, preserve_restrictions: bool = False) -> bool:
        """
        Unblock an edge and restore connectivity in adjacency lists.
        F26: Notifies unblock observers so the router can retry deferred civilians.
        F27/F48: Updates accessible flags for affected nodes.
        Returns True if the edge was actually unblocked, False if no-op.
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        if key not in self.edges:
            return False
        edge = self.edges[key]
        if not edge.blocked:
            if edge.temporarily_blocked and not preserve_restrictions:
                edge.temporarily_blocked = False
                edge.gate_ids.clear()
                self.notify_access_changed()
                return True
            return False  # Already open for everyone
        edge.blocked = False
        if not preserve_restrictions:
            edge.temporarily_blocked = False
            edge.gate_ids.clear()
        if id_b not in self.adj[id_a]:
            self.adj[id_a].append(id_b)
        if id_a not in self.adj[id_b]:
            self.adj[id_b].append(id_a)

        # F27/F48: Update accessible flags for both endpoints
        self._update_accessible(id_a)
        self._update_accessible(id_b)

        # F26: Notify unblock observers so router can retry deferred targets
        self._notify_unblocked(id_a, id_b)
        return True

    # ── Accessible flag management ────────────────────────────

    def _update_accessible(self, node_id: int):
        """
        F27/F48: Update a node's accessible flag based on current active neighbors.
        A node is accessible if it has at least one non-blocked edge.
        """
        if node_id in self.nodes:
            self.nodes[node_id].accessible = bool(self.get_neighbors(node_id))

    def refresh_all_accessible_flags(self):
        """Recompute accessible flags for all nodes. Use after bulk mutations."""
        for nid in self.nodes:
            self._update_accessible(nid)

    # ── Neighbor queries ────────────────────────────────────

    def get_neighbors(self, node_id: int, travel_mode: str = 'ambulance') -> list:
        """
        Return neighbors reachable via non-blocked edges.
        Filters adjacency list against actual edge blocked status.
        """
        result = []
        for nb_id in self.adj[node_id]:
            key = (min(node_id, nb_id), max(node_id, nb_id))
            edge = self.edges.get(key)
            if edge and edge.allows(travel_mode):
                result.append(nb_id)
        return result

    def get_grid_neighbors(self, node_id: int) -> list:
        """
        Return 4-directional grid neighbors (up/down/left/right).
        Does NOT require an edge to exist — used by CSP for constraint checking.
        """
        node = self.nodes[node_id]
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = node.row + dr, node.col + dc
            if 0 <= nr < SimConfig.GRID_ROWS and 0 <= nc < SimConfig.GRID_COLS:
                neighbors.append(nr * SimConfig.GRID_COLS + nc)
        return neighbors

    # ── Cost queries ────────────────────────────────────────

    def get_edge_cost(self, id_a: int, id_b: int, travel_mode: str = 'ambulance') -> float:
        """
        Return the effective cost of traversing the edge from id_a to id_b.
        Factors in risk multipliers for destination node id_b. Returns infinity if blocked or missing.

        NOTE (F31): This is directional. get_edge_cost(a,b) != get_edge_cost(b,a) when risks differ.
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        edge = self.edges.get(key)
        if edge is None:
            return float("inf")
        return edge.effective_cost(self, to_node_id=id_b, travel_mode=travel_mode)

    # ── Risk management ─────────────────────────────────────

    def update_risk(self, node_id: int, risk_level: str, risk_index: float = None):
        """
        Update a node's risk level. Called by the ML module.
        All subsequent get_edge_cost calls automatically use the new multiplier.
        F2: Notifies risk observers so the router can replan if needed.
        """
        node = self.nodes[node_id]
        node.risk_level = risk_level
        if risk_index is not None:
            node.risk_index = risk_index
        # F2: Notify risk-change observers
        self._notify_risk_changed(node_id)

    # ── Observer pattern ────────────────────────────────────

    def register_observer(self, callback):
        """
        Register a callback to be notified when a road is blocked: callback(id_a, id_b).
        Kept for backwards compatibility — same as register_block_observer.
        """
        self._block_observers.append(callback)

    def register_block_observer(self, callback):
        """Register a callback for road block events: callback(id_a, id_b)."""
        self._block_observers.append(callback)

    def register_unblock_observer(self, callback):
        """F26: Register a callback for road unblock events: callback(id_a, id_b)."""
        self._unblock_observers.append(callback)

    def register_risk_observer(self, callback):
        """F2: Register a callback for risk change events: callback(node_id)."""
        self._risk_observers.append(callback)

    def register_access_observer(self, callback):
        self._access_observers.append(callback)

    def notify_access_changed(self):
        for callback in self._access_observers:
            callback()

    def _notify_blocked(self, id_a: int, id_b: int):
        """Notify all block observers of a road blocking event."""
        for cb in self._block_observers:
            cb(id_a, id_b)

    def _notify_unblocked(self, id_a: int, id_b: int):
        """F26: Notify all unblock observers of a road unblocking event."""
        for cb in self._unblock_observers:
            cb(id_a, id_b)

    def _notify_risk_changed(self, node_id: int):
        """F2: Notify all risk observers of a risk level change."""
        for cb in self._risk_observers:
            cb(node_id)

    # ── Graph algorithms ────────────────────────────────────

    def bfs_distance(self, start_id: int, end_id: int) -> int:
        """
        BFS hop count (ignoring edge costs). Used by CSP for hop constraints.
        Returns -1 if no path exists.
        """
        if start_id == end_id:
            return 0
        visited = {start_id}
        queue = deque([(start_id, 0)])
        while queue:
            cur, dist = queue.popleft()
            for nb in self.get_neighbors(cur):
                if nb == end_id:
                    return dist + 1
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, dist + 1))
        return -1

    def dijkstra(self, start_id: int, travel_mode: str = 'ambulance') -> dict:
        """
        Dijkstra's shortest path from scratch using heapq.
        Returns {node_id: shortest_distance_from_start}.
        Respects risk multipliers and blocked roads via get_edge_cost.
        """
        dist = {nid: float("inf") for nid in self.nodes}
        dist[start_id] = 0.0
        heap = [(0.0, start_id)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v in self.get_neighbors(u, travel_mode):
                nd = d + self.get_edge_cost(u, v, travel_mode)
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    # ── Post-layout population assignment ───────────────────

    def populate_after_layout(self):
        """
        After CSP assigns zone types, set population values for each node.
        Uses POPULATION_MAP from config. Values are synthetic ranges (F48).
        """
        for node in self.nodes.values():
            pop_cfg = SimConfig.POPULATION_MAP.get(node.node_type, 0)
            if isinstance(pop_cfg, tuple):
                node.population = random.randint(pop_cfg[0], pop_cfg[1])
            else:
                node.population = pop_cfg

    # ── Graph statistics ────────────────────────────────────

    def count_active_edges(self) -> int:
        """Count edges that are not blocked."""
        return sum(1 for e in self.edges.values() if not e.blocked)

    def count_blocked_edges(self) -> int:
        """Count edges that are blocked."""
        return sum(1 for e in self.edges.values() if e.blocked)

    def find_disconnected_nodes(self) -> list:
        """Find nodes with zero active neighbors (isolated nodes)."""
        return [nid for nid in self.nodes if not self.get_neighbors(nid)]

    # ── Serialization ───────────────────────────────────────

    def to_dict(self) -> dict:
        """
        Serialize the entire graph state for API / frontend.
        Ready for JSON serialization via FastAPI or WebSocket.
        """
        return {
            "grid_rows": SimConfig.GRID_ROWS,
            "bank_directions": getattr(self,'bank_directions',{}),
            "grid_cols": SimConfig.GRID_COLS,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "active_edges": self.count_active_edges(),
            "blocked_edges": self.count_blocked_edges(),
            "temporarily_blocked_edges": sum(e.temporarily_blocked for e in self.edges.values()),
            "ambulance_only_edges": sum(e.temporarily_blocked and not e.blocked for e in self.edges.values()),
            "normal_active_edges": sum(e.allows('normal') for e in self.edges.values()),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CityGraph":
        """
        Reconstruct a CityGraph from serialized data.
        Useful for loading saved states or receiving from API.
        """
        graph = cls()
        graph.bank_directions={int(n):direction for n,direction in data.get('bank_directions',{}).items()}
        # Restore node attributes
        for node_data in data.get("nodes", []):
            nid = node_data["id"]
            if nid in graph.nodes:
                node = graph.nodes[nid]
                node.node_type = node_data.get("node_type", SimConfig.EMPTY)
                node.population = node_data.get("population", 0)
                node.risk_index = node_data.get("risk_index", 0.0)
                node.risk_level = node_data.get("risk_level", "NONE")
                node.risk_features = node_data.get("risk_features", {})
                node.cluster_id = node_data.get("cluster_id")
                node.crime_score=node_data.get('crime_score')
                node.crime_reasons=node_data.get('crime_reasons',[])
        # Restore edges
        for edge_data in data.get("edges", []):
            a, b = edge_data["node_a"], edge_data["node_b"]
            graph.add_edge(a, b, edge_data.get("cost", SimConfig.COST_STANDARD))
            if edge_data.get("blocked", False):
                graph.block_road(a, b)
            edge = graph.edges[(min(a,b), max(a,b))]
            edge.temporarily_blocked = edge_data.get('temporarily_blocked', False)
            edge.gate_ids = set(edge_data.get('gate_ids', []))
        return graph
