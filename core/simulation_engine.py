# simulation_engine.py — CityMind Simulation Engine
# Contains SimulationState (single source of truth) and Simulation runner.
# No GUI dependencies. Fully terminal-runnable.

import random
import time
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
        self.ambulances: list = []           # Current ambulance node IDs
        self.civilians: list = []            # Active civilian node IDs
        self.flood_history: list = []        # (step, id_a, id_b) tuples
        self.risk_predictions: dict = {}     # node_id -> risk_level
        self.active_routes: list = []        # Current planned route path
        self.police_deployments: list = []   # [(node_id, risk_level, score)] for 10 officers
        self.router = None                   # AStarRouter instance
        self.is_initialized: bool = False
        self.is_complete: bool = False

    def to_dict(self) -> dict:
        """
        Serialize the complete simulation state for API consumption.
        This is what a React frontend would receive via WebSocket.
        """
        result = {
            "step": self.step,
            "max_steps": self.max_steps,
            "is_initialized": self.is_initialized,
            "is_complete": self.is_complete,
            "graph": self.graph.to_dict(),
            "ambulances": self.ambulances,
            "civilians_remaining": self.civilians,
            "flood_history": [
                {"step": s, "node_a": a, "node_b": b}
                for s, a, b in self.flood_history
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
            result["router"] = self.router.to_dict()
        return result


# ──────────────────────────────────────────────────────────
# Simulation — the main simulation runner
# ──────────────────────────────────────────────────────────
class Simulation:
    """
    20-step simulation engine that integrates all 5 challenges.

    Initialization order (dependency-driven):
        1. CSP (layout) → assigns zone types
        2. MST (roads) → builds road network
        3. ML (crime risk) → predicts risk, updates edge costs
        4. GA (ambulances) → places ambulances using risk-aware costs
        5. A* (routing) → plans rescue mission

    Each simulation step:
        - Random flood events (30% chance)
        - Emergency team advancement
        - Periodic ambulance repositioning (every 5 steps)
        - Periodic risk re-evaluation (every 5 steps)
        - Comprehensive logging
    """

    def __init__(self, seed: int = None, verbose: bool = True):
        # Set deterministic seed if provided
        self._seed = seed or SimConfig.SEED
        if self._seed is not None:
            random.seed(self._seed)

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
        from challenges.layout_planning import CSPSolver
        solver = CSPSolver(self.graph)
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
        from challenges.road_optimization import build_road_network
        build_road_network(self.graph)
        self.events.log(EventType.ROADS,
                        f"Road network built. "
                        f"{self.graph.count_active_edges()} active edges.")

        # 3. Challenge 5: Crime risk ML (run BEFORE GA so risk weights affect fitness)
        self.events.log(EventType.ML, "Running crime risk prediction pipeline...")
        from challenges.crime_prediction import run_crime_risk_pipeline
        kmeans, dt = run_crime_risk_pipeline(self.graph)

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
                        f"Crime risk prediction complete. "
                        f"HIGH={risk_counts['HIGH']}, "
                        f"MEDIUM={risk_counts['MEDIUM']}, "
                        f"LOW={risk_counts['LOW']}")

        # Log Decision Tree rules for explainability
        self.events.log(EventType.ML,
                        f"Decision Tree rules:\n{dt.explain()}", level="debug")

        # Deploy 10 police officers to highest-risk zones
        from challenges.crime_prediction import deploy_police_officers
        self.state.police_deployments = deploy_police_officers(self.graph)
        officer_nodes = [self.graph.nodes[d[0]].label for d in self.state.police_deployments]
        self.events.log(EventType.ML,
                        f"10 police officers deployed to nodes: {', '.join(officer_nodes)}")

        # 4. Challenge 3: Ambulance placement via GA
        self.events.log(EventType.AMBULANCE, "Running GA for ambulance placement...")
        from challenges.ambulance_placement import GAambulancePlacer
        ga_placer = GAambulancePlacer(self.graph)
        self.state.ambulances = ga_placer.run()
        self.events.metrics.ga_best_fitness = ga_placer.best_fitness
        self.events.log(EventType.AMBULANCE,
                        f"Ambulances placed at nodes {[self.graph.nodes[n].label for n in self.state.ambulances]} "
                        f"(fitness={ga_placer.best_fitness:.3f})")

        # 5. Challenge 4: Emergency routing via A*
        self.events.log(EventType.ROUTING, "Creating A* emergency router...")
        from challenges.emergency_routing import create_router
        self.state.router = create_router(self.graph)
        self.state.civilians = self._pick_random_civilians(SimConfig.NUM_CIVILIANS)
        hospitals = self.graph.get_nodes_of_type(SimConfig.HOSPITAL)
        start_id = hospitals[0].id if hospitals else 0
        self.state.router.set_mission(start_id, self.state.civilians)
        self.events.log(EventType.ROUTING,
                        f"Mission set. Start: node {self.graph.nodes[start_id].label}. "
                        f"Civilians at: {[self.graph.nodes[n].label for n in self.state.civilians]}")

        # Update state
        self.state.is_initialized = True
        self.events.metrics.total_edges_active = self.graph.count_active_edges()
        self.events.log(EventType.SIMULATION,
                        "Initialization complete. All 5 challenges ready.")

    # ── Pick random civilians from residential nodes ────────

    def _pick_random_civilians(self, count: int) -> list:
        """Select random residential nodes as civilians to rescue."""
        residential = self.graph.get_nodes_of_type(SimConfig.RESIDENTIAL)
        sample_size = min(count, len(residential))
        return [n.id for n in random.sample(residential, sample_size)]

    # ── Step forward ────────────────────────────────────────

    def step_forward(self):
        """Execute one simulation step."""
        if self.state.step >= self.state.max_steps:
            return

        self.state.step += 1
        self.events.set_step(self.state.step)
        self.events.log(EventType.SIMULATION, f"--- Step {self.state.step} ---")

        # Random flood event (FLOOD_PROBABILITY chance)
        if random.random() < SimConfig.FLOOD_PROBABILITY:
            self._trigger_flood()

        # Advance emergency team one step
        if self.state.router:
            new_pos = self.state.router.advance_one_step()
            if new_pos is not None:
                self.events.log(EventType.ROUTING, f"Team moved to node {self.graph.nodes[new_pos].label}")
            self.state.active_routes = list(self.state.router.current_path)

            # Collect router log entries
            for entry in self.state.router.log:
                if "CIVILIAN REACHED" in entry:
                    self.events.log(EventType.ROUTING, entry)
                    self.events.metrics.civilians_rescued += 1
                elif "WARNING" in entry:
                    self.events.log(EventType.ROUTING, entry, level="warning")
                    self.events.metrics.civilians_unreachable += 1
                elif "REPLANNING" in entry:
                    self.events.log(EventType.ROUTING, entry)
                    self.events.metrics.total_reroutes += 1
                elif "MISSION COMPLETE" in entry:
                    self.events.log(EventType.ROUTING, entry)
                else:
                    self.events.log(EventType.ROUTING, entry, level="debug")
            self.state.router.log.clear()

        # Periodic ambulance re-evaluation
        if self.state.step % SimConfig.AMBULANCE_REEVAL_INTERVAL == 0:
            from challenges.ambulance_placement import place_ambulances_fast
            self.state.ambulances = place_ambulances_fast(self.graph)
            self.events.log(EventType.AMBULANCE,
                            f"Ambulances re-evaluated. Now at {[self.graph.nodes[n].label for n in self.state.ambulances]}")
            self.events.metrics.ambulance_repositions += 1

        # Periodic crime risk re-evaluation
        if self.state.step % SimConfig.RISK_REEVAL_INTERVAL == 0:
            from challenges.crime_prediction import run_crime_risk_pipeline, deploy_police_officers
            run_crime_risk_pipeline(self.graph)
            risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for nid, node in self.graph.nodes.items():
                self.state.risk_predictions[nid] = node.risk_level
                if node.risk_level in risk_counts:
                    risk_counts[node.risk_level] += 1
            self.events.metrics.high_risk_zones = risk_counts["HIGH"]
            self.events.metrics.medium_risk_zones = risk_counts["MEDIUM"]
            self.events.metrics.low_risk_zones = risk_counts["LOW"]
            self.events.log(EventType.ML, "Crime risk re-evaluated.")
            # Re-deploy police officers based on updated risk
            self.state.police_deployments = deploy_police_officers(self.graph)
            self.events.log(EventType.ML, "Police officers re-deployed to updated risk zones.")

        # Update edge counts in metrics
        self.events.metrics.total_edges_active = self.graph.count_active_edges()
        self.events.metrics.total_edges_blocked = self.graph.count_blocked_edges()

    # ── Flood event ─────────────────────────────────────────

    def _trigger_flood(self):
        """Block a random active edge to simulate a flood event."""
        active_edges = [(k, e) for k, e in self.graph.edges.items() if not e.blocked]
        if not active_edges:
            return
        key, edge = random.choice(active_edges)
        self.graph.block_road(edge.node_a, edge.node_b)
        self.state.flood_history.append((self.state.step, edge.node_a, edge.node_b))
        self.events.log(EventType.FLOOD,
                        f"Road between {self.graph.nodes[edge.node_a].label} and {self.graph.nodes[edge.node_b].label} flooded!")
        self.events.metrics.total_floods += 1

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
