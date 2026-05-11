# city_graph.py — CityMind shared city graph
# This is the foundation of the entire project. Every module imports from here.
# Contains: Node, Edge, CityGraph — kept together intentionally (no unnecessary fragmentation).

import heapq
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
        self.population: int = 0                     # Set after layout
        self.risk_index: float = 0.0                 # Numeric risk score from ML
        self.risk_level: str = "NONE"                # "HIGH", "MEDIUM", "LOW", "NONE"
        self.accessible: bool = True                 # False if node becomes isolated

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

    def effective_cost(self, graph: "CityGraph") -> float:
        """
        Compute actual traversal cost factoring in risk multipliers.
        Returns infinity if the road is blocked.
        """
        if self.blocked:
            return float("inf")
        risk = graph.nodes[self.node_b].risk_level
        return self.cost * SimConfig.RISK_MULTIPLIER.get(risk, 1.0)

    def other(self, node_id: int) -> int:
        """Return the other endpoint of this edge."""
        return self.node_b if node_id == self.node_a else self.node_a

    def to_dict(self) -> dict:
        """Serialize edge state for API / frontend consumption."""
        return {
            "node_a": self.node_a,
            "node_b": self.node_b,
            "cost": self.cost,
            "blocked": self.blocked,
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
    - Observers are notified when roads are blocked
    - Dijkstra and BFS use effective_cost which respects risk multipliers
    """

    def __init__(self):
        self.nodes: dict = {}       # id -> Node
        self.edges: dict = {}       # (min_id, max_id) -> Edge (canonical key)
        self.adj: dict = {}         # id -> list of neighbor node IDs
        self._observers: list = []  # Callbacks notified when a road is blocked
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
        """Add an edge between two nodes. Ignores duplicates."""
        key = (min(id_a, id_b), max(id_a, id_b))
        if key in self.edges:
            return
        edge = Edge(id_a, id_b, cost)
        self.edges[key] = edge
        self.adj[id_a].append(id_b)
        self.adj[id_b].append(id_a)

    def remove_edge(self, id_a: int, id_b: int):
        """
        Mark an edge as blocked and remove from adjacency lists.
        The Edge object is kept (with blocked=True) for logging and history.
        Notifies all registered observers.
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        if key not in self.edges:
            return
        edge = self.edges[key]
        if edge.blocked:
            return  # Already blocked — prevent double processing
        edge.blocked = True
        # Remove from adjacency lists safely
        if id_b in self.adj[id_a]:
            self.adj[id_a].remove(id_b)
        if id_a in self.adj[id_b]:
            self.adj[id_b].remove(id_a)
        # Notify observers (A* router listens here)
        self._notify_blocked(id_a, id_b)

    def block_road(self, id_a: int, id_b: int):
        """Alias for remove_edge. Called by simulation during flood events."""
        self.remove_edge(id_a, id_b)

    # ── Neighbor queries ────────────────────────────────────

    def get_neighbors(self, node_id: int) -> list:
        """
        Return neighbors reachable via non-blocked edges.
        Filters adjacency list against actual edge blocked status.
        """
        result = []
        for nb_id in self.adj[node_id]:
            key = (min(node_id, nb_id), max(node_id, nb_id))
            edge = self.edges.get(key)
            if edge and not edge.blocked:
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

    def get_edge_cost(self, id_a: int, id_b: int) -> float:
        """
        Return the effective cost of traversing the edge.
        Factors in risk multipliers. Returns infinity if blocked or missing.
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        edge = self.edges.get(key)
        if edge is None:
            return float("inf")
        return edge.effective_cost(self)

    # ── Risk management ─────────────────────────────────────

    def update_risk(self, node_id: int, risk_level: str, risk_index: float = None):
        """
        Update a node's risk level. Called by the ML module.
        All subsequent get_edge_cost calls automatically use the new multiplier.
        """
        node = self.nodes[node_id]
        node.risk_level = risk_level
        if risk_index is not None:
            node.risk_index = risk_index

    # ── Observer pattern ────────────────────────────────────

    def register_observer(self, callback):
        """Register a callback to be notified when a road is blocked: callback(id_a, id_b)."""
        self._observers.append(callback)

    def _notify_blocked(self, id_a: int, id_b: int):
        """Notify all observers of a road blocking event."""
        for cb in self._observers:
            cb(id_a, id_b)

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

    def dijkstra(self, start_id: int) -> dict:
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
            for v in self.get_neighbors(u):
                nd = d + self.get_edge_cost(u, v)
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    # ── Post-layout population assignment ───────────────────

    def populate_after_layout(self):
        """
        After CSP assigns zone types, set population values for each node.
        Uses POPULATION_MAP from config.
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
            "grid_cols": SimConfig.GRID_COLS,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "active_edges": self.count_active_edges(),
            "blocked_edges": self.count_blocked_edges(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CityGraph":
        """
        Reconstruct a CityGraph from serialized data.
        Useful for loading saved states or receiving from API.
        """
        graph = cls()
        # Restore node attributes
        for node_data in data.get("nodes", []):
            nid = node_data["id"]
            if nid in graph.nodes:
                node = graph.nodes[nid]
                node.node_type = node_data.get("node_type", SimConfig.EMPTY)
                node.population = node_data.get("population", 0)
                node.risk_index = node_data.get("risk_index", 0.0)
                node.risk_level = node_data.get("risk_level", "NONE")
                node.accessible = node_data.get("accessible", True)
        # Restore edges
        for edge_data in data.get("edges", []):
            a, b = edge_data["node_a"], edge_data["node_b"]
            graph.add_edge(a, b, edge_data.get("cost", SimConfig.COST_STANDARD))
            if edge_data.get("blocked", False):
                graph.block_road(a, b)
        return graph
