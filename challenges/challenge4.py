# challenge4.py — Challenge 4: Emergency Routing via Dynamic A* search
#
# FIXES APPLIED:
# F1  — A* heuristic now scaled by min_cost_per_unit (0.8) to ensure admissibility
# F11 — Deferred (unreachable) civilians tracked separately; restored on road unblock
# F12 — Mission completion message distinguishes all-rescued vs partial (skips)
# F26 — Router subscribes to graph unblock events to retry deferred civilians
# F32 — Batched edge-blocking suppresses intermediate replans; one replan per flood event
# F33 — Structured event callbacks replace free-form log string parsing
# F34 — Response times tracked: step_assigned → step_reached per civilian
# F37 — Mission start node and current target stored; exposed in to_dict()

import math
import heapq
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


# ── Admissible heuristic ──────────────────────────────────────────────────────
# F1 FIX: The minimum edge cost in the graph is COST_RESIDENTIAL = 0.8
# (residential-to-residential edges). Diagonal edges cost 1.4 vs geometric ~1.414.
# To guarantee admissibility (never overestimate), we scale the Euclidean distance
# by the minimum possible cost-per-unit-distance = 0.8.
# This ensures the heuristic is a lower bound on the actual path cost.
_MIN_COST_PER_UNIT = SimConfig.COST_RESIDENTIAL  # 0.8


def heuristic(graph: CityGraph, node_id: int, goal_id: int) -> float:
    """
    Admissible A* heuristic: Euclidean distance scaled by minimum edge cost per unit.
    This guarantees h(n) <= actual cost for all graphs using this cost model.
    F1: Uses COST_RESIDENTIAL (0.8) as the minimum possible cost multiplier.
    """
    n = graph.nodes[node_id]
    g = graph.nodes[goal_id]
    euclidean = math.sqrt((n.row - g.row) ** 2 + (n.col - g.col) ** 2)
    return euclidean * _MIN_COST_PER_UNIT


