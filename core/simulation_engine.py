# simulation_engine.py — CityMind Simulation Engine
# Contains SimulationState (single source of truth) and Simulation runner.
# No GUI dependencies. Fully terminal-runnable.
#
# FIXES APPLIED:
# F3  — Ambulance list is deployment positions; router current_pos is separate rescue team
# F6  — trigger_flood_at_node no longer advances simulation step (that was a side effect)
# F7  — trigger_flood_at_node counts 1 flood event per node, not per edge
# F13 — step_forward() sets is_complete when step >= max_steps
# F32 — trigger_flood_at_node uses batch block to trigger single replan
# F33 — Structured callbacks replace log string parsing for metrics
# F34 — Response times recorded via structured callbacks
# F35 — disconnected_nodes metric refreshed every step
# F36 — mission_status field added to SimulationState
# F40 — sim_id (generation counter) added to state
# F43 — Seed handling: seed=0 is now valid (uses "is not None" check)
# F2  — risk_reeval calls graph.update_risk which now notifies router via observers

import random
import time
import threading
import uuid
from core.city_graph import CityGraph
from core.event_manager import EventManager, EventType
from config.simulation_config import SimConfig


# ──────────────────────────────────────────────────────────
# SimulationState — Single Source of Truth
# This is what gets serialized for API/frontend consumption.
# ──────────────────────────────────────────────────────────
class SimulationState:
    """
    Centralized simulation state. Contains everything needed to
    describe the current state of the simulation.

    This is the SINGLE SOURCE OF TRUTH — not just CityGraph.
    All modules read from and write to this state object.

    Designed for future serialization to:
        - FastAPI endpoints
        - WebSocket real-time updates
        - React frontend state
        - Replay systems
    """

    def __init__(self, graph: CityGraph, events: EventManager):
        self.graph: CityGraph = graph
        self.events: EventManager = events
        self.step: int = 0
        self.max_steps: int = SimConfig.MAX_STEPS
        self.ambulances: list = []           # Live fleet positions; legacy deployments when no fleet exists
        self.civilians: list = []            # Active civilian node IDs
        self.flood_history: list = []        # (step, id_a, id_b) tuples (edge-level history)
        self.flood_event_history: list = []  # (step, node_id_or_edge) flood EVENTS (F7: event-level)
        self.risk_predictions: dict = {}     # node_id -> risk_level
        self.active_routes: list = []        # Current planned route path (remaining path)
        self.police_deployments: list = []   # [(node_id, risk_level, score)] for 10 officers
        self.fleet = None
        self.medical_network = None
        self.air_rescue = None
        self.police = None
        self.city_events = None
        from core.disasters import DisasterManager
        self.disasters = DisasterManager(graph, events)
        self.optimized_placements = []
        self.router = None                   # AStarRouter instance
        self.is_initialized: bool = False
        self.is_complete: bool = False

        # F36: Explicit mission status
        # Values: "NOT_STARTED", "IN_PROGRESS", "ALL_RESCUED", "PARTIAL", "FAILED"
        self.mission_status: str = "NOT_STARTED"

        # F40: Simulation identity — generation counter to detect resets
        self.sim_id: str = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        """
        Serialize the complete simulation state for API consumption.
        """
        from core.analytics import analyze
        if self.police and self.police.dynamic_crime:
            self.risk_predictions={n.id:n.risk_level for n in self.graph.nodes.values()}
            for level in ('HIGH','MEDIUM','LOW'):
                setattr(self.events.metrics,level.lower()+'_risk_zones',sum(n.risk_level==level for n in self.graph.nodes.values()))
        if self.medical_network:
            self.medical_network.refresh()
        if self.police:
            self.police_deployments = [(u['position'],self.graph.nodes[u['position']].risk_level,
                                        SimConfig.POLICE_RISK_WEIGHTS.get(self.graph.nodes[u['position']].risk_level,1))
                                       for u in self.police.units]
        self.events.metrics.total_edges_active = self.graph.count_active_edges()
        self.events.metrics.total_edges_blocked = self.graph.count_blocked_edges()
        self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())
        if self.router and self.fleet is None:
            self.active_routes = list(self.router.current_path)
            self.civilians = list(self.router.civilians)
            self.events.metrics.civilians_unreachable = len(self.router.deferred)
            if self.router.civilians:
                self.mission_status = "IN_PROGRESS"
            elif self.router.deferred:
                self.mission_status = "PARTIAL" if self.router.visited else "FAILED"
            else:
                self.mission_status = "ALL_RESCUED"
        if self.fleet is not None:
            self.ambulances = [u['position'] for u in self.fleet.units]
            view = self.fleet.compatibility_router()
            self.active_routes = view['current_path']
            self.civilians = view['civilians_remaining']
            if self.civilians:
                self.mission_status = 'PARTIAL' if self.is_complete else 'IN_PROGRESS'
            elif view['civilians_deferred']:
                self.mission_status = 'PARTIAL'
            else:
                self.mission_status = 'ALL_RESCUED' if self.fleet.emergencies else 'IDLE'
        result = {
            'city_events': self.city_events.to_dict() if self.city_events else {},
            "crime_heatmap": {'label':'Crime opportunity and reported incidents','simulation_assumptions':True,
                              'scale':'0–100 scenario score, not a crime probability',
                              'dense_residential_rule':'Low baseline unless inside a reported crime area',
                              'report_radius':SimConfig.CRIME_REPORT_RADIUS,'radius_unit':'Euclidean grid cells',
                              'bank_hospital_min_blocks':SimConfig.BANK_HOSPITAL_MIN_BLOCKS},
            "police": self.police.to_dict(self.step) if self.police else {},
            "disasters": self.disasters.to_dict(),
            "medical_network": self.medical_network.to_dict() if self.medical_network else {},
            "air_rescue": self.air_rescue.to_dict() if self.air_rescue else {},
            "dispatch_summary": self.fleet.summary() if self.fleet else {},
            "fleet": self.fleet.to_dict() if self.fleet else [],
            "emergencies": self.fleet.emergencies if self.fleet else [],
            "optimized_placements": self.optimized_placements,
            "analysis": analyze(self),
            "step": self.step,
            "max_steps": self.max_steps,
            "is_initialized": self.is_initialized,
            "is_complete": self.is_complete,
            "mission_status": self.mission_status,    # F36
            "sim_id": self.sim_id,                    # F40
            "graph": self.graph.to_dict(),
            "ambulances": self.ambulances,
            # NOTE (F3): ambulances list shows deployment positions, NOT the active rescue team.
            # The active rescue team position is in router.current_pos.
            "civilians_remaining": self.civilians,
            "flood_history": [
                {"step": s, "node_a": a, "node_b": b}
                for s, a, b in self.flood_history
            ],
            "flood_events": [
                {"step": s, "target": t, "edges_blocked": c}
                for s, t, c in self.flood_event_history
            ],
            "risk_predictions": self.risk_predictions,
            "active_routes": self.active_routes,
            "police_deployments": [
                {"node_id": nid, "risk_level": rl, "priority_score": sc}
                for nid, rl, sc in self.police_deployments
            ],
            "events": self.events.to_dict(),
        }
        if self.router:
            result["router"] = self.fleet.compatibility_router() if self.fleet else self.router.to_dict()
        return result


