# reference_dijkstra.py — CityMind 2D: Independent Reference Shortest-Path
#
# This is the TRUSTED reference implementation used to verify backend routes.
# It uses the same edge-cost semantics as the backend (effective_cost =
# base_cost * RISK_MULTIPLIER[node_b.risk_level]) and returns both the
# shortest path and a validation report.
#
# This module never calls the backend. It works from a GraphSnapshot already
# fetched and stored in AppState.

import heapq
from typing import Optional

# Risk multipliers mirror config/simulation_config.py
RISK_MULTIPLIER = {
    "HIGH":   2.0,
    "MEDIUM": 1.5,
    "LOW":    1.0,
    "NONE":   1.0,
}


def effective_cost(edge: dict, nodes: dict) -> float:
    """
    Compute the effective traversal cost for an edge dict.
    Mirrors Edge.effective_cost() in city_graph.py.

    edge keys: node_a (or nodeA), node_b (or nodeB), cost, blocked
    nodes: id -> node_dict  (with risk_level key)
    """
    if edge.get("blocked", False):
        return float("inf")
    # Normalise key names from both backend (node_a/node_b) and frontend (nodeA/nodeB)
    node_b_id = edge.get("node_b", edge.get("nodeB"))
    base_cost  = edge.get("cost", 1.0)
    node_b = nodes.get(node_b_id)
    if node_b is None:
        return float("inf")
    risk = node_b.get("risk_level", "NONE")
    return base_cost * RISK_MULTIPLIER.get(risk, 1.0)


def build_adj(nodes: dict, edges: list):
    """
    Build adjacency map: node_id -> list of (neighbor_id, effective_cost, edge_dict)
    Edges are undirected, but effective_cost depends on destination (node_b direction).
    We add BOTH directions, computing cost with the correct destination each time.
    """
    adj: dict = {nid: [] for nid in nodes}
    for edge in edges:
        if edge.get("blocked", False):
            continue
        na = edge.get("node_a", edge.get("nodeA"))
        nb = edge.get("node_b", edge.get("nodeB"))
        if na is None or nb is None:
            continue
        # Cost a→b (node_b = nb)
        cost_ab = effective_cost(edge, nodes)
        # Cost b→a (node_b = na, so we flip)
        flipped = dict(edge)
        flipped["node_b"] = na
        flipped["node_a"] = nb
        cost_ba = effective_cost(flipped, nodes)

        if na in adj:
            adj[na].append((nb, cost_ab, edge))
        if nb in adj:
            adj[nb].append((na, cost_ba, edge))
    return adj


