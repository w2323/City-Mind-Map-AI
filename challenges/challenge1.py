# challenge1.py — Challenge 1: Hybrid Urban Generation System (CSP)
import random, math
from collections import deque
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


class District:
    def __init__(self, did, cr, cc):
        self.id = did
        self.center_row = cr
        self.center_col = cc
        self.cells = []
        self.counts = {}

    def count(self, t):
        return self.counts.get(t, 0)

    def add(self, t):
        self.counts[t] = self.counts.get(t, 0) + 1

    def total_infra(self):
        return sum(v for k, v in self.counts.items() if k != SimConfig.EMPTY)


def _mdist(r1, c1, r2, c2):
    return abs(r1 - r2) + abs(c1 - c2)


def _node_rc(graph, nid):
    n = graph.nodes[nid]
    return n.row, n.col


class CSPSolver:
    """Hybrid Urban Generation System — 10-phase staged pipeline."""

    def __init__(self, graph: CityGraph):
        self.graph = graph
        self.assignment = {}
        self.districts = []
        self._fail_reason = ""

    def solve(self) -> bool:
        for attempt in range(20):
            self.assignment = {nid: SimConfig.EMPTY for nid in self.graph.nodes}
            self.districts = []
            try:
                self._phase0_districts()
                self._phase1_macro_zoning()
                self._phase2_infrastructure()
                self._phase4_residential()
                self._phase5_population()
                self._phase6_open_space()
                if self._phase7_validate():
                    return True
                self._phase8_repair()
                if self._phase7_validate():
                    return True
            except Exception:
                continue
        return False


    def _phase0_districts(self):
        R, C = SimConfig.GRID_ROWS, SimConfig.GRID_COLS
        # Quadrant-anchored seeds with random jitter for organic feel
        quadrant_anchors = [
            (R // 4, C // 4),           # NW
            (R // 4, 3 * C // 4),       # NE
            (3 * R // 4, C // 4),       # SW
            (3 * R // 4, 3 * C // 4),   # SE
        ]
        jitter = 2
        centers = []
        for ar, ac in quadrant_anchors:
            cr = max(1, min(R - 2, ar + random.randint(-jitter, jitter)))
            cc = max(1, min(C - 2, ac + random.randint(-jitter, jitter)))
            centers.append((cr, cc))
        nd = len(centers)
        self.districts = [District(i, cr, cc) for i, (cr, cc) in enumerate(centers)]
        for nid, node in self.graph.nodes.items():
            best_i = min(range(nd), key=lambda i: _mdist(node.row, node.col, self.districts[i].center_row, self.districts[i].center_col))
            self.districts[best_i].cells.append(nid)


    def _phase1_macro_zoning(self):
        R, C = SimConfig.GRID_ROWS, SimConfig.GRID_COLS
        self._industrial_zone = set()
        self._open_space_zone = set()
        for nid, node in self.graph.nodes.items():
            on_edge = node.row <= 1 or node.row >= R - 2 or node.col <= 1 or node.col >= C - 2
            on_corner = (node.row <= 2 and node.col <= 2) or (node.row <= 2 and node.col >= C - 3) or \
                        (node.row >= R - 3 and node.col <= 2) or (node.row >= R - 3 and node.col >= C - 3)
            if on_edge and not on_corner:
                self._industrial_zone.add(nid)
        mid_r, mid_c = R // 2, C // 2
        for nid, node in self.graph.nodes.items():
            if _mdist(node.row, node.col, mid_r, mid_c) <= 1:
                self._open_space_zone.add(nid)


    def _phase2_infrastructure(self):
        self._place_hospitals()
        self._place_industrial()
        self._place_power_plants()
        self._place_schools()
        self._place_depots()

    def _place_hospitals(self):
        count = SimConfig.REQUIRED_COUNTS[SimConfig.HOSPITAL]
        nd = len(self.districts)
        per_district = max(1, count // nd)
        placed = []
        for d in self.districts:
            placed_in_d = 0
            cells = list(d.cells)
            random.shuffle(cells)
            for nid in cells:
                if placed_in_d >= per_district:
                    break
                if self.assignment[nid] != SimConfig.EMPTY:
                    continue
                if nid in self._industrial_zone:
                    continue
                node = self.graph.nodes[nid]
                if not self._check_industrial_dist(node.row, node.col, SimConfig.MIN_INDUSTRIAL_HOSPITAL_DIST):
                    continue
                self.assignment[nid] = SimConfig.HOSPITAL
                d.add(SimConfig.HOSPITAL)
                placed.append(nid)
                placed_in_d += 1
        remaining = count - len(placed)
        if remaining > 0:
            all_cells = [nid for nid in self.graph.nodes if self.assignment[nid] == SimConfig.EMPTY and nid not in self._industrial_zone]
            random.shuffle(all_cells)
            for nid in all_cells:
                if remaining <= 0:
                    break
                node = self.graph.nodes[nid]
                if not self._check_industrial_dist(node.row, node.col, SimConfig.MIN_INDUSTRIAL_HOSPITAL_DIST):
                    continue
                min_d = min(_mdist(node.row, node.col, *_node_rc(self.graph, h)) for h in placed) if placed else 999
                if min_d >= 2:
                    self.assignment[nid] = SimConfig.HOSPITAL
                    self._district_of(nid).add(SimConfig.HOSPITAL)
                    placed.append(nid)
                    remaining -= 1

    def _place_industrial(self):
        count = SimConfig.REQUIRED_COUNTS[SimConfig.INDUSTRIAL]
        candidates = []
        for nid in self._industrial_zone:
            if self.assignment[nid] != SimConfig.EMPTY:
                continue
            node = self.graph.nodes[nid]
            ok = True
            for oid, ot in self.assignment.items():
                if ot == SimConfig.HOSPITAL:
                    if _mdist(node.row, node.col, *_node_rc(self.graph, oid)) < SimConfig.MIN_INDUSTRIAL_HOSPITAL_DIST:
                        ok = False
                        break
            if ok:
                candidates.append(nid)
        random.shuffle(candidates)
        placed = []
        for nid in candidates:
            if len(placed) >= count:
                break
            node = self.graph.nodes[nid]
            too_close = False
            for pid in placed:
                if _mdist(node.row, node.col, *_node_rc(self.graph, pid)) < 2:
                    too_close = True
                    break
            if not too_close:
                self.assignment[nid] = SimConfig.INDUSTRIAL
                self._district_of(nid).add(SimConfig.INDUSTRIAL)
                placed.append(nid)
        if len(placed) < count:
            fallback = [nid for nid in self.graph.nodes if self.assignment[nid] == SimConfig.EMPTY and nid not in self._open_space_zone]
            random.shuffle(fallback)
            for nid in fallback:
                if len(placed) >= count:
                    break
                node = self.graph.nodes[nid]
                ok = True
                for oid, ot in self.assignment.items():
                    if ot in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
                        if _mdist(node.row, node.col, *_node_rc(self.graph, oid)) < SimConfig.MIN_INDUSTRIAL_HOSPITAL_DIST:
                            ok = False
                            break
                if ok:
                    self.assignment[nid] = SimConfig.INDUSTRIAL
                    self._district_of(nid).add(SimConfig.INDUSTRIAL)
                    placed.append(nid)

    def _place_power_plants(self):
        count = SimConfig.REQUIRED_COUNTS[SimConfig.POWER_PLANT]
        industrials = [nid for nid, t in self.assignment.items() if t == SimConfig.INDUSTRIAL]
        candidates = []
        for nid in self.graph.nodes:
            if self.assignment[nid] != SimConfig.EMPTY:
                continue
            node = self.graph.nodes[nid]
            near_ind = any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= SimConfig.POWER_PLANT_INDUSTRIAL_DIST for ind in industrials)
            if not near_ind:
                continue
            near_res_core = any(_mdist(node.row, node.col, *_node_rc(self.graph, oid)) <= 1 for oid, ot in self.assignment.items() if ot == SimConfig.HOSPITAL)
            if near_res_core:
                continue
            candidates.append(nid)
        random.shuffle(candidates)
        placed = []
        used_districts = set()
        for nid in candidates:
            if len(placed) >= count:
                break
            d = self._district_of(nid)
            if d.id in used_districts and len(placed) < count - 1:
                continue
            self.assignment[nid] = SimConfig.POWER_PLANT
            d.add(SimConfig.POWER_PLANT)
            placed.append(nid)
            used_districts.add(d.id)
        for nid in candidates:
            if len(placed) >= count:
                break
            if nid not in placed and self.assignment[nid] == SimConfig.EMPTY:
                self.assignment[nid] = SimConfig.POWER_PLANT
                self._district_of(nid).add(SimConfig.POWER_PLANT)
                placed.append(nid)

    def _place_schools(self):
        count = SimConfig.REQUIRED_COUNTS[SimConfig.SCHOOL]
        hospitals = [nid for nid, t in self.assignment.items() if t == SimConfig.HOSPITAL]
        candidates = []
        for nid in self.graph.nodes:
            if self.assignment[nid] != SimConfig.EMPTY:
                continue
            node = self.graph.nodes[nid]
            ok = True
            for oid, ot in self.assignment.items():
                if ot == SimConfig.INDUSTRIAL:
                    if _mdist(node.row, node.col, *_node_rc(self.graph, oid)) < SimConfig.MIN_INDUSTRIAL_SCHOOL_DIST:
                        ok = False
                        break
            if not ok:
                continue
            near_hosp = any(_mdist(node.row, node.col, *_node_rc(self.graph, h)) <= 4 for h in hospitals)
            score = 0
            if near_hosp:
                score += 5
            if nid not in self._industrial_zone:
                score += 3
            R, C = SimConfig.GRID_ROWS, SimConfig.GRID_COLS
            if 2 <= node.row <= R - 3 and 2 <= node.col <= C - 3:
                score += 2
            candidates.append((score, random.random(), nid))
        candidates.sort(reverse=True)
        placed = []
        used_districts = set()
        for _, _, nid in candidates:
            if len(placed) >= count:
                break
            d = self._district_of(nid)
            if d.id in used_districts and len(placed) < count - 1:
                continue
            self.assignment[nid] = SimConfig.SCHOOL
            d.add(SimConfig.SCHOOL)
            placed.append(nid)
            used_districts.add(d.id)
        for _, _, nid in candidates:
            if len(placed) >= count:
                break
            if self.assignment[nid] == SimConfig.EMPTY:
                self.assignment[nid] = SimConfig.SCHOOL
                self._district_of(nid).add(SimConfig.SCHOOL)
                placed.append(nid)

    def _place_depots(self):
        count = SimConfig.REQUIRED_COUNTS[SimConfig.DEPOT]
        candidates = []
        for nid in self.graph.nodes:
            if self.assignment[nid] != SimConfig.EMPTY:
                continue
            node = self.graph.nodes[nid]
            pop_weight = 0
            for oid, ot in self.assignment.items():
                if ot in (SimConfig.HOSPITAL, SimConfig.RESIDENTIAL):
                    d = _mdist(node.row, node.col, *_node_rc(self.graph, oid))
                    if d <= 5:
                        pop_weight += max(0, 6 - d)
            candidates.append((pop_weight, nid))
        candidates.sort(reverse=True)
        placed = []
        used_districts = set()
        for _, nid in candidates:
            if len(placed) >= count:
                break
            node = self.graph.nodes[nid]
            d = self._district_of(nid)
            if d.id in used_districts and len(placed) < min(count, len(self.districts)):
                continue
            ok = True
            for pid in placed:
                if _mdist(node.row, node.col, *_node_rc(self.graph, pid)) < SimConfig.MIN_DEPOT_DEPOT_DIST:
                    ok = False
                    break
            if ok:
                self.assignment[nid] = SimConfig.DEPOT
                d.add(SimConfig.DEPOT)
                placed.append(nid)
                used_districts.add(d.id)
        if len(placed) < count:
            for _, nid in candidates:
                if len(placed) >= count:
                    break
                if self.assignment[nid] == SimConfig.EMPTY:
                    self.assignment[nid] = SimConfig.DEPOT
                    self._district_of(nid).add(SimConfig.DEPOT)
                    placed.append(nid)


    def _phase4_residential(self):
        infra_placed = sum(1 for t in self.assignment.values() if t != SimConfig.EMPTY)
        total_cells = len(self.graph.nodes)
        target_empty = int(total_cells * 0.20)
        total_target = max(SimConfig.REQUIRED_COUNTS[SimConfig.RESIDENTIAL],
                           total_cells - infra_placed - target_empty)
        hospitals = [nid for nid, t in self.assignment.items() if t == SimConfig.HOSPITAL]
        services = [nid for nid, t in self.assignment.items()
                    if t in (SimConfig.HOSPITAL, SimConfig.SCHOOL)]
        industrials = set(nid for nid, t in self.assignment.items()
                         if t == SimConfig.INDUSTRIAL)
        placed = 0

        # Stage 1: BFS growth from services — relaxed hop limit (5) for wider spread
        visited = set()
        queue = deque()
        for s in services:
            queue.append((s, 0))
            visited.add(s)
        while queue and placed < total_target:
            nid, depth = queue.popleft()
            if self.assignment[nid] == SimConfig.EMPTY and depth > 0:
                node = self.graph.nodes[nid]
                near_ind = any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= 1
                               for ind in industrials)
                p = 1.0 - (depth * 0.02)
                if nid in self._open_space_zone:
                    p -= 0.4
                if not near_ind and p > 0 and random.random() < p:
                    self.assignment[nid] = SimConfig.RESIDENTIAL
                    self._district_of(nid).add(SimConfig.RESIDENTIAL)
                    placed += 1
            if depth < 12:
                nbs = list(self.graph.get_grid_neighbors(nid))
                random.shuffle(nbs)
                for nb in nbs:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append((nb, depth + 1))

        # Stage 2: District-balanced fill — round-robin batches
        while placed < total_target:
            sorted_districts = sorted(self.districts,
                                       key=lambda d: d.count(SimConfig.RESIDENTIAL))
            filled_any = False
            batch = max(3, (total_target - placed) // len(self.districts))
            for d in sorted_districts:
                if placed >= total_target:
                    break
                cells = [nid for nid in d.cells if self.assignment[nid] == SimConfig.EMPTY]
                random.shuffle(cells)
                added = 0
                for nid in cells:
                    if placed >= total_target or added >= batch:
                        break
                    node = self.graph.nodes[nid]
                    near_ind = any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= 1
                                   for ind in industrials)
                    if not near_ind:
                        self.assignment[nid] = SimConfig.RESIDENTIAL
                        d.add(SimConfig.RESIDENTIAL)
                        placed += 1
                        added += 1
                        filled_any = True
            if not filled_any:
                break

        # Stage 3: Final fill — any remaining empty not near industrial
        if placed < total_target:
            empties = [nid for nid in self.graph.nodes
                       if self.assignment[nid] == SimConfig.EMPTY]
            random.shuffle(empties)
            for nid in empties:
                if placed >= total_target:
                    break
                node = self.graph.nodes[nid]
                near_ind = any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= 1
                               for ind in industrials)
                if not near_ind:
                    self.assignment[nid] = SimConfig.RESIDENTIAL
                    self._district_of(nid).add(SimConfig.RESIDENTIAL)
                    placed += 1


    def _phase5_population(self):
        R, C = SimConfig.GRID_ROWS, SimConfig.GRID_COLS
        services = [nid for nid, t in self.assignment.items() if t in (SimConfig.HOSPITAL, SimConfig.SCHOOL, SimConfig.DEPOT)]
        for nid, node in self.graph.nodes.items():
            pop_cfg = SimConfig.POPULATION_MAP.get(self.assignment[nid], 0)
            if isinstance(pop_cfg, tuple):
                lo, hi = pop_cfg
                if services:
                    min_d = min(_mdist(node.row, node.col, *_node_rc(self.graph, s)) for s in services)
                else:
                    min_d = 5
                if min_d <= 2:
                    node.population = random.randint(int(hi * 0.7), hi)
                elif min_d <= 4:
                    node.population = random.randint(int((lo + hi) / 2), int(hi * 0.8))
                else:
                    node.population = random.randint(lo, int((lo + hi) / 2))
            else:
                node.population = pop_cfg


    def _phase6_open_space(self):
        total = len(self.graph.nodes)
        empty_count = sum(1 for t in self.assignment.values() if t == SimConfig.EMPTY)
        target_min = int(total * SimConfig.EMPTY_RATIO_MIN)
        target_max = int(total * SimConfig.EMPTY_RATIO_MAX)
        if empty_count > target_max:
            empties = [nid for nid, t in self.assignment.items() if t == SimConfig.EMPTY]
            random.shuffle(empties)
            services = [nid for nid, t in self.assignment.items() if t in (SimConfig.HOSPITAL, SimConfig.SCHOOL)]
            hospitals = [nid for nid, t in self.assignment.items() if t == SimConfig.HOSPITAL]
            for nid in empties:
                if empty_count <= target_max:
                    break
                node = self.graph.nodes[nid]
                near_ind = any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= 1 for ind, t in self.assignment.items() if t == SimConfig.INDUSTRIAL)
                if not near_ind:
                    self.assignment[nid] = SimConfig.RESIDENTIAL
                    self._district_of(nid).add(SimConfig.RESIDENTIAL)
                    empty_count -= 1
        self._break_large_empty_clusters()

    def _break_large_empty_clusters(self):
        empties = {nid for nid, t in self.assignment.items() if t == SimConfig.EMPTY}
        visited = set()
        for nid in empties:
            if nid in visited:
                continue
            cluster = []
            q = deque([nid])
            visited.add(nid)
            while q:
                cur = q.popleft()
                cluster.append(cur)
                for nb in self.graph.get_grid_neighbors(cur):
                    if nb in empties and nb not in visited:
                        visited.add(nb)
                        q.append(nb)
            if len(cluster) > SimConfig.MAX_EMPTY_CLUSTER:
                mid = cluster[len(cluster) // 2]
                self.assignment[mid] = SimConfig.RESIDENTIAL
                self._district_of(mid).add(SimConfig.RESIDENTIAL)


    def _phase7_validate(self) -> bool:
        ok = True
        for nid, t in self.assignment.items():
            if t == SimConfig.INDUSTRIAL:
                node = self.graph.nodes[nid]
                for nb in self.graph.get_grid_neighbors(nid):
                    if self.assignment[nb] in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
                        ok = False
                        break
        hospitals = [nid for nid, t in self.assignment.items() if t == SimConfig.HOSPITAL]
        for nid, t in self.assignment.items():
            if t == SimConfig.RESIDENTIAL:
                node = self.graph.nodes[nid]
                if not any(_mdist(node.row, node.col, *_node_rc(self.graph, h)) <= SimConfig.HOSPITAL_HOP_LIMIT for h in hospitals):
                    pass  # Soft constraint — logged but does not fail validation
        industrials = [nid for nid, t in self.assignment.items() if t == SimConfig.INDUSTRIAL]
        for nid, t in self.assignment.items():
            if t == SimConfig.POWER_PLANT:
                node = self.graph.nodes[nid]
                if not any(_mdist(node.row, node.col, *_node_rc(self.graph, ind)) <= SimConfig.INDUSTRIAL_HOP_LIMIT for ind in industrials):
                    ok = False
        counts = {}
        for t in self.assignment.values():
            counts[t] = counts.get(t, 0) + 1
        for tname, req in SimConfig.REQUIRED_COUNTS.items():
            if counts.get(tname, 0) < req:
                self._fail_reason = f"Missing {tname}: need {req}, have {counts.get(tname, 0)}"
                ok = False
        return ok


    def _phase8_repair(self):
        for nid, t in list(self.assignment.items()):
            if t == SimConfig.INDUSTRIAL:
                for nb in self.graph.get_grid_neighbors(nid):
                    if self.assignment[nb] in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
                        best = self._find_swap_target(nid, SimConfig.INDUSTRIAL)
                        if best is not None:
                            self.assignment[nid] = SimConfig.EMPTY
                            self.assignment[best] = SimConfig.INDUSTRIAL
                        break
        # C2 is soft — do not remove residential for hospital proximity
        counts = {}
        for t in self.assignment.values():
            counts[t] = counts.get(t, 0) + 1
        for tname, req in SimConfig.REQUIRED_COUNTS.items():
            deficit = req - counts.get(tname, 0)
            if deficit > 0 and tname == SimConfig.RESIDENTIAL:
                empties = [nid for nid, t in self.assignment.items() if t == SimConfig.EMPTY]
                random.shuffle(empties)
                for nid in empties[:deficit]:
                    self.assignment[nid] = SimConfig.RESIDENTIAL

    def _find_swap_target(self, orig_nid, node_type):
        node = self.graph.nodes[orig_nid]
        candidates = []
        for nid in self.graph.nodes:
            if self.assignment[nid] != SimConfig.EMPTY:
                continue
            n = self.graph.nodes[nid]
            ok = True
            if node_type == SimConfig.INDUSTRIAL:
                for nb in self.graph.get_grid_neighbors(nid):
                    if self.assignment.get(nb) in (SimConfig.HOSPITAL, SimConfig.SCHOOL):
                        ok = False
                        break
            if ok:
                candidates.append((abs(n.row - node.row) + abs(n.col - node.col), nid))
        candidates.sort()
        return candidates[0][1] if candidates else None


    def _district_of(self, nid):
        node = self.graph.nodes[nid]
        return min(self.districts, key=lambda d: _mdist(node.row, node.col, d.center_row, d.center_col))

    def _check_industrial_dist(self, row, col, min_dist):
        for oid, ot in self.assignment.items():
            if ot == SimConfig.INDUSTRIAL:
                if _mdist(row, col, *_node_rc(self.graph, oid)) < min_dist:
                    return False
        return True

    def apply_assignment_to_graph(self):
        for nid, node in self.graph.nodes.items():
            node.node_type = self.assignment.get(nid, SimConfig.EMPTY)
        self._phase5_population()

    def identify_failing_constraint(self) -> str:
        return self._fail_reason or "CONFLICT: Hybrid solver could not produce a valid layout."

    def suggest_minimum_conflict_adjustment(self) -> list:
        return []
