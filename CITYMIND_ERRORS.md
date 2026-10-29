# CityMind AI — Findings Against the Original Uploaded ZIP

**Scope:** The original `City-Mind-Map-AI-main(1).zip` only. No project files were changed. The detached React/3D frontend is excluded from the review, except where the current 2D Diagnostics screen contains stale claims about it. This is a code-level review plus the bundled Pygame tests; it is not a claim that every runtime/UI interaction was manually exercised.

## Verification baseline

- Ran the bundled `frontend-2d-pygame` test suite against the original archive: **29 passed**.
- Passing tests do not cover many of the failure cases below.
- The pasted LLM report contains useful findings, but a few of its statements are stale for this exact ZIP. In particular, this ZIP's `core/simulation_engine.py` already chooses the nearest placed ambulance to the first civilian when creating the initial mission (`lines 187–200`); it does **not** always start at `hospitals[0]`. The 2D Diagnostics screen still incorrectly claims that it does.

## A. Critical / high-priority correctness defects

### 1. A* heuristic can overestimate path cost
**File:** `challenges/challenge4.py:10–14, 79–120`; costs in `config/simulation_config.py:12–23`; graph generation in `challenges/challenge2.py:24–47`.

The A* heuristic is raw Euclidean grid distance. Yet orthogonal residential-to-residential edges cost `0.8`, and diagonal edges cost `1.4` versus geometric diagonal length about `1.414`. The heuristic is therefore not guaranteed to be admissible. Since the implementation also uses a closed set and does not reopen a closed node when a cheaper route is found, it is not guaranteed to return the minimum-cost route on the generated weighted graph.

**Impact:** The route may be legal but more expensive than the true optimum, especially on residential/diagonal combinations. This undermines ambulance response cost, route validation, and comparisons with Dijkstra.

**Needed verification/fix:** Compare A* against reference Dijkstra on generated/random graphs with every configured edge type, risk levels, and blocked roads. Use a proven admissible heuristic or zero heuristic (Dijkstra behavior) until validated.

### 2. Risk changes do not cause active-route replanning
**Files:** `core/city_graph.py:224–243`; `core/simulation_engine.py:263–278`; `challenges/challenge4.py:133–145`.

`update_risk()` changes node risk directly, and edge cost depends on the destination node's current risk. The router only observes road-block events. The periodic crime-risk pipeline updates risk predictions and police deployment but does not ask the router to reconsider its route.

**Impact:** The active route can remain legal but no longer be the cheapest route under the current risk costs. The frontend can report old route decisions as if they reflect the latest risk map.

### 3. Ambulance repositioning is not connected to the active mission vehicle
**File:** `core/simulation_engine.py:255–261`.

Every configured five steps, the GA replaces `state.ambulances` with a new placement list. It does not move actual ambulance entities, preserve per-vehicle status, or synchronize the active router's current position/assignment. The router is a single moving rescue team, while the displayed ambulance list is a separate placement result.

**Impact:** The map can show ambulances at new nodes while the active route continues from the previous mission position. It cannot faithfully model multiple independently dispatched ambulances.

**Nuance for this ZIP:** Initial mission creation does choose the nearest currently placed ambulance to the first civilian (`simulation_engine.py:187–200`), so the pasted report's claim that the initial router always starts at the first hospital is stale. The repositioning/dispatch architecture problem remains.

### 4. Genetic-algorithm ambulance placement is effectively not optimizing the configured choice
**Files:** `challenges/challenge3.py:31–49, 71–105, 153–212`; `config/simulation_config.py:37–44, 53–64`.

Candidates are restricted to nodes already typed `AMBULANCE_DEPOT`; configuration asks for exactly three depots and three ambulances. Initial chromosomes therefore contain the same three depot locations in different orders. Permuting a chromosome does not change its coverage fitness, so the GA has no meaningful location-selection problem to optimize. Mutation can also create duplicate depot IDs when there are no unused candidates, potentially leaving one depot unoccupied.

**Impact:** The UI's “GA best fitness” can imply a meaningful optimized deployment when candidate locations are essentially fixed. The algorithm cannot choose better non-depot locations even if the model should allow them.

