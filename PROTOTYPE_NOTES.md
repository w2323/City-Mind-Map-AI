Sector terminology and unchanged mechanics: [SECTOR_VIEW_GUIDE.md](SECTOR_VIEW_GUIDE.md).

Current bank/police spacing and crime heatmap rules: [CRIME_HEATMAP_GUIDE.md](CRIME_HEATMAP_GUIDE.md).

Police stations, moving patrols, crime reporting, joint medical response and deployment comparisons: [POLICE_OPERATIONS_GUIDE.md](POLICE_OPERATIONS_GUIDE.md).

Road restrictions and the current disaster workflow: [DISASTER_CONTROLS_GUIDE.md](DISASTER_CONTROLS_GUIDE.md).

Current medical-center and helicopter behavior is documented in [RESCUE_OPERATIONS_GUIDE.md](RESCUE_OPERATIONS_GUIDE.md). Helicopter bases are non-hospital buildings; air missions deliver directly to a safe hospital and then return to a safe building.

Current UI and ambulance behavior: [frontend-2d-pygame/DISPATCH_WORKSPACE.md](frontend-2d-pygame/DISPATCH_WORKSPACE.md). The explicit depot-fleet workflow supersedes earlier descriptions of preset civilian missions and GA redeployment.

# CityMind functional prototype

Run commands from the inner project folder containing `main.py`, `core/`, `backend/`, and `frontend/`.

## Run

Python 3.11+ and Node 24 are recommended. Use a virtual environment for Python dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the localhost URL printed by Vite. The dev and preview servers proxy `/api` to Python. For another backend address set `CITYMIND_BACKEND_URL` before starting Vite. For a separately hosted build, set `VITE_API_BASE_URL` at build time or configure a reverse proxy for `/api`. Set `CITYMIND_ALLOWED_ORIGINS` to a comma-separated origin allowlist when needed.

The Pygame frontend uses the same API:

```powershell
python frontend-2d-pygame/main.py
```

The CLI also uses the shared Python algorithms:

```powershell
python main.py --seed 42 --steps 100 --json
```

Use one API worker. The model is shared in process, is not persisted, and resets when the server restarts. Both interfaces can observe and change the same city. This is a local prototype without account authentication or production deployment infrastructure; bind to loopback for local use.

## Backend ownership

`config/simulation_config.py` owns simulation settings. `core/analytics.py` computes coverage, connectivity, risk health, road views, and ambulance routes. `/state` contains graph, analysis, events, config, revision, simulation identity, and optimization status in one snapshot. React polls this snapshot every second and accepts mutation snapshots immediately. State reads and writes are serialized; expensive GA jobs operate on frozen graphs outside that lock.

The frontend no longer invents fitness/progress, population, percentage metrics, risk-factor weights, or road/ambulance algorithm results. Visual styling, geometry scale, animation timing, and decorative traffic remain presentation code. Traffic cars are illustrative, not modeled traffic measurements. Each comparison viewport has its own animation pool.

The analytical response-budget metric (used by React and the older diagnostics) is the fraction of residential nodes reachable from a deployed ambulance within `COVERAGE_COST_LIMIT` risk-weighted road cost. Pygame Dispatch separately reports all-node road reachability from medical centers. Ambulance radii and their controls have been removed; operational reachability and out-of-service counts are in `dispatch_summary`. Costs have no physical meter/minute conversion. Rescue response measurements use simulation steps. The risk health index weights LOW=1 and MEDIUM=`MEDIUM_RISK_HEALTH_WEIGHT`; HIGH contributes zero. Connectivity reports the largest component's share of all nodes, plus explicit component and bridge counts.

The live crime heatmap uses configured bank opportunity, industrial/residential interfaces, dense residential neighborhoods and simulation crime reports. Its scores are not measured probabilities. The original two-feature K-Means/decision-tree cost preparation remains before the medical GA to preserve existing medical placements for each seed; it no longer drives the published crime map. Legacy risk field names remain for API compatibility.

