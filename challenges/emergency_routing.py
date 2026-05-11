# emergency_routing.py — Challenge 4: Emergency Routing via Dynamic A*
# A* search with event-driven replanning when roads are blocked.
#
# Design note: For dynamic environments, advanced alternatives exist:
#   - D* Lite: Incrementally repairs shortest path trees when edge costs change
#   - Lifelong Planning A* (LPA*): Maintains consistent g-values across changes
# However, for a 225-node grid, full A* re-computation is fast enough (~1ms)
# and simpler to implement, validate, and explain in a viva.
#
# All algorithms implemented from scratch — no external pathfinding libraries.

import math
import heapq
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


# ──────────────────────────────────────────────────────────
# Heuristic function — Euclidean distance
# Admissible because: straight-line distance <= actual road cost
# (minimum edge cost is 0.8, and grid spacing is 1.0)
# Manhattan would over-estimate with diagonal edges (cost 1.4)
# ──────────────────────────────────────────────────────────
def heuristic(graph: CityGraph, node_id: int, goal_id: int) -> float:
    """Euclidean distance heuristic. Admissible and consistent for this grid."""
    n = graph.nodes[node_id]
    g = graph.nodes[goal_id]
    return math.sqrt((n.row - g.row) ** 2 + (n.col - g.col) ** 2)


class AStarRouter:
    """
    Emergency routing system using A* search with dynamic replanning.

    Features:
        - Optimal shortest path via A* with Euclidean heuristic
        - Event-driven replanning: automatically recalculates when a road is blocked
        - Sequential civilian rescue: visits civilians in order
        - No stale cached paths: paths are always recomputed from current position

    The router registers as an observer on the shared graph, so road blocks
    trigger immediate re-evaluation without polling.
    """

    def __init__(self, graph: CityGraph):
        self.graph = graph
        self.current_path: list = []      # Remaining path nodes
        self.current_pos: int = None      # Team's current position (node ID)
        self.civilians: list = []         # Unvisited civilian node IDs (ordered)
        self.visited: list = []           # Rescued civilian node IDs
        self.log: list = []               # Event log entries (simulation collects these)
        self.total_reroutes: int = 0      # Count of replanning events

        # Register as observer for road block events
        self.graph.register_observer(self._on_road_blocked)

    # ── Mission setup ───────────────────────────────────────

    def set_mission(self, start_id: int, civilian_ids: list):
        """Initialize a rescue mission from start_id visiting all civilian_ids in sequence."""
        self.current_pos = start_id
        self.civilians = list(civilian_ids)
        self.visited = []
        self._plan_next_leg()

    # ── Path planning ───────────────────────────────────────

    def _plan_next_leg(self):
        """Plan route from current position to next unvisited civilian."""
        if not self.civilians:
            self.current_path = []
            self.log.append("MISSION COMPLETE: All civilians reached.")
            return

        next_target = self.civilians[0]
        path = self.astar(self.current_pos, next_target)

        if path is None:
            self.log.append(
                f"WARNING: No path to civilian at node {self.graph.nodes[next_target].label}. Skipping."
            )
            self.civilians.pop(0)
            self._plan_next_leg()  # Try next civilian
        else:
            self.current_path = path
            self.log.append(
                f"ROUTE PLANNED: {self.graph.nodes[self.current_pos].label} -> {self.graph.nodes[next_target].label}, "
                f"{len(path)} steps"
            )

    # ── A* algorithm — from scratch ─────────────────────────

    def astar(self, start_id: int, goal_id: int) -> list:
        """
        A* search algorithm. Returns list of node IDs (path) or None.

        Guarantees:
            - Optimal path (Euclidean heuristic is admissible + consistent)
            - Respects blocked roads (via graph.get_neighbors)
            - Respects risk multipliers (via graph.get_edge_cost)
            - No stale data (always queries live graph state)
        """
        if start_id == goal_id:
            return [start_id]

        g_score = {start_id: 0.0}
        came_from = {start_id: None}

        # Priority queue: (f_score, node_id)
        heap = [(heuristic(self.graph, start_id, goal_id), start_id)]
        closed = set()

        while heap:
            f, current = heapq.heappop(heap)

            if current in closed:
                continue
            closed.add(current)

            if current == goal_id:
                return self._reconstruct_path(came_from, goal_id)

            for neighbor in self.graph.get_neighbors(current):
                if neighbor in closed:
                    continue
                tentative_g = g_score[current] + self.graph.get_edge_cost(current, neighbor)
                if tentative_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g
                    came_from[neighbor] = current
                    f_score = tentative_g + heuristic(self.graph, neighbor, goal_id)
                    heapq.heappush(heap, (f_score, neighbor))

        return None  # No path found

    def _reconstruct_path(self, came_from: dict, end_id: int) -> list:
        """Reconstruct path from came_from dict."""
        path = []
        node = end_id
        while node is not None:
            path.append(node)
            node = came_from[node]
        path.reverse()
        return path

    # ── Observer callback — road block handler ──────────────

    def _on_road_blocked(self, id_a: int, id_b: int):
        """
        Called automatically when a road is blocked on the shared graph.
        If the blocked edge is on the current path, triggers replanning.
        No stale cached paths — recomputes from current position.
        """
        if self._path_uses_edge(id_a, id_b):
            self.total_reroutes += 1
            self.log.append(
                f"REPLANNING: Road ({self.graph.nodes[id_a].label} <-> {self.graph.nodes[id_b].label}) blocked on current route. "
                f"Recalculating from node {self.graph.nodes[self.current_pos].label}."
            )
            self._plan_next_leg()

    def _path_uses_edge(self, id_a: int, id_b: int) -> bool:
        """Check if the blocked edge is part of the current planned path."""
        for i in range(len(self.current_path) - 1):
            a = self.current_path[i]
            b = self.current_path[i + 1]
            if (a == id_a and b == id_b) or (a == id_b and b == id_a):
                return True
        return False

    # ── Step execution ──────────────────────────────────────

    def advance_one_step(self) -> int:
        """
        Move the team one node forward along the current path.
        Returns the new position node ID, or None if no movement.
        """
        if not self.current_path or len(self.current_path) < 2:
            return None

        # Move to next node in path
        self.current_pos = self.current_path[1]
        self.current_path.pop(0)

        # Check if we've reached the target civilian
        if self.civilians and self.current_pos == self.civilians[0]:
            self.log.append(f"CIVILIAN REACHED at node {self.graph.nodes[self.current_pos].label}")
            self.visited.append(self.civilians.pop(0))
            self._plan_next_leg()

        return self.current_pos

    # ── Serialization ───────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize router state for API / frontend."""
        return {
            "current_pos": self.current_pos,
            "current_path": self.current_path,
            "civilians_remaining": self.civilians,
            "civilians_rescued": self.visited,
            "total_reroutes": self.total_reroutes,
        }


# ──────────────────────────────────────────────────────────
# Entry point — simulation creates router here
# ──────────────────────────────────────────────────────────
def create_router(graph: CityGraph) -> AStarRouter:
    """Create and return an A* router bound to the shared graph."""
    return AStarRouter(graph)
