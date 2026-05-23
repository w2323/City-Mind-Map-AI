# challenge2.py — Challenge 2: Road Network Optimization (MST)

import random
from collections import deque
from core.city_graph import CityGraph
from config.simulation_config import SimConfig



def generate_candidate_edges(graph: CityGraph) -> list:
    """
    Generate all possible grid-adjacent edges as (cost, id_a, id_b) tuples.
    4-directional: cost 1.0 (or 0.8 if both endpoints are RESIDENTIAL)
    Diagonal: cost 1.4
    """
    edges = []
    for row in range(SimConfig.GRID_ROWS):
        for col in range(SimConfig.GRID_COLS):
            node = graph.get_node(row, col)

            # Right neighbor
            if col + 1 < SimConfig.GRID_COLS:
                nb = graph.get_node(row, col + 1)
                cost = (SimConfig.COST_RESIDENTIAL
                        if node.node_type == SimConfig.RESIDENTIAL
                        and nb.node_type == SimConfig.RESIDENTIAL
                        else SimConfig.COST_STANDARD)
                edges.append((cost, node.id, nb.id))

            # Down neighbor
            if row + 1 < SimConfig.GRID_ROWS:
                nb = graph.get_node(row + 1, col)
                cost = (SimConfig.COST_RESIDENTIAL
                        if node.node_type == SimConfig.RESIDENTIAL
                        and nb.node_type == SimConfig.RESIDENTIAL
                        else SimConfig.COST_STANDARD)
                edges.append((cost, node.id, nb.id))

            # Diagonal down-right
            if row + 1 < SimConfig.GRID_ROWS and col + 1 < SimConfig.GRID_COLS:
                nb = graph.get_node(row + 1, col + 1)
                edges.append((SimConfig.COST_DIAGONAL, node.id, nb.id))

            # Diagonal down-left
            if row + 1 < SimConfig.GRID_ROWS and col - 1 >= 0:
                nb = graph.get_node(row + 1, col - 1)
                edges.append((SimConfig.COST_DIAGONAL, node.id, nb.id))

    return edges



