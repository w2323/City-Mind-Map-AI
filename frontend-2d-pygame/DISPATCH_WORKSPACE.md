# Python dispatch workspace

The Python/Pygame workspace has a city map, sector labels, live ambulance and police positions, helicopter landing markers, and operational controls. All nine tool destinations remain available. See [RESCUE_OPERATIONS_GUIDE.md](../RESCUE_OPERATIONS_GUIDE.md) for the current outage and relocation rules.

## Requested behavior

- The city starts with **zero emergencies**. There are no randomly assigned civilian targets or preset C markers.
- Every medical center starts with its own ambulance, with a stable ID, position, service status and route.
- Ambulance radius sliders, circles, stored radii and the radius endpoint have been removed. Gate and crime-area radii remain available.
- Road coverage describes actual connectivity. Dispatch excludes busy and out-of-service units.
- Type a node such as C4 into the emergency field and press GO or Enter. Clicking a grid node fills the same field; it does not create an emergency until GO is pressed.
- Python chooses the **operational available ambulance with the lowest reachable, risk-weighted road cost**. It honors road closures without a radius restriction.
- GO starts playback so the ambulance travels along its actual route. It resolves the emergency on arrival, then returns to its depot. It becomes available again only on returning. Automatically started playback stops when all units have returned.
- Multiple ambulances can respond concurrently. If no available unit can reach a target, the request fails clearly and does not create a fake assignment. Duplicate active emergencies at one node are rejected.
- If a route becomes blocked, the unit waits or finds a new route. Blocked assignments are retained and retried when connectivity returns.
- Each session has a bounded 1,000-record emergency history and the existing simulation step limit; New City starts a fresh session.

## How this fits the existing algorithms

The project previously used GA staging positions plus a separate single rescue team with a preset civilian list. That model could not represent three independent ambulances with separate availability. `core/ambulance_fleet.py` now handles explicit multi-unit dispatch using the shared graph and A* implementation. `core/simulation_engine.py` integrates it with simulation steps, floods, risk updates and metrics.

The existing CSP layout, MST/redundant road construction, crime-risk model, police placement, GA controls, route laboratory, flood/road controls, exports and diagnostics remain available. GA results are now **staging recommendations** under `optimized_placements`; they never teleport the operational depot fleet. The legacy router snapshot is a compatibility view of the leading active fleet journey, while `fleet` and `emergencies` expose the full multi-unit state.

The shared API and CLI also start idle. React continues receiving the compatible state envelope. The visual redesign targets the Python frontend.

## Backend endpoints

- `POST /simulation/emergencies` with `{"node":"C4"}` assigns the nearest available reachable unit and returns an updated state snapshot.
- `POST /simulation/helicopter/relocate` requests a fuel-budgeted flight from an exposed helipad to a safe, ambulance-accessible landing spot.
- `GET /state` includes `fleet`, `emergencies`, `dispatch_summary`, and `optimized_placements`.
- Existing lifecycle, graph, route, flood, block/unblock, optimization, and export endpoints remain available.

## Run

From the inner project folder containing `core`, `backend` and `frontend-2d-pygame`:

```powershell
python frontend-2d-pygame/main.py --auto-backend
```

Restart any previously running backend so it loads the fleet endpoints and idle startup behavior. The Python UI opens directly on Dispatch. Space pauses/resumes, N advances one step, 1–9 navigate the tools, and F1 opens help.

## Verification

- Backend and desktop regression tests cover nearest-unit selection, busy/out-of-service exclusion, duplicate/unreachable requests, retained assignments, recovery, arrival, physical helicopter relocation, direct hospital delivery, return to a building base and fuel charges for all flight legs.
- A live local API/Pygame smoke test drives the actual SDL event loop: types an emergency sector, clicks GO, verifies the nearest unit, and observes arrival and return.
- The live test also verified route comparison, GA completion, CSV export and all nine screen renders. UI checks use an offscreen SDL driver rather than a visible desktop window.
- Screenshots are in `frontend-2d-pygame/artifacts/`; `1_dashboard.png` shows idle startup and `live_dispatch.png` shows a real test assignment.

```powershell
python -m pytest tests frontend-2d-pygame/tests -q
python frontend-2d-pygame/tools/render_screens.py
python frontend-2d-pygame/tools/live_smoke.py
```