# ──────────────────────────────────────────────────────────
# Simulation — the main simulation runner
# ──────────────────────────────────────────────────────────
class Simulation:
    """Shared Python city model.

    Initialization builds CSP zoning and roads, fits risk predictions, and uses
    a genetic algorithm to locate real medical centers. Each center owns an
    ambulance. Emergencies are explicitly entered by the operator.

    Road changes refresh medical reachability and facility recommendations.
    Steps move real ambulances and the fuel-budgeted helicopter. Air rescues fly
    directly to a safe hospital, then return to a separate building base.
    Later GA runs propose sites without moving physical facilities or vehicles.

    Callers serialize access with the API lock. This object is not thread-safe.
    """

    def __init__(self, seed: int = None, verbose: bool = True, automatic_events: bool = None):
        # F43 FIX: Use "is not None" to allow seed=0 as a valid seed
        self._seed = seed if seed is not None else SimConfig.SEED
        self._automatic_events = SimConfig.AUTOMATIC_CITY_EVENTS if automatic_events is None else automatic_events

        # Use a local Random instance to avoid contaminating global state
        # when multiple simulations run in the same process
        self._rng = random.Random(self._seed)

        self.events = EventManager(verbose=verbose)
        self.graph = CityGraph()
        self.state = SimulationState(self.graph, self.events)

    # ── Initialization — all 5 challenges in order ──────────

    def initialize(self):
        """
        Initialize all 5 challenge modules in dependency order.
        Raises RuntimeError if any critical step fails.
        """
        self.events.metrics.simulation_start_time = time.time()
        self.events.log(EventType.SIMULATION, "Initializing CityMind simulation...")

        # 1. Challenge 1: City layout via CSP
        self.events.log(EventType.LAYOUT, "Running CSP solver for city layout...")
        from challenges.challenge1 import CSPSolver
        solver = CSPSolver(self.graph, rng=self._rng)
        if not solver.solve():
            conflict = solver.identify_failing_constraint()
            suggestions = solver.suggest_minimum_conflict_adjustment()
            self.events.log(EventType.LAYOUT, f"LAYOUT FAILED: {conflict}", level="error")
            for s in suggestions:
                self.events.log(EventType.LAYOUT, f"  Suggestion: {s[3]}", level="warning")
            raise RuntimeError(conflict)
        solver.apply_assignment_to_graph()
        self.events.log(EventType.LAYOUT, "City layout assigned successfully via CSP.")

        # 2. Challenge 2: Road network via Kruskal's MST
        self.events.log(EventType.ROADS, "Building road network (MST + redundancy)...")
        from challenges.challenge2 import build_road_network
        build_road_network(self.graph)
        self.events.log(EventType.ROADS,
                        f"Road network built. "
                        f"{self.graph.count_active_edges()} active edges.")

        # 3. Challenge 5: Crime risk ML (run BEFORE GA so risk weights affect fitness)
        self.events.log(EventType.ML, "Preparing the existing medical-planning cost model...")
        from challenges.challenge5 import run_crime_risk_pipeline
        kmeans, dt = run_crime_risk_pipeline(self.graph, rng=self._rng)

        # Update risk predictions in state
        risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for nid, node in self.graph.nodes.items():
            self.state.risk_predictions[nid] = node.risk_level
            if node.risk_level in risk_counts:
                risk_counts[node.risk_level] += 1
        self.events.metrics.high_risk_zones = risk_counts["HIGH"]
        self.events.metrics.medium_risk_zones = risk_counts["MEDIUM"]
        self.events.metrics.low_risk_zones = risk_counts["LOW"]

        self.events.log(EventType.ML,
                        f"Medical-planning cost model ready. "
                        f"HIGH={risk_counts['HIGH']}, "
                        f"MEDIUM={risk_counts['MEDIUM']}, "
                        f"LOW={risk_counts['LOW']}")

        # Log Decision Tree rules for explainability
        self.events.log(EventType.ML,
                        f"Medical-planning decision tree:\n{dt.explain()}", level="debug")

        # Deploy 10 police officers to highest-risk zones
        from challenges.challenge5 import deploy_police_officers
        self.state.police_deployments = deploy_police_officers(self.graph) if self.state.police is None else self.state.police_deployments
        officer_nodes = [self.graph.nodes[d[0]].label for d in self.state.police_deployments]
        self.events.log(EventType.ML,
                        f"Initial planning-cost priority areas: {', '.join(officer_nodes)}")

        # Optimize actual medical-center sites across the city road network.
        from core.medical_network import MedicalCenterPlanner, MedicalNetwork
        planner = MedicalCenterPlanner(self.graph, rng=self._rng)
        centers = planner.run()
        # Move displaced zoning into vacated medical plots rather than delete it.
        old_sites = [n for n in self.graph.nodes.values() if n.node_type in (SimConfig.HOSPITAL, SimConfig.DEPOT)]
        vacated = [n for n in old_sites if n.id not in centers]
        displaced = [(self.graph.nodes[n].node_type, self.graph.nodes[n].population)
                     for n in centers if self.graph.nodes[n].node_type not in (SimConfig.HOSPITAL, SimConfig.DEPOT)]
        for node in vacated:
            node.node_type, node.population = SimConfig.EMPTY, 0
        for node, (zone, population) in zip(vacated, displaced):
            node.node_type, node.population = zone, population
        for n in centers:
            self.graph.nodes[n].node_type = SimConfig.HOSPITAL
            self.graph.nodes[n].population = SimConfig.POPULATION_MAP[SimConfig.HOSPITAL]
        # Zoning moved during facility planning; refit the displayed risk inputs
        # and police scores so they match the final city rather than old plots.
        from core.bank_placement import place_banks
        place_banks(self.graph,centers,random.Random(self._seed if self._seed is not None else self._rng.getrandbits(32)))
        self.refresh_risk()
        self.events.log(EventType.ML,'Live crime heatmap ready: bank assets, residential context and reported incidents.')
        self.state.optimized_placements = centers
        self.state.medical_network = MedicalNetwork(self.graph, centers, self.events)
        self.events.metrics.ga_best_fitness = planner.best_fitness
        self.events.log(EventType.AMBULANCE, 'GA medical centers: '+', '.join(self.graph.nodes[n].label for n in centers))

        # 5. Challenge 4: Emergency routing via A*
        self.events.log(EventType.ROUTING, "Creating A* emergency router...")
        from challenges.challenge4 import create_router
        self.state.router = create_router(self.graph)

        # F33: Set up structured callbacks on the router
        self._setup_router_callbacks()

        # Explicit dispatch: one idle ambulance at each GA-placed medical center.
        from core.ambulance_fleet import AmbulanceFleet
        self.state.fleet = AmbulanceFleet(self.graph, self.events, centers=centers)
        self.state.fleet.network = self.state.medical_network
        self.state.fleet.disasters = self.state.disasters
        from core.air_rescue import AirRescue
        self.state.air_rescue = AirRescue(self.graph, self.state.medical_network, self.state.fleet)
        from core.police_service import PoliceService
        self.state.police = PoliceService(self.graph,self.events,self.state.fleet,self.state.medical_network,
                                         self.state.air_rescue,seed=self._rng.randrange(2**32),dynamic_crime=True)
        from core.city_events import CityEvents
        self.state.city_events = CityEvents(self, self._automatic_events)
        if any(not bank['protected'] for bank in self.state.police.bank_protection()):
            raise RuntimeError('City layout cannot provide a road-accessible police station within three grid blocks of every bank')
        self.state.ambulances = [unit['position'] for unit in self.state.fleet.units]
        self.state.civilians = []
        # Retain the standalone router for diagnostics and algorithm comparison.
        self.state.router.current_pos = self.state.ambulances[0] if self.state.ambulances else None
        self.state.mission_status = 'IDLE'
        self.events.log(EventType.ROUTING, 'Medical-center fleet ready. Waiting for an operator to enter an emergency node.')

        # Update state
        self.state.is_initialized = True
        self.events.metrics.total_edges_active = self.graph.count_active_edges()
        # F35: Initial disconnected nodes count
        self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())
        self.events.log(EventType.SIMULATION,
                        "Initialization complete. All 5 challenges ready.")

    def refresh_risk(self):
        from challenges.challenge5 import deploy_police_officers
        from core.crime_heatmap import update_crime_heatmap
        update_crime_heatmap(self.graph,self.state.police.reports if self.state.police else (),self.state.step)
        self.state.risk_predictions = {n.id: n.risk_level for n in self.graph.nodes.values()}
        for level in ('HIGH', 'MEDIUM', 'LOW'):
            setattr(self.events.metrics, level.lower()+'_risk_zones',
                    sum(n.risk_level == level for n in self.graph.nodes.values()))
        self.state.police_deployments = deploy_police_officers(self.graph) if self.state.police is None else self.state.police_deployments
        if self.state.medical_network:
            self.state.medical_network.refresh()
        if self.state.fleet:
            self.state.fleet.replan()
        if self.state.police:
            self.state.police.refresh(self.state.step)

    def _setup_router_callbacks(self):
        """F33: Set up structured event callbacks on the router to replace log string parsing."""
        router = self.state.router

        def on_rescued(civilian_id: int):
            """Called when a civilian is successfully rescued."""
            self.events.metrics.civilians_rescued += 1
            self.events.log(EventType.ROUTING,
                            f"Civilian rescued (id={civilian_id}) — total rescued: "
                            f"{self.events.metrics.civilians_rescued}")

        def on_deferred(civilian_id: int):
            """Called when a civilian is deferred (unreachable — F11)."""
            self.events.metrics.civilians_unreachable += 1
            self.events.log(EventType.ROUTING,
                            f"Civilian deferred/unreachable (id={civilian_id}) — "
                            f"will retry if connectivity returns", level="warning")

        def on_replanning(reason: str):
            """Called when the router replans its route."""
            self.events.metrics.total_reroutes += 1
            self.events.log(EventType.ROUTING, f"REPLANNING triggered: {reason}")

        def on_mission_complete(rescued: int, deferred: int):
            """F36: Called when mission ends — updates mission_status."""
            if deferred == 0:
                self.state.mission_status = "ALL_RESCUED"
                self.events.log(EventType.ROUTING,
                                f"MISSION COMPLETE: All {rescued} civilians rescued.")
            else:
                self.state.mission_status = "PARTIAL"
                self.events.log(EventType.ROUTING,
                                f"MISSION ENDED: {rescued} rescued, {deferred} deferred/unreachable.",
                                level="warning")

        def on_response_time(steps: float):
            """F34: Called when a civilian is rescued — records response time in steps."""
            self.events.metrics.record_response_time(steps)

        router.on_civilian_rescued = on_rescued
        router.on_civilian_deferred = on_deferred
        router.on_replanning = on_replanning
        router.on_mission_complete = on_mission_complete
        router.on_response_time_recorded = on_response_time

    # ── Pick random civilians from residential nodes ────────

    def _pick_random_civilians(self, count: int) -> list:
        """Select random residential nodes as civilians to rescue."""
        residential = self.graph.get_nodes_of_type(SimConfig.RESIDENTIAL)
        sample_size = min(count, len(residential))
        return [n.id for n in self._rng.sample(residential, sample_size)]

    # ── Step forward ────────────────────────────────────────

    def step_forward(self):
        """Execute one simulation step."""
        if self.state.step >= self.state.max_steps:
            return

        self.state.step += 1
        # A display horizon must never freeze an in-flight rescue or road handoff.
        if (self.state.step >= self.state.max_steps and
                ((self.state.city_events and (self.state.city_events.enabled or self.state.city_events.road_leases)) or
                 (self.state.fleet and (any(u['phase'] for u in self.state.fleet.units) or
                                       any(e['status']=='QUEUED' for e in self.state.fleet.emergencies))) or
                 (self.state.air_rescue and self.state.air_rescue.status != 'READY') or
                 (self.state.police and (self.state.police.automatic_incidents or
                                        any(r['status']!='RESOLVED' for r in self.state.police.reports) or
                                        any(u['phase'] in ('RESPONDING','ON_SCENE','RETURNING')
                                            for u in self.state.police.units))))):
            self.state.max_steps += SimConfig.MAX_STEPS
        self.events.set_step(self.state.step)
        self.events.log(EventType.SIMULATION, f"--- Step {self.state.step} ---")

        # F13 FIX: Check and set is_complete when step limit reached
        if self.state.step >= self.state.max_steps:
            self.state.is_complete = True
            self.events.log(EventType.SIMULATION, "Step limit reached — simulation complete.")

        if self.state.city_events:
            self.state.city_events.advance(self.state.step)

        # Advance emergency team one step
        if self.state.fleet is not None:
            if self.state.medical_network:
                self.state.medical_network.refresh()
            self.state.fleet.advance(self.state.step)
            if self.state.air_rescue:
                self.state.air_rescue.advance(self.state.step)
        elif self.state.router:
            self.state.router.set_step(self.state.step)  # F34: keep step in sync
            new_pos = self.state.router.advance_one_step(self.state.step)
            if new_pos is not None:
                self.events.log(EventType.ROUTING, f"Team moved to node {self.graph.nodes[new_pos].label}")
            self.state.active_routes = list(self.state.router.current_path)

            # F33 FIX: Collect remaining router log entries (non-metric ones)
            # Metric events are handled by structured callbacks above
            for entry in self.state.router.log:
                if "ROUTE PLANNED" in entry or "MISSION" in entry:
                    self.events.log(EventType.ROUTING, entry)
                elif "WARNING" in entry:
                    self.events.log(EventType.ROUTING, entry, level="warning")
                else:
                    self.events.log(EventType.ROUTING, entry, level="debug")
            self.state.router.log.clear()

        # Periodic crime risk re-evaluation
        # F2 FIX: update_risk() now notifies risk observers; router can replan if needed
        if self.state.step % SimConfig.RISK_REEVAL_INTERVAL == 0:
            self.refresh_risk()
            self.events.log(EventType.ML, "Crime heatmap refreshed from assets, residential context and reported incidents.")

        # Periodic ambulance re-evaluation
        # F3 NOTE: This updates deployment positions. Does NOT change router.current_pos.
        if self.state.fleet is None and self.state.step % SimConfig.AMBULANCE_REEVAL_INTERVAL == 0:
            from challenges.challenge3 import GAambulancePlacer
            placer = GAambulancePlacer(self.graph, pop_size=SimConfig.GA_FAST_POP_SIZE,
                                      generations=SimConfig.GA_FAST_GENERATIONS, rng=self._rng)
            placements = placer.run()
            self.state.optimized_placements = placements
            if self.state.fleet is None:
                self.state.ambulances = placements
            self.events.metrics.ga_best_fitness = placer.best_fitness
            self.events.log(EventType.AMBULANCE,
                            f"GA staging recommendation: {[self.graph.nodes[n].label for n in placements]}"
                            f" (deployment positions; rescue team at "
                            f"{self.graph.nodes[self.state.router.current_pos].label if self.state.router and self.state.router.current_pos is not None else 'N/A'})")
            self.events.metrics.ambulance_repositions += 1

        # Update edge counts in metrics
        if self.state.police:
            before={r['id'] for r in self.state.police.reports}
            self.state.police.advance(self.state.step)
            if self.state.city_events:
                for report in self.state.police.reports:
                    if report['id'] not in before and report['source']=='AUTOMATIC':
                        self.state.city_events.record('CRIME',self.state.step,node_id=report['node_id'],
                            label=report['label'],report_id=report['id'],crime_type=report['kind'])
        self.events.metrics.total_edges_active = self.graph.count_active_edges()
        self.events.metrics.total_edges_blocked = self.graph.count_blocked_edges()

        # F35 FIX: Refresh disconnected_nodes metric every step
        self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())

        if self.state.is_complete:
            self.events.metrics.simulation_end_time = time.time()

    # ── Flood event ─────────────────────────────────────────

    def _trigger_flood(self):
        """Block a random active edge to simulate a flood event."""
        active_edges = [(k, e) for k, e in self.graph.edges.items() if not e.blocked]
        if not active_edges:
            return
        key, edge = self._rng.choice(active_edges)
        changed = self.graph.block_road(edge.node_a, edge.node_b)
        if changed:
            self.state.flood_history.append((self.state.step, edge.node_a, edge.node_b))
            self.state.flood_event_history.append((self.state.step, f"edge({edge.node_a},{edge.node_b})", 1))
            self.events.log(EventType.FLOOD,
                            f"Road between {self.graph.nodes[edge.node_a].label} and "
                            f"{self.graph.nodes[edge.node_b].label} flooded!")
            self.events.metrics.total_floods += 1

    def trigger_flood_at_node(self, node_id: int) -> dict:
        """
        Manually flood a specific node by blocking all adjacent roads.

        F6 FIX: Does NOT advance simulation step. Flooding is a pure graph mutation.
        F7 FIX: Counts as ONE flood event, not one per edge.
        F9 FIX: Returns result dict with flooded=True/False and edges_blocked count.
        F32 FIX: Uses batch block mode — triggers single replan after all edges blocked.

        Returns:
            {"flooded": bool, "node_id": int, "edges_blocked": int, "message": str}
        """
        # F9 FIX: Validate node_id
        if node_id not in self.graph.nodes:
            return {
                "flooded": False,
                "node_id": node_id,
                "edges_blocked": 0,
                "message": f"Node {node_id} does not exist in graph."
            }

        edges_to_block = []
        for key, edge in self.graph.edges.items():
            if not edge.blocked and (edge.node_a == node_id or edge.node_b == node_id):
                edges_to_block.append((key, edge))

        if not edges_to_block:
            return {
                "flooded": False,
                "node_id": node_id,
                "edges_blocked": 0,
                "message": f"Node {node_id} ({self.graph.nodes[node_id].label}) has no active edges to flood."
            }

        # F32 FIX: Begin batch block — suppress intermediate replans
        if self.state.router:
            self.state.router.begin_batch_block()
            for key, edge in edges_to_block:
                self.state.router.mark_batch_affected(edge.node_a, edge.node_b)

        edges_actually_blocked = 0
        for key, edge in edges_to_block:
            changed = self.graph.block_road(edge.node_a, edge.node_b)
            if changed:
                self.state.flood_history.append((self.state.step, edge.node_a, edge.node_b))
                edges_actually_blocked += 1

        # F32 FIX: End batch — trigger single replan if needed
        if self.state.router:
            self.state.router.end_batch_block()

        if edges_actually_blocked > 0:
            # F7 FIX: Count ONE flood event, not per-edge
            self.events.metrics.total_floods += 1
            self.state.flood_event_history.append(
                (self.state.step, node_id, edges_actually_blocked)
            )
            self.events.log(
                EventType.FLOOD,
                f"GOD MODE: Flood at {self.graph.nodes[node_id].label}! "
                f"{edges_actually_blocked} road(s) blocked.",
                level="warning"
            )

        if self.state.fleet is not None:
            if self.state.medical_network:
                self.state.medical_network.refresh()
            self.state.fleet.replan()
        if self.state.police:
            self.state.police.refresh(self.state.step)
        # F35: Refresh disconnected_nodes after flood
        self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())

        return {
            "flooded": edges_actually_blocked > 0,
            "node_id": node_id,
            "edges_blocked": edges_actually_blocked,
            "message": (
                f"Flooded node {self.graph.nodes[node_id].label}: "
                f"{edges_actually_blocked} road(s) blocked."
                if edges_actually_blocked > 0
                else f"Node {self.graph.nodes[node_id].label} had no active edges to flood."
            )
        }

    def block_road_manually(self, node_a: int, node_b: int, source='MANUAL') -> dict:
        """
        F8/F10 FIX: Manually block a road between node_a and node_b.
        Validates both IDs and edge existence. Returns outcome dict.

        Returns:
            {"changed": bool, "message": str}
        """
        if node_a not in self.graph.nodes:
            return {"changed": False, "error": f"Node {node_a} does not exist."}
        if node_b not in self.graph.nodes:
            return {"changed": False, "error": f"Node {node_b} does not exist."}

        key = (min(node_a, node_b), max(node_a, node_b))
        if key not in self.graph.edges:
            return {"changed": False, "error": f"No road exists between {node_a} and {node_b}."}

        if source=='MANUAL' and self.state.city_events:
            self.state.city_events.release_road(key)
        changed = self.graph.block_road(node_a, node_b)
        if changed:
            self.state.disasters.record('block', self.state.step,
                                        f"{'Automatic temporary' if source=='AUTOMATIC' else 'Manual'} road closure: {self.graph.nodes[node_a].label} - {self.graph.nodes[node_b].label} fully blocked.")
            self.state.flood_history.append((self.state.step, node_a, node_b))
            # F8 FIX: Manual block does NOT increment total_floods (it's not a flood event)
            # It's a road closure. Metrics track separately.
            self.events.log(EventType.FLOOD,
                            f"Manual road closure: {self.graph.nodes[node_a].label} <-> "
                            f"{self.graph.nodes[node_b].label}",
                            level="warning")
            # F35: Update disconnected_nodes
            self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())
        if self.state.fleet is not None:
            if self.state.medical_network:
                self.state.medical_network.refresh()
            self.state.fleet.replan()
        if self.state.police:
            self.state.police.refresh(self.state.step)
        return {
            "changed": changed,
            "message": (
                f"Road {self.graph.nodes[node_a].label} <-> {self.graph.nodes[node_b].label} "
                f"{'blocked' if changed else 'was already blocked (no-op)'}."
            )
        }

    def unblock_road_manually(self, node_a: int, node_b: int, source='MANUAL') -> dict:
        """
        F8/F10 FIX: Manually unblock a road. Validates both IDs and edge existence.

        Returns:
            {"changed": bool, "message": str}
        """
        if node_a not in self.graph.nodes:
            return {"changed": False, "error": f"Node {node_a} does not exist."}
        if node_b not in self.graph.nodes:
            return {"changed": False, "error": f"Node {node_b} does not exist."}

        key = (min(node_a, node_b), max(node_a, node_b))
        if key not in self.graph.edges:
            return {"changed": False, "error": f"No road exists between {node_a} and {node_b}."}

        if source=='MANUAL' and self.state.city_events:
            self.state.city_events.release_road(key)
        changed = self.graph.unblock_road(node_a, node_b, preserve_restrictions=source=='AUTOMATIC')
        if changed:
            self.state.disasters.record('unblock', self.state.step,
                                        f"Road {self.graph.nodes[node_a].label} - {self.graph.nodes[node_b].label}: "+
                                        ('automatic closure expired; Gate restrictions retained.' if source=='AUTOMATIC' else 'reopened for all traffic.'))
        if changed:
            self.events.log(EventType.FLOOD,
                            f"Road restored: {self.graph.nodes[node_a].label} <-> "
                            f"{self.graph.nodes[node_b].label}")
            # F35: Update disconnected_nodes
            self.events.metrics.disconnected_nodes = len(self.graph.find_disconnected_nodes())
        if self.state.fleet is not None:
            if self.state.medical_network:
                self.state.medical_network.refresh()
            self.state.fleet.replan()
        if self.state.police:
            self.state.police.refresh(self.state.step)
        return {
            "changed": changed,
            "message": (
                f"Road {self.graph.nodes[node_a].label} <-> {self.graph.nodes[node_b].label} "
                f"{'unblocked' if changed else 'was already open (no-op)'}."
            )
        }

    # ── Full simulation run ─────────────────────────────────

    def run_full(self) -> SimulationState:
        """
        Run the complete simulation (initialize + all steps).
        Returns the final SimulationState.
        """
        self.initialize()
        for _ in range(self.state.max_steps):
            self.step_forward()

        self.state.is_complete = True
        self.events.metrics.simulation_end_time = time.time()
        self.events.log(EventType.SIMULATION, "SIMULATION COMPLETE.")
        self.events.log(EventType.METRIC, self.events.metrics.summary())

        return self.state