class UnionFind:
    """Union-Find (Disjoint Set) with path compression and union by rank."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """Union by rank. Returns True if x and y were in different sets."""
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True



def build_mst(graph: CityGraph) -> list:
    """
    Build Minimum Spanning Tree using Kruskal's algorithm.
    Returns list of (id_a, id_b, cost) for MST edges.
    Also adds those edges to the shared graph.
    """
    candidates = generate_candidate_edges(graph)
    candidates.sort()  # Sort by cost (greedy choice)
    uf = UnionFind(SimConfig.GRID_ROWS * SimConfig.GRID_COLS)
    mst_edges = []

    for cost, a, b in candidates:
        if uf.union(a, b):
            mst_edges.append((a, b, cost))
            graph.add_edge(a, b, cost)
            if len(mst_edges) == SimConfig.GRID_ROWS * SimConfig.GRID_COLS - 1:
                break  # MST complete (V-1 edges)

    return mst_edges



def add_redundancy_edges(graph: CityGraph, extra_count: int = None):
    """
    Add extra edges beyond MST to improve network robustness.
    Priority: dead-end nodes (degree == 1) first, then cheapest available.
    """
    if extra_count is None:
        extra_count = SimConfig.REDUNDANCY_EDGES

    candidates = generate_candidate_edges(graph)
    existing = set(graph.edges.keys())

    # Only edges not already in the graph
    non_mst = [(c, a, b) for c, a, b in candidates
               if (min(a, b), max(a, b)) not in existing]
    non_mst.sort()

    # Dead-end nodes — only 1 active neighbor
    dead_ends = {nid for nid in graph.nodes if len(graph.adj[nid]) == 1}

    added = 0

    # Priority 1: Connect dead-end nodes
    for cost, a, b in non_mst:
        if added >= extra_count:
            break
        if a in dead_ends or b in dead_ends:
            graph.add_edge(a, b, cost)
            added += 1

    # Priority 2: Cheapest remaining edges
    for cost, a, b in non_mst:
        if added >= extra_count:
            break
        key = (min(a, b), max(a, b))
        if key not in graph.edges:
            graph.add_edge(a, b, cost)
            added += 1



def bfs_path(graph: CityGraph, start: int, end: int) -> list:
    """Standard BFS. Returns list of node IDs from start to end, or None."""
    if start == end:
        return [start]
    visited = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nb in graph.get_neighbors(cur):
            if nb not in visited:
                visited[nb] = cur
                if nb == end:
                    path = []
                    node = end
                    while node is not None:
                        path.append(node)
                        node = visited[node]
                    path.reverse()
                    return path
                queue.append(nb)
    return None


def bfs_path_excluding(graph: CityGraph, start: int, end: int,
                       excluded_edges: set) -> list:
    """BFS that skips edges whose canonical key is in excluded_edges."""
    if start == end:
        return [start]
    visited = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nb in graph.get_neighbors(cur):
            key = (min(cur, nb), max(cur, nb))
            if key in excluded_edges:
                continue
            if nb not in visited:
                visited[nb] = cur
                if nb == end:
                    path = []
                    node = end
                    while node is not None:
                        path.append(node)
                        node = visited[node]
                    path.reverse()
                    return path
                queue.append(nb)
    return None



def ensure_hospital_depot_redundancy(graph: CityGraph) -> bool:
    """
    Verify and enforce 2 edge-disjoint paths between Primary Hospital
    and Primary Ambulance Depot.

    Edge-disjoint means: no single edge failure can disconnect both paths.
    This is stronger than just "two different paths" — it uses the
    max-flow/min-cut principle (if min-cut >= 2, then 2 edge-disjoint
    paths exist by Menger's theorem).

    Note: For production systems, D* Lite or Lifelong Planning A* could
    provide more efficient dynamic replanning, but for this 225-node grid,
    BFS-based verification is sufficient and simpler to validate.
    """
    hospitals = graph.get_nodes_of_type(SimConfig.HOSPITAL)
    depots = graph.get_nodes_of_type(SimConfig.DEPOT)
    if not hospitals or not depots:
        return False

    h_id = hospitals[0].id    # Primary hospital
    d_id = depots[0].id       # Primary depot

    # Find first path via BFS
    path1 = bfs_path(graph, h_id, d_id)
    if path1 is None:
        return False

    # Collect edges used by path1
    used_edges = set()
    for i in range(len(path1) - 1):
        used_edges.add((min(path1[i], path1[i + 1]), max(path1[i], path1[i + 1])))

    # Try to find second path that shares NO edges with path1
    path2 = bfs_path_excluding(graph, h_id, d_id, used_edges)
    if path2 is not None:
        return True  # Already have 2 edge-disjoint paths

    # No second path found — incrementally add edges until one exists
    candidates = generate_candidate_edges(graph)
    candidates.sort()
    for cost, a, b in candidates:
        key = (min(a, b), max(a, b))
        if key not in graph.edges and key not in used_edges:
            graph.add_edge(a, b, cost)
            path2 = bfs_path_excluding(graph, h_id, d_id, used_edges)
            if path2 is not None:
                return True

    return False


def find_bridges(graph: CityGraph) -> list:
    """
    Find bridge edges (edges whose removal disconnects the graph).
    Uses Tarjan's bridge-finding algorithm.
    Useful for identifying critical single-points-of-failure in the road network.
    """
    disc = {}
    low = {}
    parent = {}
    bridges = []
    timer = [0]

    def dfs(u):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in graph.get_neighbors(u):
            if v not in disc:
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.append((min(u, v), max(u, v)))
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])

    # Run from all unvisited nodes (handles disconnected components)
    for nid in graph.nodes:
        if nid not in disc:
            parent[nid] = -1
            dfs(nid)

    return bridges



def build_road_network(graph: CityGraph) -> bool:
    """
    Build the complete road network:
    1. Kruskal's MST for minimum-cost spanning tree
    2. Redundancy edges to eliminate dead ends
    3. Edge-disjoint hospital-depot path guarantee
    """
    build_mst(graph)
    add_redundancy_edges(graph)
    success = ensure_hospital_depot_redundancy(graph)
    if not success:
        raise RuntimeError(
            "Critical: Could not establish 2 edge-disjoint paths "
            "between Primary Hospital and Ambulance Depot."
        )
    return True