“All roads” shows candidate grid roads, including roads not built in the active model. “Optimized (MST)” shows a minimum spanning forest of currently open built roads. “Optimized (2-connected)” shows the live built network; initial construction removes all bridges. Floods can break that property, and health checks reflect this. Comparison views do not change the simulation topology. Layout hospital proximity remains a soft modeling constraint in the existing CSP solver; industrial/hospital separation is reported as measured, rather than assumed satisfied.

Play advances the actual Python simulation; Pause stops playback. Start/Restart resets the model. The GA controls run bounded, sequential optimization runs in one background worker. Progress comes from evaluated generations, Resume continues a paused job, and Reset cancels it. A flood, road change, simulation step, or restart cancels work based on stale graph data. Completed positions are committed only to the matching simulation revision. A completed job can be infeasible on a disconnected graph; `feasible` is false. Medical-center GA fitness includes an unreachable-node penalty; legacy ambulance fitness can be `null` for unreachable targets. Metrics export downloads the current backend CSV.

## API

Existing Pygame endpoints are preserved: `GET /`, `/state`, `/graph`; `POST /start`, `/simulation/reset`, `/simulation/step`, `/simulation/flood_node/{id}`, `/simulation/block_road/{a}/{b}`, `/simulation/unblock_road/{a}/{b}`, `/simulation/route`.

- Optional reset body: `{"seed": 0}`. Omitting the seed generates a new city; explicit seeds reproduce runs.
- Route body: `{"src": 0, "dst": 1}`. Unreachable routes return `reachable: false`, an empty path, and `path_cost: null`.
- `GET /simulation/ambulance_routes/{target}` returns risk-aware candidate routes and the best reachable deployed ambulance.
- `POST /simulation/optimization/start` accepts `{"runs": 1}` up to `OPTIMIZATION_MAX_RUNS`; it also resumes a paused job.
- `POST /simulation/optimization/pause` and `/simulation/optimization/reset` control the active job.
- `GET /metrics/export` returns a CSV attachment.

Input models reject unexpected fields, string/bool route IDs, and excessive optimization counts. Mutating browser requests from unapproved origins are rejected before model access. Native Pygame requests do not require Origin headers. Non-finite costs and metrics use JSON null. Temporary route calculations do not register observers. Custom road costs must be finite and positive, and A* derives a valid heuristic bound from live roads.

## Verification

```powershell
python -m pytest tests frontend-2d-pygame/tests -q
cd frontend
npm run build
npm audit
```

For headless Pygame render tests set `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`.

The test suite covers API validation and serialization, concurrent steps, flood idempotency and restoration, observer retention, CSV output, ambulance ranking, real GA completion, pause/cancellation on mutation, co-located rescues, custom-cost optimal routing, deterministic seeds, and existing Pygame rendering/routing regressions. This does not certify every possible state or replace load testing and deployment hardening.

## Earlier baseline results (before explicit fleet and air rescue)

- 68 Python API, algorithm, integration, and headless Pygame tests passed.
- One headless Edge end-to-end test passed: real playback, GA completion, CSV download, and switching between single and comparison views, with no JavaScript page errors.
- A seeded 100-step CLI run completed in about 3.2 seconds of model time, including 27 flood events and 20 redeployments. It correctly reported four rescues and one unreachable civilian rather than claiming total success.
- React production build passed. Vite reports a large 3D bundle warning; further code splitting is a performance follow-up.
- npm audit reported zero known vulnerabilities after compatible dependency updates. This is an npm dependency audit, not a guarantee that all vulnerabilities in every dependency or deployment are absent.

Run the browser smoke test using `npm run test:e2e` in `frontend/`. The test starts isolated servers on 8101 and 5175, sets the test origin allowlist explicitly, and uses installed Microsoft Edge. For other platforms install a Playwright browser and adjust the launch channel in `playwright.config.js`.