### 5. Infinite / infeasible placement fitness is not handled as a distinct result
**File:** `challenges/challenge3.py:84–105, 153–212`.

If any residential node is unreachable from all candidate ambulance nodes, the nearest distance is infinity and chromosome fitness becomes infinity. The run method can still return a `best_solution`/fallback without an explicit infeasible-placement status.

**Impact:** An unreachable demand area can be hidden behind a placement result rather than surfaced as an infeasible configuration. The UI should not present this as an ordinary valid solution.

### 6. Flooding a node also advances the simulation
**File:** `backend/api/main.py:53–59`.

`POST /simulation/flood_node/{node_id}` triggers the flood and then calls `step_forward()`. One manual flood request can therefore advance the step counter, move the rescue team, trigger an additional random flood, and run scheduled risk/ambulance updates.

**Impact:** Flood action has unexpected side effects and makes deterministic flood/replanning tests hard to isolate. The 2D UI message “Routes recalculated” also masks the fact that a full simulation step occurred.

### 7. Manual node flooding counts blocked roads as floods
**File:** `core/simulation_engine.py:298–314`.

A node flood blocks all active incident edges, appends one history record per blocked edge, and increments `total_floods` by the number of blocked edges. A single physical flood at one node can count as several floods. If the node has no active edges, the function returns without recording an incident.

**Impact:** “Total floods” is not a consistent count of flood incidents. History is edge-level rather than event-level and can overstate incident count.

### 8. Manual road blocking does not consistently update simulation metrics/events
**File:** `backend/api/main.py:61–70`; `core/simulation_engine.py:280–314`.

`/simulation/block_road` appends to `flood_history` regardless of whether the road exists or was already blocked, but does not increment `total_floods`, log a flood event, or immediately refresh edge counters. `/simulation/unblock_road` changes graph connectivity but does not remove/annotate history or update any related metrics. Node flooding, random flooding, and direct road blocking therefore have different accounting semantics.

**Impact:** API state, dashboard metrics, event log, and graph can disagree until later steps; invalid/no-op requests may still be reported as successful operations.

### 9. Invalid flood node IDs can be reported as successful
**Files:** `backend/api/main.py:53–59`; `core/simulation_engine.py:298–314`.

The flood function does not validate `node_id` before scanning edges. If no incident edges match, it returns silently; the API still returns a success message and advances a simulation step. Invalid IDs may therefore be accepted as a successful flood request.

### 10. Road-block endpoints do not validate node IDs or edge existence
**File:** `backend/api/main.py:61–70`; `core/city_graph.py:140–180`.

The API passes IDs directly to graph methods. Missing edges are silently ignored by `CityGraph`, but the endpoint still returns “Blocked road” / “Unblocked road.” Invalid node IDs can also make graph adjacency access unsafe if a matching edge key exists in malformed state.

**Impact:** Clients cannot distinguish a successful mutation from a no-op, and invalid requests do not receive clear 4xx responses.

### 11. A road reopening does not restore previously skipped civilians
**File:** `challenges/challenge4.py:45–77` (mission planning), `core/city_graph.py:165–180` (unblock).

When the next civilian is unreachable, the router logs a warning and removes/skips that target while continuing the queue. Unblocking a road restores graph connectivity but does not restore skipped civilians or trigger route reconsideration.

**Impact:** A temporary flood can permanently remove a civilian from the rescue mission even after a route becomes available again.

### 12. “Mission complete” does not mean all civilians were rescued
**File:** `challenges/challenge4.py:45–77, 158–188`; `core/simulation_engine.py:239–253`.

The router can empty its target queue by skipping unreachable civilians and log mission completion. The completion meaning is therefore “no targets remain in the queue,” not necessarily “all selected civilians rescued.” The simulation's `is_complete` flag is not tied to rescue outcome.

**Impact:** Success can be overstated; unresolved civilians can disappear from pending work and metrics.

### 13. Simulation completion flag is not set by normal API stepping
**Files:** `core/simulation_engine.py:218–224, 317–330`; `backend/api/main.py:47–51`.

`step_forward()` returns when `step >= max_steps`, but it does not set `state.is_complete`. Only `run_full()` sets that flag, and the API's step endpoint never calls `run_full()`. Once step 100 is reached through the API, the state can remain `is_complete=False`; further step requests return the same step as if they had succeeded.

