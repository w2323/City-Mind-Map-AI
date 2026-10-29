# state.py — CityMind 2D: Application State
# Single authoritative client-side state object.
# Distinguishes: backend snapshot, cached display, pending ops, diagnostics.

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto
import threading
import time


class ConnectionStatus(Enum):
    DISCONNECTED = auto()
    CONNECTING   = auto()
    CONNECTED    = auto()
    ERROR        = auto()


class ActiveScreen(Enum):
    DASHBOARD       = "Dispatch"
    CITY_MAP        = "City Map"
    ROUTE_LAB       = "Route Lab"
    GOD_MODE        = "Disasters"
    AMBULANCE       = "Ambulance Center"
    RISK_HEATMAP    = "Crime Heatmap"
    POLICE          = "Police Operations"
    METRICS         = "Metrics & Log"
    DIAGNOSTICS     = "Diagnostics"


@dataclass
class GraphSnapshot:
    """Immutable snapshot of the backend graph at a point in time."""
    nodes:         dict = field(default_factory=dict)   # id -> node_dict
    edges:         list = field(default_factory=list)   # list of edge_dict
    grid_rows:     int  = 15
    grid_cols:     int  = 15
    active_edges:  int  = 0
    blocked_edges: int  = 0
    edge_index:    dict = field(default_factory=dict)
    fetched_at:    float = 0.0

    def is_stale(self, max_age: float = 30.0) -> bool:
        return (time.time() - self.fetched_at) > max_age


@dataclass
class SimSnapshot:
    """Most recently fetched simulation state."""
    sim_id:            str   = ""   # F40: Backend simulation/session version UUID
    fleet:             list  = field(default_factory=list)
    emergencies:       list  = field(default_factory=list)
    dispatch_summary:  dict  = field(default_factory=dict)
    medical_network:   dict  = field(default_factory=dict)
    air_rescue:        dict  = field(default_factory=dict)
    disasters:         dict  = field(default_factory=dict)
    police:            dict  = field(default_factory=dict)
    city_events:       dict  = field(default_factory=dict)
    optimized_placements: list = field(default_factory=list)
    revision:          int   = 0
    analysis:          dict  = field(default_factory=dict)
    config:            dict  = field(default_factory=dict)
    optimization:      dict  = field(default_factory=dict)
    mission_status:    str   = "NOT_STARTED"
    step:              int   = 0
    max_steps:         int   = 100
    is_initialized:    bool  = False
    is_complete:       bool  = False
    ambulances:        list  = field(default_factory=list)
    civilians:         list  = field(default_factory=list)
    flood_history:     list  = field(default_factory=list)
    risk_predictions:  dict  = field(default_factory=dict)
    active_routes:     list  = field(default_factory=list)
    police_deployments:list  = field(default_factory=list)
    router:            dict  = field(default_factory=dict)
    events:            dict  = field(default_factory=dict)
    fetched_at:        float = 0.0

    @property
    def metrics(self) -> dict:
        return self.events.get("metrics", {})

    @property
    def event_log(self) -> list:
        return self.events.get("events", [])


class AppLog:
    """Client-side log of operations and diagnostics (NOT backend history)."""

    def __init__(self, max_entries: int = 500):
        self._entries: list = []
        self._lock = threading.Lock()
        self.max_entries = max_entries

    def add(self, message: str, level: str = "info", category: str = "APP"):
        ts = time.strftime("%H:%M:%S")
        entry = {"ts": ts, "level": level, "cat": category, "msg": message}
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries.pop(0)

    def entries(self, level_filter: str = None, cat_filter: str = None) -> list:
        with self._lock:
            result = list(self._entries)
        if level_filter:
            result = [e for e in result if e["level"] == level_filter]
        if cat_filter:
            result = [e for e in result if e["cat"] == cat_filter]
        return result

    def clear(self):
        with self._lock:
            self._entries.clear()


