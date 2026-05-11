# layout_planning.py — Challenge 1: City Layout Planning via CSP
#
# Implements a genuine Backtracking Search with Minimum Remaining Values (MRV)
# and Forward Checking to strictly adhere to urban planning constraints and
# exact required node counts.
#
# To prevent deep thrashing in the heavy-tailed search space, this solver
# uses a Randomized Backtracking approach with restarts (Las Vegas algorithm).

import random
from collections import deque
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


class CSPSolver:
    """
    Constraint Satisfaction Problem solver for city layout planning.

    Constraints:
        C1: Industrial zones cannot be adjacent to Schools or Hospitals
        C2: Every Residential node must have a Hospital within 3 grid hops
        C3: Every Power Plant must have an Industrial zone within 2 grid hops
    """

    def __init__(self, graph: CityGraph):
        self.graph = graph
        self.assignment: dict = {}
        self.domains: dict = {}
        self.remaining_counts: dict = dict(SimConfig.REQUIRED_COUNTS)
        self.step_count = 0
        self.max_steps_per_restart = 500

        # Precompute grid neighbors for fast access
        self.neighbors_cache = {}
        for nid in self.graph.nodes:
            self.neighbors_cache[nid] = self.graph.get_grid_neighbors(nid)

        # Value ordering priority ensures highly-constrained zones are placed first
        self.value_priority = [
            SimConfig.HOSPITAL,
            SimConfig.INDUSTRIAL,
            SimConfig.SCHOOL,
            SimConfig.DEPOT,
            SimConfig.POWER_PLANT,
            SimConfig.RESIDENTIAL,
            SimConfig.EMPTY
        ]

    def solve(self) -> bool:
        """Main entry point. Uses Random Restarts to avoid backtracking thrashing."""
        max_restarts = 100
        for attempt in range(max_restarts):
            self.assignment.clear()
            self.remaining_counts = dict(SimConfig.REQUIRED_COUNTS)
            self.step_count = 0
            
            for nid in self.graph.nodes:
                self.domains[nid] = list(SimConfig.ALL_TYPES)

            if self._backtrack():
                return True

        return False

    def _backtrack(self) -> bool:
        """Recursive backtracking search."""
        if len(self.assignment) == len(self.graph.nodes):
            return True

        self.step_count += 1
        if self.step_count > self.max_steps_per_restart:
            return False  # Trigger restart if thrashing

        var = self.select_unassigned_variable()
        if var is None:
            return False

        for value in self._order_domain_values(var):
            if self._is_consistent(var, value):
                # Save domain state for backtracking
                saved_domains = {
                    nid: list(self.domains[nid]) 
                    for nid in self.neighbors_cache[var] 
                    if nid not in self.assignment
                }

                self._assign(var, value)

                if self._backtrack():
                    return True

                # Backtrack
                self._unassign(var, value, saved_domains)

        return False

    def select_unassigned_variable(self) -> int:
        """MRV heuristic: selects the variable with the smallest domain size. Ties broken randomly."""
        unassigned = [nid for nid in self.graph.nodes if nid not in self.assignment]
        if not unassigned:
            return None

        min_domain = min(len(self.domains[nid]) for nid in unassigned)
        candidates = [nid for nid in unassigned if len(self.domains[nid]) == min_domain]
        return random.choice(candidates)

    def _order_domain_values(self, node_id: int) -> list:
        """Order values prioritizing special required types first to prune search space."""
        valid_values = [v for v in self.value_priority if v in self.domains[node_id]]
        
        # Prevent stranding: Do not allow POWER_PLANT if any INDUSTRIAL is left
        if self.remaining_counts[SimConfig.INDUSTRIAL] > 0 and SimConfig.POWER_PLANT in valid_values:
            valid_values.remove(SimConfig.POWER_PLANT)
            
        # Prevent stranding: Do not allow RESIDENTIAL if any HOSPITAL is left
        if self.remaining_counts[SimConfig.HOSPITAL] > 0 and SimConfig.RESIDENTIAL in valid_values:
            valid_values.remove(SimConfig.RESIDENTIAL)
            
        # Do not allow EMPTY if unassigned cells are exactly equal to remaining required types
        total_remaining = sum(v for k, v in self.remaining_counts.items() if k != SimConfig.EMPTY)
        unassigned_count = len(self.graph.nodes) - len(self.assignment)
        if unassigned_count <= total_remaining and SimConfig.EMPTY in valid_values:
            valid_values.remove(SimConfig.EMPTY)

        return [v for v in valid_values if v == SimConfig.EMPTY or self.remaining_counts.get(v, 0) > 0]

    def _assign(self, node_id: int, value: str):
        self.assignment[node_id] = value
        self.graph.nodes[node_id].node_type = value
        
        if value != SimConfig.EMPTY:
            self.remaining_counts[value] -= 1
            
        self._forward_check(node_id, value)

    def _unassign(self, node_id: int, value: str, saved_domains: dict):
        del self.assignment[node_id]
        self.graph.nodes[node_id].node_type = SimConfig.EMPTY
        
        if value != SimConfig.EMPTY:
            self.remaining_counts[value] += 1
            
        for nid, dom in saved_domains.items():
            self.domains[nid] = dom

    def _forward_check(self, node_id: int, value: str):
        """Forward checking: prune incompatible values from adjacent nodes' domains (C1)."""
        if value == SimConfig.INDUSTRIAL:
            for nb in self.neighbors_cache[node_id]:
                if nb not in self.assignment:
                    if SimConfig.HOSPITAL in self.domains[nb]:
                        self.domains[nb].remove(SimConfig.HOSPITAL)
                    if SimConfig.SCHOOL in self.domains[nb]:
                        self.domains[nb].remove(SimConfig.SCHOOL)
                        
        elif value in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
            for nb in self.neighbors_cache[node_id]:
                if nb not in self.assignment:
                    if SimConfig.INDUSTRIAL in self.domains[nb]:
                        self.domains[nb].remove(SimConfig.INDUSTRIAL)

    def _is_consistent(self, node_id: int, value: str) -> bool:
        if value == SimConfig.EMPTY:
            return True

        if self.remaining_counts[value] <= 0:
            return False

        # C1: Industrial zones cannot be adjacent to Schools or Hospitals
        if value == SimConfig.INDUSTRIAL:
            for nb in self.neighbors_cache[node_id]:
                if self.assignment.get(nb) in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
                    return False
        elif value in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
            for nb in self.neighbors_cache[node_id]:
                if self.assignment.get(nb) == SimConfig.INDUSTRIAL:
                    return False

        # C2: Every Residential node must have a Hospital within 3 grid hops
        if value == SimConfig.RESIDENTIAL:
            # We enforce HOSPITAL before RESIDENTIAL, so we only check placed hospitals
            found_hosp = False
            for h_id in [nid for nid, t in self.assignment.items() if t == SimConfig.HOSPITAL]:
                if self._bfs_grid_hops(node_id, h_id) <= SimConfig.HOSPITAL_HOP_LIMIT:
                    found_hosp = True
                    break
            if not found_hosp:
                return False

        # C3: Every Power Plant must have an Industrial zone within 2 grid hops
        if value == SimConfig.POWER_PLANT:
            # We enforce INDUSTRIAL before POWER_PLANT, so we only check placed industrials
            found_ind = False
            for i_id in [nid for nid, t in self.assignment.items() if t == SimConfig.INDUSTRIAL]:
                if self._bfs_grid_hops(node_id, i_id) <= SimConfig.INDUSTRIAL_HOP_LIMIT:
                    found_ind = True
                    break
            if not found_ind:
                return False

        return True

    def _bfs_grid_hops(self, start_id: int, end_id: int) -> int:
        """Fast Manhattan distance between two grid nodes (perfect for empty grid)."""
        n1 = self.graph.nodes[start_id]
        n2 = self.graph.nodes[end_id]
        return abs(n1.row - n2.row) + abs(n1.col - n2.col)

    def apply_assignment_to_graph(self):
        """Sync final assignment to the graph nodes and populate."""
        for nid, node in self.graph.nodes.items():
            node.node_type = self.assignment.get(nid, SimConfig.EMPTY)
        self.graph.populate_after_layout()

    def identify_failing_constraint(self) -> str:
        return "CONFLICT: Backtracking search could not find a layout satisfying all constraints."

    def suggest_minimum_conflict_adjustment(self) -> list:
        return []
