"""Backend calculations shared by both frontends. Units are model cost and steps."""
import math
from collections import Counter

from challenges.challenge2 import generate_candidate_edges, find_bridges, UnionFind
from config.simulation_config import SimConfig


def finite(value):
    return round(value, 6) if math.isfinite(value) else None


def route(graph, src, dst, travel_mode='normal'):
    # A temporary router must never subscribe to graph mutation observers.
    from challenges.challenge4 import AStarRouter
    path = AStarRouter(graph, observe=False, travel_mode=travel_mode).astar(src, dst)
    return {
        "src": src, "dst": dst, "src_label": graph.nodes[src].label,
        "travel_mode": travel_mode,
        "dst_label": graph.nodes[dst].label, "reachable": path is not None,
        "path": path or [], "hops": len(path) - 1 if path else 0,
        "path_cost": finite(sum(graph.get_edge_cost(a, b, travel_mode) for a, b in zip(path, path[1:]))) if path else None,
    }


def ambulance_routes(state, target):
    fleet = getattr(state, 'fleet', None)
    if fleet:
        fleet.refresh_service()
    candidates = ([{**route(state.graph, u['position'], target, 'ambulance'), 'ambulance_id': u['id']} for u in fleet.units if u['status'] == 'AVAILABLE']
                  if fleet else [route(state.graph, src, target, 'ambulance') for src in state.ambulances])
    reachable = [r for r in candidates if r["reachable"]]
    return {"target": target, "candidates": candidates,
            "best": min(reachable, key=lambda r: (sum(state.graph.get_edge_cost(a,b) for a,b in zip(r['path'],r['path'][1:])),
                                                   r.get('ambulance_id', r['src']))) if reachable else None}


def analyze(state):
    graph = state.graph
    # Cache by actual model values, including changes made outside the HTTP API.
    signature = (tuple((n.node_type, n.population, n.risk_level, n.risk_index) for n in graph.nodes.values()),
                 tuple((a, b, e.cost, e.blocked, e.temporarily_blocked, tuple(sorted(e.gate_ids))) for (a, b), e in graph.edges.items()), tuple(state.ambulances))
    if getattr(state, "_analysis_signature", None) == signature:
        return state._analysis
    nodes = list(graph.nodes.values())
    types = Counter(n.node_type for n in nodes)
    risks = Counter(n.risk_level for n in nodes)
    # Connected means one component, not merely absence of isolated nodes.
    unseen = set(graph.nodes)
    components = []
    while unseen:
        root = next(iter(unseen))
        component = {n for n, d in graph.dijkstra(root).items() if math.isfinite(d)}
        components.append(component)
        unseen -= component
    largest = max(map(len, components), default=0)
    bridges = find_bridges(graph)
    connected = len(components) == 1
    residential = [n.id for n in nodes if n.node_type == SimConfig.RESIDENTIAL]
    maps = [graph.dijkstra(a) for a in state.ambulances]
    distances = {n: min((d.get(n, math.inf) for d in maps), default=math.inf) for n in residential}
    covered = [n for n, d in distances.items() if d <= SimConfig.COVERAGE_COST_LIMIT]
    coverage = 100 * len(covered) / len(residential) if residential else 100
    count = sum(risks[r] for r in ("LOW", "MEDIUM", "HIGH"))
    health = round(100 * (risks["LOW"] + risks["MEDIUM"] * SimConfig.MEDIUM_RISK_HEALTH_WEIGHT) / count) if count else 0
    candidates = generate_candidate_edges(graph)
    uf = UnionFind(max(graph.nodes, default=-1) + 1)
    mst = []
    for cost, a, b in sorted((e.cost, e.node_a, e.node_b) for e in graph.edges.values() if not e.blocked):
        if uf.union(a, b):
            mst.append({**graph.edges[(min(a,b),max(a,b))].to_dict(), "nodeA": a, "nodeB": b})
    live = [{**e.to_dict(), "nodeA": e.node_a, "nodeB": e.node_b} for e in graph.edges.values()]
    all_roads = []
    for cost, a, b in candidates:
        existing = graph.edges.get((min(a, b), max(a, b)))
        all_roads.append({"nodeA": a, "nodeB": b, "cost": cost,
                          "blocked": existing.blocked if existing else False, "candidate": existing is None})
        all_roads[-1]['temporarily_blocked'] = existing.temporarily_blocked if existing else False
    industrials = graph.get_nodes_of_type(SimConfig.INDUSTRIAL)
    hospitals = graph.get_nodes_of_type(SimConfig.HOSPITAL)
    zoning = all(abs(i.row-h.row) + abs(i.col-h.col) >= SimConfig.MIN_INDUSTRIAL_HOSPITAL_DIST for i in industrials for h in hospitals)
    result = {
        "totalNodes": len(nodes), "typeCounts": dict(types),
        "riskCounts": {r: risks[r] for r in ("HIGH", "MEDIUM", "LOW")},
        "residential": types[SimConfig.RESIDENTIAL], "hospitals": types[SimConfig.HOSPITAL],
        "schools": types[SimConfig.SCHOOL], "industrial": types[SimConfig.INDUSTRIAL],
        "powerPlants": types[SimConfig.POWER_PLANT], "depots": types[SimConfig.DEPOT],
        "healthPct": health, "connectivityPct": round(100 * largest / len(nodes), 2) if nodes else 0,
        "connected": connected, "twoEdgeConnected": connected and not bridges,
        "bridgeCount": len(bridges), "componentCount": len(components),
        "ambulanceOnlyRoads": sum(e.temporarily_blocked and not e.blocked for e in graph.edges.values()),
        "normalOpenRoads": sum(e.allows('normal') for e in graph.edges.values()),
        "coveragePct": round(coverage, 2), "deadZones": len(residential) - len(covered),
        "coveredNodes": covered, "coverageCostLimit": SimConfig.COVERAGE_COST_LIMIT,
        "worstResponseCost": finite(max(distances.values(), default=0)),
        "overallRisk": "HIGH" if risks["HIGH"] else "MEDIUM" if risks["MEDIUM"] else "LOW",
        "industrialHospitalSeparation": zoning, "edgeList": live,
        "roadViews": {"All roads": all_roads, "Optimized (MST)": mst,
                      "Optimized (2-connected)": live, "Comparison": live},
    }
    state._analysis_signature = signature
    state._analysis = result
    return result