**Impact:** UI completion indicators and controls can be wrong, and the API can report “Stepped to 100” repeatedly despite no progress.

### 14. No per-ambulance dispatch/navigation model
**Files:** `core/simulation_engine.py` state and mission setup; `challenges/challenge3.py`; `challenges/challenge4.py`.

There is one router with one current position and one sequential civilian queue, not one route/assignment/status per ambulance. GA placement only creates a list of node IDs; it does not model available, responding, transporting, or idle vehicles.

**Impact:** It cannot accurately simulate several ambulances independently serving separate emergencies. A correct shortest path from one start node does not prove that the right ambulance was dispatched.

## B. Route Lab and 2D frontend correctness problems

### 15. Route Lab overlays routes that may have different endpoints
**File:** `frontend-2d-pygame/screens/route_lab.py:108–141`.

The selected source/destination path is computed by the frontend reference Dijkstra. The amber route is `sim.active_routes`, the backend's current rescue mission route. These may have different start and destination nodes. The screen overlays them together and can imply they are competing solutions to the same routing problem.

**Impact:** Misleading visual comparison. A fair algorithm comparison requires both algorithms to use identical endpoints, graph snapshot, direction-sensitive risk costs, and blocked-edge state.

### 16. Route Lab does not ask the backend to calculate an arbitrary route
**File:** `backend/api/main.py` (all routes); `frontend-2d-pygame/screens/route_lab.py:108–141`.

There is no API endpoint that accepts arbitrary source and destination IDs and returns a fresh backend A* path/cost. Route Lab's user-selected route is calculated by its local Dijkstra implementation, while the backend route is only the active mission route.

**Impact:** Route Lab cannot directly verify backend A* for the endpoints entered by the user. It is a reference-path viewer, not a complete backend routing test.

### 17. Route Lab validation can become stale or retain old results
**File:** `frontend-2d-pygame/screens/route_lab.py:128–135, 260–275, 308–316`.

Validation of the backend active route is refreshed when the user calculates a route and when `on_state_updated()` sees both an old reference result and a non-empty active route. If the route disappears, the condition does not clear `state.route_validation`; the results panel can continue showing validation for an earlier path. The displayed reference path and breakdown also are not automatically recalculated after graph costs/blockages change.

**Impact:** UI can display stale validity/optimality after floods or risk updates.

### 18. Path validation conflates “unreachable” with “invalid path”
**File:** `frontend-2d-pygame/algorithms/reference_dijkstra.py:146–185`.

`validate_path()` reports any empty path as invalid. But when the destination is unreachable, an empty path is the expected result. The UI/diagnostics should separate “no feasible path exists” from “algorithm returned a malformed route.”

**Impact:** A legitimate disconnected-graph result is reported as an algorithm error, confusing flood diagnosis.

### 19. Path validation can mishandle malformed paths before reporting clean errors
**File:** `frontend-2d-pygame/algorithms/reference_dijkstra.py:187–240`.

The validator computes canonical edge keys and later cost using path IDs after merely appending an issue for nonexistent nodes. Malformed values or mixed/unexpected ID types can raise exceptions during `min(a,b)` or dictionary indexing instead of returning a validation report. It also treats a one-node path as valid without checking that it represents the intended source/target pair.

**Impact:** Diagnostics may crash or accept an endpoint-mismatched zero-hop route if caller context is wrong.

### 20. Ambulance Center reachability results are snapshots, not live per-ambulance route assignments
**File:** `frontend-2d-pygame/screens/ambulance.py:47–78`.

The screen computes reachability from each current placement to each civilian when validation runs. It does not represent which ambulance is assigned, each vehicle's actual moving position, or whether the route will remain valid after later changes. It calculates distances, but these are not dispatch assignments.

**Impact:** “Can reach” may be read as “will respond”; coverage becomes stale after graph/risk/placement changes until validation is rerun.

### 21. Diagnostics screen contains stale/incorrect audit claims for this ZIP
**File:** `frontend-2d-pygame/screens/diagnostics.py:239–247, 249–332`.

