Current UI and ambulance behavior: [DISPATCH_WORKSPACE.md](DISPATCH_WORKSPACE.md). The explicit depot-fleet workflow supersedes earlier descriptions of preset civilian missions and GA redeployment.

See [OPTIMIZATION_NOTES.md](OPTIMIZATION_NOTES.md) for current controls, performance measurements, lifecycle improvements, and verification commands.

# CityMind — 2D Operations Center (Pygame Desktop Application)

An engineering-grade, 2D desktop operations center built with Python and Pygame for **City Mind Map AI**. It provides complete observability, rigorous shortest-path validation, real-time God Mode intervention testing, multi-layer heatmaps, and comprehensive automated test suites.

---

## 1. Architecture Overview

- **Native Pygame Desktop Application**: Pure Python desktop UI built with `pygame-ce`. Does **not** require a web browser or localhost web frontend server.
- **Decoupled Client-Server Model**: Communicates with the FastAPI simulation backend over a clean, thread-safe HTTP API (`backend_client/api_client.py`).
- **Non-Blocking Architecture**: Background poller (`BackgroundPoller`) and asynchronous mutation runner (`AsyncOpRunner`) ensure the UI event loop runs smoothly at 60 FPS without stutter or freezing.
- **Reference Shortest-Path Engine**: Includes an independent, authoritative Dijkstra implementation (`algorithms/reference_dijkstra.py`) to audit and validate backend A* paths and per-edge traversal costs.
- **Preserved 3D Frontend**: The original React Three.js frontend in `frontend/` is preserved intact and untouched.

---

## 2. Nine Specialized Operational Screens

| Screen | Key Features |
|---|---|
| **Dashboard** | Simulation KPIs (step, active edges, rescued civilians, risk distribution), quick action buttons, live log feed. |
| **City Map** | Interactive 2D grid rendering with pan & zoom, node inspector (type, population, risk index/level, coordinates), edge inspector (base cost, directional effective cost, blocked status). |
| **Route Lab** | Side-by-side comparison of backend A* vs independent reference Dijkstra; per-edge cost breakdown with risk multipliers; optimality and validity checks; dual-route map overlays. |
| **God Mode** | Controlled disaster simulation; interactive node selection; safe confirmation dialog; single-node flood triggering; route replanning verification; flood history tracking. |
| **Ambulance Center** | GA placement fitness and node positions; civilian rescue progress; reachability matrix from each ambulance; active route optimality check. |
| **Risk & Heatmap** | 4 selectable heatmap overlays: Crime Risk Level, Population Density, Ambulance Reachability, and Police Coverage. Node risk inspector and distribution statistics. |
| **Police Deployment** | 10-officer deployment from the ML pipeline (K-Means + Decision Tree); priority scoring; risk distribution display. |
| **Metrics & Event Log** | Comprehensive metric panels (simulation progress, graph connectivity, response metrics) and searchable, color-coded backend event history. |
| **Engineering Diagnostics** | Automated graph integrity checks, routing correctness tests, hop-count vs weighted-cost trap audit, backend connection health, and documented architectural findings. |

---

## 3. Quick Start & Launch Instructions

### Prerequisites

Install Python 3.10+ dependencies:

```bash
pip install -r requirements.txt
pip install pygame-ce
```

### Step 1: Start the Backend API

In a terminal:

```bash
python -m uvicorn backend.api.main:app --port 8000
```

### Step 2: Launch the 2D Desktop Application

In a separate terminal:

```bash
# Launch directly to dashboard
python frontend-2d-pygame/main.py

# Launch directly into a specific screen
python frontend-2d-pygame/main.py --screen route_lab
python frontend-2d-pygame/main.py --screen god_mode
python frontend-2d-pygame/main.py --screen diagnostics

# Custom backend URL
python frontend-2d-pygame/main.py --backend-url http://127.0.0.1:8000
```

---

## 4. Automated Testing

Run the full automated test suite (29 tests across 6 test modules):

```bash
python -m pytest frontend-2d-pygame/tests -v
```

### Test Suite Coverage:
1. `test_graph.py`: Node ID uniqueness, grid coordinates, valid endpoints, adjacency symmetry, edge blocking/unblocking, graph serialization roundtrip, isolated node detection.
2. `test_routing.py`: Weighted shortest paths, hop-count trap (verifies algorithm does not mistakenly favor fewer hops over lower cost), A* vs Reference Dijkstra equivalence, blocked road avoidance, unreachable destination handling, risk-multiplier sensitivity.
3. `test_flood_replanning.py`: Observer event-driven dynamic replanning upon road closures, alternative path selection, unreachable civilian skips, consecutive floods, road unblocking.
4. `test_ambulance.py`: Source node verification (router starts at active ambulance, not arbitrary hospital), GA fitness validation, civilian rescue progression.
5. `test_frontend_integration.py`: Graceful backend connection failure handling, timeout handling, invalid node ID rejection, zero vs missing value distinction, local log ring buffer.
6. `test_regression.py`: Explicit regression tests for all resolved backend defects.

---

## 5. Summary of Audited & Fixed Backend Defects

1. **Directional Edge Traversal Cost (`core/city_graph.py`)**:
   - *Problem*: `Edge.effective_cost` hardcoded evaluation of `self.node_b`, so traversing from node $B$ into node $A$ incorrectly evaluated $B$'s risk level rather than destination $A$'s risk level.
   - *Fix*: Parameterized `effective_cost(graph, to_node_id=None)` and updated `CityGraph.get_edge_cost(id_a, id_b)` to pass `to_node_id=id_b`.
2. **Emergency Route Source Selection (`core/simulation_engine.py`)**:
   - *Problem*: Emergency rescue mission was hardcoded to start at `hospitals[0].id` rather than from an active ambulance position.
   - *Fix*: Mission start node dynamically selects the closest placed ambulance to the first target civilian.
3. **Road Unblocking Method (`core/city_graph.py`)**:
   - *Problem*: `CityGraph` lacked an `unblock_road` method to reopen previously closed edges.
   - *Fix*: Added `unblock_road(id_a, id_b)` restoring adjacency lists and setting `blocked=False`.
4. **Backend API Endpoints (`backend/api/main.py`)**:
   - *Enhancement*: Added `/simulation/reset`, `/simulation/block_road/{node_a}/{node_b}`, and `/simulation/unblock_road/{node_a}/{node_b}` while preserving all existing routes.