class AppState:
    """
    Single authoritative application state.

    Layers:
      backend_graph   — last confirmed GraphSnapshot from API
      backend_sim     — last confirmed SimSnapshot from API
      local_log       — client-side operation log
      pending_op      — name of in-flight operation or None
      selected_node   — currently selected node id (int) or None
      selected_edge   — currently selected edge tuple (a,b) or None
      active_screen   — which screen is visible
      connection      — ConnectionStatus enum
      god_mode        — bool: God Mode active
    """

    def __init__(self):
        self.backend_graph:   GraphSnapshot   = GraphSnapshot()
        self.backend_sim:     SimSnapshot     = SimSnapshot()
        self.local_log:       AppLog          = AppLog()
        self.pending_op:      Optional[str]   = None
        self.selected_node:   Optional[int]   = None
        self.selected_edge:   Optional[tuple] = None
        self.active_screen:   ActiveScreen    = ActiveScreen.DASHBOARD
        self.connection:      ConnectionStatus= ConnectionStatus.DISCONNECTED
        self.god_mode:        bool            = False
        self.last_error:      Optional[str]   = None

        # Route Lab state
        self.route_src:       Optional[int]   = None
        self.route_dst:       Optional[int]   = None
        self.route_result:    Optional[dict]  = None   # backend route
        self.route_ref:       Optional[dict]  = None   # reference Dijkstra result
        self.route_validation:Optional[dict]  = None   # validation report

        # Map view state (managed by GraphRenderer)
        self.map_offset:      list = [0, 0]
        self.map_scale:       float = 1.0

        # Heatmap layer
        self.heatmap_layer:   str  = "risk"  # "risk" | "population" | "police" | "ambulance"

        # Flood test results
        self.flood_test_results: list = []

        # Diagnostics cache
        self.graph_diagnostics: Optional[dict] = None

        self._lock = threading.RLock()
        self._retired_sim_ids = []
        self.visual_revision = 0

    def update_graph(self, graph_dict: dict):
        if not isinstance(graph_dict, dict):
            return
        with self._lock:
            raw_nodes = graph_dict.get("nodes", [])
            if isinstance(raw_nodes, dict):
                raw_nodes = raw_nodes.values()
            nodes = {nd["id"]: nd for nd in raw_nodes if isinstance(nd, dict) and isinstance(nd.get("id"), int)}
            raw_edges = graph_dict.get("edges", [])
            if isinstance(raw_edges, dict):
                raw_edges = raw_edges.values()
            edges = [e for e in raw_edges if isinstance(e, dict) and e.get("node_a") in nodes and e.get("node_b") in nodes]
            previous = self.backend_graph
            if nodes == previous.nodes:
                nodes = previous.nodes
            if edges == previous.edges:
                edges = previous.edges
            edge_index = previous.edge_index if edges is previous.edges else {
                (min(e["node_a"], e["node_b"]), max(e["node_a"], e["node_b"])): e for e in edges
            }
            self.backend_graph = GraphSnapshot(
                nodes         = nodes,
                edges         = edges,
                edge_index    = edge_index,
                grid_rows     = graph_dict.get("grid_rows", 15),
                grid_cols     = graph_dict.get("grid_cols", 15),
                active_edges  = graph_dict.get("active_edges", 0),
                blocked_edges = graph_dict.get("blocked_edges", 0),
                fetched_at    = time.time(),
            )

    def update_sim(self, sim_dict: dict):
        if not isinstance(sim_dict, dict):
            return

        # Handle wrapped state dict if present
        if "state" in sim_dict and isinstance(sim_dict["state"], dict):
            outer_sim_id = sim_dict.get("sim_id", "")
            sim_dict = dict(sim_dict["state"])
            if outer_sim_id and not sim_dict.get("sim_id"):
                sim_dict["sim_id"] = outer_sim_id

        incoming_sim_id = sim_dict.get("sim_id", "")
        incoming_step = sim_dict.get("step", 0)
        incoming_revision = sim_dict.get("revision", 0)

        with self._lock:
            if incoming_sim_id and incoming_sim_id in self._retired_sim_ids:
                return False
            previous = self.backend_sim
            previous_graph = self.backend_graph
            if previous.sim_id and incoming_sim_id and previous.sim_id != incoming_sim_id:
                self._retired_sim_ids = (self._retired_sim_ids + [previous.sim_id])[-32:]
                self.selected_node = self.selected_edge = None
                self.route_result = self.route_ref = self.route_validation = None
            # F23: Prevent stale background poller response from overwriting newer mutation state
            if self.backend_sim.sim_id and incoming_sim_id:
                if incoming_sim_id == self.backend_sim.sim_id:
                    if incoming_step < self.backend_sim.step or incoming_revision < self.backend_sim.revision:
                        # Stale older step received from delayed poller — discard
                        return False

            # Update embedded graph if present
            if "graph" in sim_dict and sim_dict["graph"]:
                self.update_graph(sim_dict["graph"])

            router_d = sim_dict.get("router", {}) or {}
            self.backend_sim = SimSnapshot(
                sim_id             = incoming_sim_id or self.backend_sim.sim_id,
                revision           = incoming_revision,
                fleet              = sim_dict.get("fleet", []),
                emergencies        = sim_dict.get("emergencies", []),
                dispatch_summary   = sim_dict.get("dispatch_summary", {}),
                medical_network    = sim_dict.get('medical_network', {}),
                air_rescue         = sim_dict.get('air_rescue', {}),
                city_events        = sim_dict.get('city_events', {}),
                disasters          = sim_dict.get('disasters', {}),
                police             = sim_dict.get('police', {}),
                optimized_placements = sim_dict.get("optimized_placements", []),
                analysis           = sim_dict.get("analysis", {}),
                config             = sim_dict.get("config", {}),
                optimization       = sim_dict.get("optimization", {}),
                mission_status     = sim_dict.get("mission_status", "NOT_STARTED"),
                step               = incoming_step,
                max_steps          = sim_dict.get("max_steps", 100),
                is_initialized     = sim_dict.get("is_initialized", False),
                is_complete        = sim_dict.get("is_complete", False),
                ambulances         = sim_dict.get("ambulances", []),
                civilians          = sim_dict.get("civilians_remaining", []),
                flood_history      = sim_dict.get("flood_history", []),
                risk_predictions   = sim_dict.get("risk_predictions", {}),
                active_routes      = sim_dict.get("active_routes", []),
                police_deployments = sim_dict.get("police_deployments", []),
                router             = router_d,
                events             = sim_dict.get("events", {}),
                fetched_at         = time.time(),
            )

            current = self.backend_sim
            changed = (previous_graph.nodes is not self.backend_graph.nodes or
                       previous_graph.edges is not self.backend_graph.edges or
                       any(getattr(previous, key) != getattr(current, key) for key in
                           ("sim_id", "revision", "step", "fleet", "emergencies", "medical_network", "air_rescue", "disasters", "police", "city_events", "ambulances", "civilians", "active_routes",
                            "risk_predictions", "police_deployments", "optimization", "mission_status")))
            if changed:
                self.visual_revision += 1
            return changed

    def get_node(self, node_id: int) -> Optional[dict]:
        return self.backend_graph.nodes.get(node_id)

    def get_edge(self, a: int, b: int) -> Optional[dict]:
        return self.backend_graph.edge_index.get((min(a, b), max(a, b)))

    @property
    def is_connected(self) -> bool:
        return self.connection == ConnectionStatus.CONNECTED

    @property
    def has_graph(self) -> bool:
        return bool(self.backend_graph.nodes)