The screen says Python A* is correct, despite the A* heuristic issue above. It also says the router starts at `hospitals[0]`, but this ZIP's current `simulation_engine.py:187–200` selects the nearest placed ambulance to the first civilian. It includes claims about React/3D pathfinding, which are out of scope and do not diagnose the current 2D/backend behavior.

**Impact:** The built-in diagnostics UI itself gives false reassurance and can direct debugging toward a defect that has already changed in the current backend.

### 22. `validate_path()` optimality means optimal only for the path's own endpoints
**File:** `frontend-2d-pygame/algorithms/reference_dijkstra.py:222–240`.

The optimality check runs Dijkstra from `path[0]` to `path[-1]`; it does not verify that these endpoints are the intended mission source and target. A route can be optimal between the wrong endpoints and still pass.

**Impact:** It cannot prove the active route is serving the correct civilian/mission without separate endpoint checks.

### 23. Background poller can overwrite a newer mutation response with an older snapshot
**Files:** `frontend-2d-pygame/backend_client/api_client.py:105–143`; `frontend-2d-pygame/app/application.py:122–140, 233–245`.

The background poller and async mutation operations both enqueue state payloads, but snapshots carry no server-side version or sequence number. Responses can arrive in a different order than requests. An older `/state` poll that finishes after a mutation response can overwrite the newer state in the UI.

**Impact:** Frontend may briefly show a pre-flood route, old step count, or old metrics after reporting the operation succeeded.

### 24. Frontend “thread-safe client” uses a shared requests Session without using its lock
**File:** `frontend-2d-pygame/backend_client/api_client.py:26–31, 38–86`.

`CityMindClient` creates a `requests.Session` and a `_lock`, but request methods do not acquire the lock. Polling and mutation requests can use the same session concurrently. The docstring's thread-safe claim is not enforced.

**Impact:** Concurrency behavior is not guaranteed; session-level state/cookies/connection reuse can race. Prefer a session per thread/request or serialize access.

### 25. Frontend route selection can preserve old state after failed/unreachable calculation
**File:** `frontend-2d-pygame/screens/route_lab.py` (route run/clear/result state).

The screen updates result fields on successful calculation, but error/unreachable paths need to consistently clear all prior route overlays and validation state. Otherwise an error message can coexist with old visual output. This should be regression-tested for invalid source, invalid destination, unreachable pair, then valid pair.

**Impact:** The screen can visually show a previous route when the latest calculation did not produce one.

## C. Graph and algorithm issues

### 26. `unblock_road()` does not notify route observers
**File:** `core/city_graph.py:165–180`.

Blocking a road notifies the router; unblocking does not. The router also does not maintain/retry skipped targets when connectivity is restored.

**Impact:** Route planning is event-driven only for one direction of graph change. Restoring connectivity cannot trigger a recovery policy.

### 27. Node `accessible` flag is not kept in sync with actual graph connectivity
**File:** `core/city_graph.py:25, 310–312`; graph mutation methods.

`Node.accessible` is serialized, but road blocking/unblocking never recalculates it. `find_disconnected_nodes()` exists separately and is not used to update node accessibility or `metrics.disconnected_nodes` in the normal step path.

**Impact:** Any frontend feature trusting `accessible` can show a node as accessible despite having no active neighbors, or vice versa. The disconnected-nodes metric can remain stale/default.

### 28. `add_edge()` has no endpoint validation
**File:** `core/city_graph.py:130–138`.

The method canonicalizes the edge key but directly indexes `self.adj[id_a]` and `self.adj[id_b]`. Invalid IDs raise `KeyError`; self-loops are not rejected explicitly.

**Impact:** Malformed graph-building or restore data can crash graph construction rather than return a controlled error.

### 29. Road redundancy check does not implement the claimed general edge-disjoint-path guarantee robustly
**File:** `challenges/challenge2.py:193–241`.

`ensure_hospital_depot_redundancy()` finds one BFS path, excludes its edges, and searches for another. If none exists, it adds candidate edges while excluding only the first path's edge set. This can find two edge-disjoint paths if successful, but it does not calculate max-flow/min-cut and the function's “Menger theorem” comment overstates the algorithmic guarantee. Also, inspect `build_road_network()` call path to ensure this verifier is actually invoked; a helper that is never called does not enforce redundancy.