def dijkstra(
    nodes: dict,
    edges: list,
    start_id: int,
    goal_id: Optional[int] = None,
) -> dict:
    """
    Reference Dijkstra implementation.

    Uses real edge costs and risk multipliers.
    Rejects negative edge weights (logs them but skips).

    Returns dict with keys:
        dist       : {node_id: float}  — shortest distance from start
        prev       : {node_id: int}    — predecessor map
        path       : list[int]         — path to goal_id (empty if unreachable or no goal)
        path_cost  : float             — total cost of path to goal_id
        reachable  : bool
        hops       : int               — number of edges in path
        warnings   : list[str]         — non-fatal issues
    """
    warnings = []
    adj = build_adj(nodes, edges)

    dist = {nid: float("inf") for nid in nodes}
    prev = {nid: None for nid in nodes}
    dist[start_id] = 0.0

    heap = [(0.0, start_id)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue   # stale entry
        for v, cost, _edge in adj.get(u, []):
            if cost < 0:
                warnings.append(f"Negative edge cost {cost:.3f} on ({u},{v}) — skipped (Dijkstra undefined)")
                continue
            nd = d + cost
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    # Reconstruct path to goal_id
    path = []
    path_cost = float("inf")
    reachable = False

    if goal_id is not None:
        if dist.get(goal_id, float("inf")) < float("inf"):
            reachable = True
            path_cost = dist[goal_id]
            node = goal_id
            while node is not None:
                path.append(node)
                node = prev[node]
            path.reverse()
        else:
            warnings.append(f"Node {goal_id} is unreachable from {start_id}.")

    return {
        "dist":       dist,
        "prev":       prev,
        "path":       path,
        "path_cost":  path_cost,
        "reachable":  reachable,
        "hops":       max(0, len(path) - 1),
        "warnings":   warnings,
        "start_id":   start_id,
        "goal_id":    goal_id,
    }


def validate_path(
    path: list,
    nodes: dict,
    edges: list,
    claimed_cost: Optional[float] = None,
    check_optimality: bool = True,
    expected_source: Optional[int] = None,
    expected_target: Optional[int] = None,
) -> dict:
    """
    Validate a path (list of node_ids) against the current graph snapshot.

    Checks:
    1. Path is non-empty list of valid integer node IDs (F19).
    2. Separates unreachable destination from malformed/invalid path (F18).
    3. Validates path against expected_source and expected_target if provided (F22).
    4. Every consecutive pair is connected by a non-blocked edge.
    5. Actual path cost matches claimed_cost (if provided).
    6. Optimality: run reference Dijkstra between expected or path endpoints (F22).

    Returns a validation report dict:
        valid           : bool
        unreachable     : bool
        issues          : list[str]
        actual_cost     : float
        claimed_cost    : float or None
        cost_match      : bool or None
        optimal         : bool or None
        ref_cost        : float or None
        ref_path        : list[int] or None
        expected_source : int or None
        expected_target : int or None
    """
    issues = []

    if not isinstance(path, list) or not path:
        is_unreachable = False
        if expected_source is not None and expected_target is not None:
            if expected_source in nodes and expected_target in nodes:
                ref = dijkstra(nodes, edges, expected_source, expected_target)
                if not ref.get("reachable", False):
                    is_unreachable = True
        return {
            "valid":           False,
            "unreachable":     is_unreachable,
            "issues":          ["Destination is unreachable."] if is_unreachable else ["Path is empty."],
            "actual_cost":     float("inf"),
            "claimed_cost":    claimed_cost,
            "cost_match":      None,
            "optimal":         None,
            "ref_cost":        float("inf") if is_unreachable else None,
            "ref_path":        [] if is_unreachable else None,
            "expected_source": expected_source,
            "expected_target": expected_target,
        }

    # F19: Safely validate node IDs before graph lookups
    has_type_or_missing_error = False
    for i, nid in enumerate(path):
        if not isinstance(nid, int):
            issues.append(f"Node at index {i} is not an integer ID: {nid!r}")
            has_type_or_missing_error = True
        elif nid not in nodes:
            issues.append(f"Node {nid} at index {i} does not exist in graph.")
            has_type_or_missing_error = True

    # F22: Endpoint validation
    if expected_source is not None and len(path) > 0 and path[0] != expected_source:
        issues.append(f"Path starts at {path[0]}, expected {expected_source}.")
    if expected_target is not None and len(path) > 0 and path[-1] != expected_target:
        issues.append(f"Path ends at {path[-1]}, expected {expected_target}.")

    # Build edge lookup
    edge_map = {}
    for e in edges:
        na = e.get("node_a", e.get("nodeA"))
        nb = e.get("node_b", e.get("nodeB"))
        if isinstance(na, int) and isinstance(nb, int):
            edge_map[(min(na, nb), max(na, nb))] = e

    actual_cost = 0.0

    if has_type_or_missing_error:
        actual_cost = float("inf")
    elif len(path) == 1:
        # F19: Single-node path
        if expected_source is not None and expected_target is not None:
            if expected_source != expected_target:
                issues.append(f"Single-node path cannot connect {expected_source} to {expected_target}.")
                actual_cost = float("inf")
            elif path[0] != expected_source:
                issues.append(f"Single-node path [{path[0]}] does not match source {expected_source}.")
                actual_cost = float("inf")
            else:
                actual_cost = 0.0
        else:
            actual_cost = 0.0
    else:
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            key = (min(a, b), max(a, b))
            edge = edge_map.get(key)
            if edge is None:
                issues.append(f"No edge between {a} and {b}.")
                actual_cost = float("inf")
            elif edge.get("blocked", False):
                issues.append(f"Edge ({a},{b}) is blocked.")
                actual_cost = float("inf")
            else:
                traversal_edge = dict(edge)
                traversal_edge["node_b"] = b
                traversal_edge["node_a"] = a
                actual_cost += effective_cost(traversal_edge, nodes)

    cost_match = None
    if claimed_cost is not None and actual_cost < float("inf"):
        cost_match = abs(actual_cost - claimed_cost) < 1e-6

    # Optimality check (F22: check endpoints)
    optimal = None
    ref_cost = None
    ref_path = None
    if check_optimality and len(path) >= 2 and not has_type_or_missing_error:
        src_chk = expected_source if expected_source is not None else path[0]
        dst_chk = expected_target if expected_target is not None else path[-1]
        ref = dijkstra(nodes, edges, src_chk, dst_chk)
        ref_cost = ref["path_cost"]
        ref_path = ref["path"]
        if ref_cost < float("inf"):
            optimal = actual_cost <= ref_cost + 1e-6
            if not optimal:
                issues.append(
                    f"Suboptimal path: actual={actual_cost:.4f}, optimal={ref_cost:.4f} "
                    f"(excess={actual_cost - ref_cost:.4f})"
                )
        else:
            issues.append("Reference Dijkstra found destination unreachable.")

    valid = (len(issues) == 0) and actual_cost < float("inf")

    return {
        "valid":           valid,
        "unreachable":     False,
        "issues":          issues,
        "actual_cost":     actual_cost,
        "claimed_cost":    claimed_cost,
        "cost_match":      cost_match,
        "optimal":         optimal,
        "ref_cost":        ref_cost,
        "ref_path":        ref_path,
        "expected_source": expected_source,
        "expected_target": expected_target,
    }


def compute_path_breakdown(path: list, nodes: dict, edges: list) -> list:
    """
    For each edge in a path, return a breakdown dict:
      {from_id, to_id, from_label, to_label, base_cost, risk_level, risk_mult, effective_cost}
    Used by Route Lab for per-edge inspection.
    """
    edge_map = {}
    for e in edges:
        na = e.get("node_a", e.get("nodeA"))
        nb = e.get("node_b", e.get("nodeB"))
        if na is not None and nb is not None:
            edge_map[(min(na, nb), max(na, nb))] = e

    breakdown = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        key = (min(a, b), max(a, b))
        edge = edge_map.get(key, {})
        base = edge.get("cost", 1.0)
        nb_node = nodes.get(b, {})
        risk = nb_node.get("risk_level", "NONE")
        mult  = RISK_MULTIPLIER.get(risk, 1.0)
        eff   = base * mult if not edge.get("blocked", False) else float("inf")

        def label(nid):
            n = nodes.get(nid, {})
            col = n.get("col", 0)
            row = n.get("row", 0)
            return f"{chr(65+col)}{row+1}"

        breakdown.append({
            "from_id":       a,
            "to_id":         b,
            "from_label":    label(a),
            "to_label":      label(b),
            "base_cost":     base,
            "risk_level":    risk,
            "risk_mult":     mult,
            "effective_cost":eff,
            "blocked":       edge.get("blocked", False),
        })
    return breakdown