class AStarRouter:
    """
    Emergency routing system using A* search with dynamic replanning.

    Features:
        - Optimal shortest path via A* with admissible Euclidean heuristic (F1)
        - Event-driven replanning: automatically recalculates when a road is blocked
        - Road unblock awareness: deferred civilians retried when connectivity returns (F11/F26)
        - Sequential civilian rescue: visits civilians in order
        - Deferred civilians: unreachable targets tracked separately, not silently dropped (F11)
        - Structured event callbacks: metrics derived from events, not log strings (F33)
        - Response time tracking: steps from assignment to rescue (F34)
        - Mission endpoints stored in state: start node and current target (F37)
        - Batched flood replanning: one replan per flood event, not per edge (F32)

    The router registers as an observer on the shared graph, so road blocks and unblocks
    trigger immediate re-evaluation without polling.
    """

    def __init__(self, graph: CityGraph, observe: bool = True, travel_mode: str = 'ambulance'):
        self.graph = graph
        if travel_mode not in ('ambulance', 'normal', 'commercial'):
            raise ValueError('Unknown travel mode')
        self.travel_mode = travel_mode
        self.current_path: list = []      # Remaining path nodes to current target
        self.current_pos: int = None      # Team's current position (node ID)
        self.civilians: list = []         # Unvisited civilian node IDs (ordered)
        self.deferred: list = []          # F11: Civilians that were unreachable (retried on unblock)
        self.visited: list = []           # Rescued civilian node IDs
        self.log: list = []               # Event log entries (simulation collects these)
        self.total_reroutes: int = 0      # Count of replanning events

        # F37: Mission metadata
        self.mission_start_id: int = None        # Starting node of the mission
        self.mission_target_id: int = None       # Current target civilian node ID

        # F34: Response time tracking
        self._civilian_assigned_step: dict = {}  # civilian_id -> step when assigned
        self._current_step: int = 0              # Updated each advance_one_step call

        # F33: Structured event callbacks
        # on_civilian_rescued(civilian_id) — called when a civilian is rescued
        # on_civilian_deferred(civilian_id) — called when a civilian is deferred (unreachable)
        # on_replanning(reason) — called on route replanning
        # on_mission_complete(rescued_count, deferred_count) — called on mission end
        self.on_civilian_rescued = None
        self.on_civilian_deferred = None
        self.on_replanning = None
        self.on_mission_complete = None

        # F32: Suppress intermediate replans during batched edge blocking
        self._suppress_replan: bool = False

        # Register as observer for road block, unblock, and risk change events
        if observe:
            self.graph.register_observer(self._on_road_blocked)
            self.graph.register_unblock_observer(self._on_road_unblocked)
            self.graph.register_risk_observer(self._on_risk_changed)
            if travel_mode != 'ambulance':
                self.graph.register_access_observer(lambda: self._on_road_unblocked(None, None))

    @property
    def deferred_civilians(self) -> list:
        """Alias for self.deferred (F11)."""
        return self.deferred

    def set_step(self, step: int):
        """Update the current simulation step for response time tracking (F34)."""
        self._current_step = step

    def set_mission(self, start_id: int, civilian_ids: list):
        """Initialize a rescue mission from start_id visiting all civilian_ids in sequence."""
        self.current_pos = start_id
        self.mission_start_id = start_id      # F37
        self.civilians = list(civilian_ids)
        self.deferred = []                    # F11: clear deferred list
        self.visited = []
        # F34: Record assignment step for all civilians
        for civ_id in civilian_ids:
            self._civilian_assigned_step[civ_id] = self._current_step
        self._plan_next_leg()

    def _plan_next_leg(self):
        """Plan route from current position to next unvisited civilian."""
        if not self.civilians:
            # F12: Distinguish "all rescued" vs "partial with deferred"
            rescued = len(self.visited)
            deferred = len(self.deferred)
            if deferred == 0:
                self.current_path = []
                self.mission_target_id = None   # F37
                msg = f"MISSION COMPLETE: All {rescued} civilians rescued."
                self.log.append(msg)
                if self.on_mission_complete:
                    self.on_mission_complete(rescued, 0)
            else:
                self.current_path = []
                self.mission_target_id = None   # F37
                msg = (
                    f"MISSION ENDED: {rescued} civilian(s) rescued, "
                    f"{deferred} deferred (unreachable, will retry if connectivity returns)."
                )
                self.log.append(msg)
                if self.on_mission_complete:
                    self.on_mission_complete(rescued, deferred)
            return

        next_target = self.civilians[0]
        self.mission_target_id = next_target   # F37
        path = self.astar(self.current_pos, next_target)

        if path is None:
            # F11: Defer unreachable civilian — do NOT permanently drop them
            deferred_civ = self.civilians.pop(0)
            self.deferred.append(deferred_civ)
            warning_msg = (
                f"WARNING: No path to civilian at node {self.graph.nodes[deferred_civ].label}. "
                f"Deferred for retry if road connectivity is restored."
            )
            self.log.append(warning_msg)
            if self.on_civilian_deferred:
                self.on_civilian_deferred(deferred_civ)  # F33
            self._plan_next_leg()  # Try next civilian
        else:
            self.current_path = path
            self.log.append(
                f"ROUTE PLANNED: {self.graph.nodes[self.current_pos].label} -> "
                f"{self.graph.nodes[next_target].label}, {len(path)} steps"
            )

    def astar(self, start_id: int, goal_id: int) -> list:
        """
        A* search algorithm. Returns list of node IDs (path) or None.

        Guarantees (F1 fixed):
            - Optimal path (admissible heuristic: Euclidean * 0.8 never overestimates)
            - Respects blocked roads (via graph.get_neighbors)
            - Respects risk multipliers (via graph.get_edge_cost)
            - No stale data (always queries live graph state)
            - Handles equal-cost node reopening correctly (g_score comparison)
        """
        if start_id == goal_id:
            return [start_id]

        g_score = {start_id: 0.0}
        came_from = {start_id: None}

        # Priority queue: (f_score, node_id)
        # Derive a consistent bound from live edges: custom cheap/long roads
        # may violate the grid's fixed 0.8 cost-per-unit assumption.
        scale = min((e.cost * min(SimConfig.RISK_MULTIPLIER.values()) /
                     max(math.hypot(self.graph.nodes[e.node_a].row - self.graph.nodes[e.node_b].row,
                                    self.graph.nodes[e.node_a].col - self.graph.nodes[e.node_b].col), 1)
                     for e in self.graph.edges.values() if e.allows(self.travel_mode)), default=0)
        def estimate(n):
            a, b = self.graph.nodes[n], self.graph.nodes[goal_id]
            return math.hypot(a.row-b.row, a.col-b.col) * scale
        heap = [(estimate(start_id), start_id)]
        closed = set()

        while heap:
            f, current = heapq.heappop(heap)

            if current in closed:
                continue
            closed.add(current)

            if current == goal_id:
                return self._reconstruct_path(came_from, goal_id)

            for neighbor in self.graph.get_neighbors(current, self.travel_mode):
                if neighbor in closed:
                    continue
                tentative_g = g_score[current] + self.graph.get_edge_cost(current, neighbor, self.travel_mode)
                if tentative_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g
                    came_from[neighbor] = current
                    f_score = tentative_g + estimate(neighbor)
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

    def _on_road_blocked(self, id_a: int, id_b: int):
        """
        Called automatically when a road is blocked on the shared graph.
        If the blocked edge is on the current path, triggers replanning.
        F32: If _suppress_replan is True (during batch flood), skip individual replans.
        """
        if self._suppress_replan:
            return  # F32: Will replan once after full batch is applied
        if self._path_uses_edge(id_a, id_b):
            self.total_reroutes += 1
            replan_msg = (
                f"REPLANNING: Road ({self.graph.nodes[id_a].label} <-> "
                f"{self.graph.nodes[id_b].label}) blocked on current route. "
                f"Recalculating from node {self.graph.nodes[self.current_pos].label}."
            )
            self.log.append(replan_msg)
            if self.on_replanning:
                self.on_replanning(f"edge ({id_a},{id_b}) blocked")  # F33
            self._plan_next_leg()

    def _on_road_unblocked(self, id_a: int, id_b: int):
        """
        F26: Called when a road is unblocked on the shared graph.
        If there are deferred civilians, retry them — connectivity may have been restored.
        F11: Move deferred civilians back to the queue for retry.
        """
        if self.deferred:
            # Restore deferred civilians to the front of the queue for retry
            # Keep original order: deferred first, then remaining
            self.civilians = self.deferred + self.civilians
            self.deferred = []
            self.log.append(
                f"ROAD RESTORED: Retrying {len(self.civilians)} deferred/pending civilian(s). "
                f"Replanning from {self.graph.nodes[self.current_pos].label}."
            )
            self._plan_next_leg()
        elif self.civilians:
            self._plan_next_leg()

    def _on_risk_changed(self, node_id: int):
        """
        F2: Called when a node's risk level changes.
        If the node is on the current path, recalculate route to find cheaper detour.
        """
        if self._suppress_replan:
            self._batch_affected = bool(self.current_path) or getattr(self, "_batch_affected", False)
            return
        if self.current_path:
            self.total_reroutes += 1
            if self.on_replanning:
                self.on_replanning(f"node {node_id} risk changed")
            self._plan_next_leg()

    def begin_batch_block(self):
        """
        F32: Begin a batch road-blocking operation. Suppress intermediate replans.
        Call end_batch_block() after all edges have been blocked.
        """
        self._suppress_replan = True
        self._batch_affected = False  # Track if any blocked edge was on current path

    def end_batch_block(self):
        """
        F32: End a batch road-blocking operation and trigger a single replan if needed.
        """
        self._suppress_replan = False
        if self._batch_affected:
            self.total_reroutes += 1
            self.log.append(
                f"REPLANNING (batch flood): Recalculating from node "
                f"{self.graph.nodes[self.current_pos].label}."
            )
            if self.on_replanning:
                self.on_replanning("batch flood")  # F33
            self._plan_next_leg()
            self._batch_affected = False

    def mark_batch_affected(self, id_a: int, id_b: int):
        """F32: Called during batch blocking to record if current path is affected."""
        if self._path_uses_edge(id_a, id_b):
            self._batch_affected = True

    def _path_uses_edge(self, id_a: int, id_b: int) -> bool:
        """Check if the blocked edge is part of the current planned path."""
        for i in range(len(self.current_path) - 1):
            a = self.current_path[i]
            b = self.current_path[i + 1]
            if (a == id_a and b == id_b) or (a == id_b and b == id_a):
                return True
        return False

    def advance_one_step(self, current_step: int = None) -> int:
        """
        Move the team one node forward along the current path.
        Returns the new position node ID, or None if no movement.
        F34: Accepts current_step for response time tracking.
        """
        if current_step is not None:
            self._current_step = current_step

        if not self.current_path:
            return None

        # Move to next node in path
        if len(self.current_path) >= 2:
            self.current_pos = self.current_path[1]
            self.current_path.pop(0)

        # Check if we've reached the target civilian
        if self.civilians and self.current_pos == self.civilians[0]:
            rescued_civ = self.civilians.pop(0)
            self.visited.append(rescued_civ)
            self.log.append(f"CIVILIAN REACHED at node {self.graph.nodes[self.current_pos].label}")

            # F33: Structured event callback
            if self.on_civilian_rescued:
                self.on_civilian_rescued(rescued_civ)

            # F34: Record response time (in simulation steps)
            assigned_step = self._civilian_assigned_step.get(rescued_civ, 0)
            response_steps = self._current_step - assigned_step
            self.on_response_time_recorded = getattr(self, 'on_response_time_recorded', None)
            if self.on_response_time_recorded:
                self.on_response_time_recorded(float(response_steps))

            self._plan_next_leg()

        return self.current_pos

    def to_dict(self) -> dict:
        """Serialize router state for API / frontend. F37: includes mission endpoints."""
        return {
            "current_pos": self.current_pos,
            "current_path": self.current_path,
            "civilians_remaining": self.civilians,
            "civilians_deferred": self.deferred,   # F11: exposed
            "civilians_rescued": self.visited,
            "total_reroutes": self.total_reroutes,
            "mission_start_id": self.mission_start_id,    # F37
            "mission_target_id": self.mission_target_id,  # F37
        }


def create_router(graph: CityGraph) -> AStarRouter:
    """Create and return an A* router bound to the shared graph."""
    return AStarRouter(graph)