**Impact:** Do not assume every generated road network is protected against a single edge failure solely because the helper exists.

### 30. Diagonal road edges allow corner-cutting through blocked/empty cells
**File:** `challenges/challenge2.py:39–47`.

Diagonal candidate edges are added between diagonal grid cells without checking whether either adjacent orthogonal cell is passable. In a grid-routing model where cells represent obstacles or floodable terrain, this permits diagonal movement through corners that would be physically blocked. If the intended model treats every node as a traversable road junction regardless of zone, this is a modeling limitation rather than a runtime bug; the intended rule should be explicit.

### 31. Direction-dependent edge costs are easy to misinterpret as undirected costs
**Files:** `core/city_graph.py:62–72, 211–220`; `frontend-2d-pygame/algorithms/reference_dijkstra.py:43–69`.

The graph is structurally undirected, but effective cost depends on the destination node's risk. So cost A→B can differ from B→A. The reference Dijkstra mirrors this behavior, but API edge serialization only returns base `cost`, not both directional effective costs. Any screen or future client treating `cost` as the actual traversal cost will calculate incorrect values.

**Impact:** Route calculations can disagree across components unless each computes directional effective cost from the destination risk consistently.

## D. Simulation metrics and state semantics

### 32. Reroute counts can be inflated by a single node flood
**Files:** `core/city_graph.py:140–159`; `challenges/challenge4.py:133–145`; `core/simulation_engine.py:308–314`.

A node flood blocks each incident edge one at a time. Every blocked edge on the active path can invoke the observer and replan again. `total_reroutes` counts replan triggers, not flood incidents or distinct successful route changes.

**Impact:** A single flood can inflate reroute metrics and do repeated unnecessary searches. Batch the closures and replan once after the graph mutation.

### 33. Rescue metrics are derived by scanning free-form log strings
**File:** `core/simulation_engine.py:239–253`.

The engine detects “CIVILIAN REACHED”, “WARNING”, “REPLANNING”, and “MISSION COMPLETE” by substring matching router log messages. Metrics correctness depends on exact message text and on the log being drained at the right time. `civilians_unreachable` can count warning events rather than unique civilians, and router logs can be replayed or missed if lifecycle changes.

**Impact:** Counts can diverge from actual unique rescue outcomes. Use structured event types with civilian IDs and idempotent counters.

### 34. `avg_response_time` and `worst_response_time` are never populated by the shown rescue flow
**File:** `core/event_manager.py:41–57`; `core/simulation_engine.py:231–253`.

The metrics class supports `record_response_time()`, but the mission step logic does not call it when a civilian is reached. Response-time KPIs can remain zero despite rescues.

**Impact:** Dashboard response-time metrics are not meaningful unless another caller records them.

### 35. `disconnected_nodes` metric is not refreshed during normal steps
**Files:** `core/event_manager.py:44`; `core/city_graph.py:310–312`; `core/simulation_engine.py:280–282`.

The step updates active/blocked edge counts but does not recompute `metrics.disconnected_nodes` from the graph.

**Impact:** The displayed disconnected-node count may remain zero/stale after floods.

### 36. `is_complete` and rescue status are separate but not clearly represented
**Files:** `core/simulation_engine.py:31–33, 218–224, 317–330`; `challenges/challenge4.py:180–188`.

The API state has a simulation-step completion flag, while router mission completion is only a log entry. The frontend can have no remaining route but the simulation still runs; conversely it can reach max steps while `is_complete` remains false. There is no explicit `mission_status` or unresolved-civilian set.

**Impact:** The UI cannot reliably distinguish mission complete, mission failed/partial, and simulation time exhausted.

### 37. Active route only stores the remaining path
**File:** `core/simulation_engine.py:231–237`; `challenges/challenge4.py:158–169`.

Each movement pops the departed node and writes the remaining route to `state.active_routes`. The original plan and traversed path are not preserved, and route cost/graph version are not stored.

**Impact:** After a flood or reroute, it is difficult to tell whether the original plan was suboptimal, the graph changed, or the team deviated. The UI must treat `active_routes` as a remaining path, not full journey history.

### 38. Risk penalty is not a flood/road-safety model
**Files:** `config/simulation_config.py:17–23`; `core/city_graph.py:62–72`.

Risk multiplies destination traversal cost, while flooding blocks edges. The model does not represent flood depth, vehicle clearance, road capacity, travel speed, or ambulance-specific restrictions. A high-risk road remains traversable at a penalty unless separately blocked.

**Impact:** The route may be optimal for the implemented scalar cost but not operationally safe under realistic flood/ambulance conditions. Clarify whether “risk” means crime risk, flood hazard, delay, or all of them; they should not be conflated.

## E. Data quality, reproducibility, API concurrency, and maintainability

### 39. API uses a mutable module-global simulation without synchronization
**File:** `backend/api/main.py:22–24, 39–70`.

All endpoints share global `sim`, and no lock serializes step/flood/block/unblock/reset operations. Reset replaces the global object while another request may be reading or mutating the previous object. FastAPI can serve requests concurrently.

**Impact:** Concurrent requests can return inconsistent snapshots or apply changes to different simulation instances. Add a service object and synchronize mutations/read snapshots.

### 40. Reset and `/start` silently discard all prior in-memory state
**File:** `backend/api/main.py:39–45`.

Both routes create a brand-new seeded simulation. That is valid reset behavior, but it is not coordinated with in-flight requests, and the API doesn't include a simulation/version ID for clients to detect a reset boundary.

**Impact:** In-flight poll results from the old simulation can arrive after reset and overwrite the new state in the 2D frontend.

### 41. API lacks a dedicated route-calculation/diagnostic endpoint
**File:** `backend/api/main.py`.

The API exposes state, graph, step, flood, block, unblock, and reset only. It cannot calculate a requested source→destination path without starting/altering the active mission or doing local frontend routing.

**Impact:** The 2D frontend cannot ask the backend for arbitrary A* routes or compare backend route cost/path with reference Dijkstra on the same endpoints.

### 42. CORS allows only two localhost origins
**File:** `backend/api/main.py:14–20`.

CORS is hard-coded to `localhost:5173` and `127.0.0.1:5173`. The Pygame client is not subject to browser CORS, but a browser frontend served on a different port/host will fail cross-origin requests unless configured.

**Impact:** Local deployment on a different port or remote/dev host can fail despite backend being healthy. This is deployment configuration, not a routing defect.

### 43. Seed handling treats seed `0` as “no seed”
**File:** `core/simulation_engine.py:69–73`.

`self._seed = seed or SimConfig.SEED` means a valid integer seed of zero is replaced by `SimConfig.SEED`. Use an explicit `seed is not None` check.

**Impact:** Users cannot reproduce a run with seed zero as requested. In addition, use of module-global `random.seed()` means separate Simulation instances in the same process share/reset global RNG state, which is unsafe if multiple simulations are created concurrently.

### 44. CSP solver silently swallows every exception
**File:** `challenges/challenge1.py:44–62`.

Each of 20 layout attempts catches `Exception` and discards the exception details. If an actual implementation error occurs, it is treated like a random constraint failure and eventually becomes a generic layout failure.

**Impact:** Real defects are difficult to diagnose and may look nondeterministic. Log the exception/traceback and distinguish expected infeasible layouts from programming errors.

### 45. Risk predictions are trained against synthetic rule-generated labels
**File:** `challenges/challenge5.py:109–145` and pipeline code.

The decision tree dataset labels are generated from rules based on the same graph features/clustering, rather than observed crime incidents. The trained model largely learns the synthetic rule used to label the data, not validated real-world crime risk.

**Impact:** “Crime prediction” is a simulation/demo heuristic, not an empirically validated forecast. Scores should not be presented as real crime likelihood without real labeled data, validation metrics, and calibration.

### 46. K-means/decision-tree output lacks a demonstrated validation score
**File:** `challenges/challenge5.py`.

The pipeline builds clusters and a decision tree, but the project does not appear to hold out labeled observations and report accuracy/precision/recall or calibration against an independent dataset. Rule-derived labels make ordinary train accuracy especially uninformative.

**Impact:** There is no evidence in the current app that risk classification is predictive or stable. Treat it as generated scenario logic until validated.

### 47. Police deployment is risk-ranked placement, not a movement/coverage simulation
**Files:** `challenges/challenge5.py` deployment function; `core/simulation_engine.py:142–149, 263–278`; `frontend-2d-pygame/screens/police.py`.

The backend calculates deployment nodes/scores and replaces the deployment list after risk updates, but does not model officers moving, availability, patrol coverage, or travel routes. Reassignment is an instantaneous placement update.

**Impact:** The UI can imply active police deployment while representing only static ranking/placement. Label this clearly or model unit state and movement.

### 48. Graph node accessibility/population semantics may be stale or synthetic
**Files:** `core/city_graph.py:21–26, 288–298`.

`accessible` defaults true and is not recomputed after road blocking. Population values are generated from configured ranges and node types; they are synthetic. If UI features imply actual accessible status or actual population, that interpretation is unsupported by current updates/data.

**Impact:** Some map indicators can be semantically misleading even if they render correctly.

### 49. API success messages do not consistently verify mutation outcome
**File:** `backend/api/main.py:61–70`; graph methods silently return on missing/already blocked/already open edges.

The block/unblock endpoints always return success text after calling methods, regardless of whether a state change occurred.

**Impact:** UI logs can say a road was blocked/unblocked when the graph did not change. Mutation methods should return changed/no-op/invalid outcomes.

### 50. Long-lived event/log state is unbounded in memory
**Files:** `core/event_manager.py:123, 168–170`; `core/simulation_engine.py` router log lifecycle.

`event_history` appends every event without a retention limit. Long-lived API sessions or repeated resets create new managers, but a long single simulation or future higher-frequency event source can grow the list indefinitely. Router logs are drained per step, but events are not bounded.

**Impact:** Memory usage can grow over long-running sessions; consider bounded retention or persistent log storage.

## F. Test coverage gaps

The existing **29 tests pass**, but the current suite does not establish correctness for these critical scenarios:

1. A* differential optimality vs Dijkstra over generated graphs with 0.8 residential edges, 1.4 diagonal edges, asymmetric risk multipliers, and blocked edges.
2. Risk update changes route optimality without any road closure.
3. Multi-edge node flood triggers one intended replan and counts one flood incident.
4. Unreachable civilian becomes reachable after unblocking and is retried.
5. Repositioning during an active mission does not desynchronize the displayed vehicle and router.
6. GA placement with unreachable residential demand explicitly reports infeasibility; mutation never silently duplicates required placements.
7. API invalid node/edge IDs return 4xx and do not advance time or change counters.
8. Flood endpoint does not unexpectedly step time (or the behavior is explicitly tested/documented).
9. Concurrent reset vs step/flood and poll response ordering cannot restore stale state.
10. `is_complete` becomes true at the correct terminal condition and step endpoint does not claim progress when no step happened.
11. Metrics match unique rescued/unreachable civilians and response times are recorded.
12. Route Lab clears stale result/validation on unreachable inputs, graph changes, and route disappearance.
13. Validation checks intended endpoints and cleanly distinguishes unreachable from malformed route.
14. `accessible` and `disconnected_nodes` update after edge mutations.
15. Diagnostics screen assertions reflect the current backend rather than stale hard-coded notes.

## Recommended fix order

1. Fix A* optimality and verify against reference Dijkstra.
2. Make flood operations atomic, validate IDs/edges, separate flooding from stepping, and normalize event/counter semantics.
3. Correct mission lifecycle: track rescued/pending/unreachable/retryable civilians and true completion status.
4. Separate ambulance placement, per-vehicle dispatch, and navigation; never overwrite active vehicle positions as a side effect of GA placement.
5. Trigger replanning on risk-cost changes and road unblocking where policy requires it.
6. Add a backend arbitrary-route endpoint and make Route Lab compare identical endpoints against the backend.
7. Fix state synchronization, API locking/versioning, stale frontend validations, and misleading diagnostics text.
8. Make metrics structured and accurate; validate risk model claims and clarify synthetic data semantics.
9. Add the missing regression tests before considering the system route-correct.
