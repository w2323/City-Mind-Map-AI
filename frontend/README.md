# CityMind React 3D operations center

React and Pygame share the existing FastAPI simulation. Dispatch, road restrictions, medical-center placement, police, helicopters and optimization execute in Python. React displays snapshots and animates vehicles between reported positions.

## Run

After dependencies are installed, run `./run_3d.ps1` from the repository root. It starts the API if needed and the React dev server. An already-running shared API is reused. Alternatively use the two terminals below.

Start the backend from the repository root:

```powershell
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8000. Override the backend with `CITYMIND_BACKEND_URL`, or use `VITE_API_BASE_URL` for a separately hosted API and configure its allowed origins.

Use one backend worker. Both frontends see the same city; stepping or restarting either changes the shared simulation.

## Workflows

| Pygame functionality | React control |
| --- | --- |
| Dispatch, emergency queue, fleet | Dispatch; select a sector or enter its label |
| Air rescue, landing buildings, relocation, fuel | Dispatch; air rescue unlocks without road access |
| Medical coverage and center construction | Dispatch; build a current recommended site |
| Route Lab | Route Lab; A*, independent Dijkstra, normal/ambulance modes, road costs and 3D paths |
| Automatic medical/crime/road events | City Events; switches and probability sliders |
| Police reports, patrols, medical help, station planning, comparison | Police |
| Road block/unblock, eight Gate levels, preview, history | Disasters; select a road or gate center |
| GA start/pause/reset, candidate routes, fleet validation | Ambulance |
| Normal, crime, population, medical and police layers | City Map / Heatmap |
| Sector labels, IDs, road costs, traffic, comparison views | City Map |
| Network health and CSV | Dashboard |
| Graph/fleet diagnostics, all metrics, filtered event history | Diagnostics |

The left sidebar matches the Pygame workspaces. Number keys 1–9 select those workspaces; Escape closes the active tool panel. Simulation Play/Pause, Step and New City remain in the sidebar.

Grid references are visible by default. Numbers run horizontally and letters vertically: A2 is beside A1, and B1 is below A1. The renderer transposes the displayed coordinates while preserving the Python model's sector IDs and labels. Map overview aligns the grid squarely; orbit and walking retain free camera movement. Border references are drawn on all four sides using a shared texture atlas.

Traffic signals appear at suitable three/four-way intersections. Red/amber/green phases alternate between crossing directions, and background traffic stops at red or amber. Signals are a presentation layer; emergency vehicle movement remains controlled by the Python simulation. Turn them off independently under City Map → Traffic Signals.

Operator commands are serialized behind any in-flight simulation step. Playback no longer disables police/dispatch controls on every tick or silently drops clicks. Probability sliders update locally while dragged and send one setting when released. Police station planning pauses this browser's playback to keep the recommendations fresh, offers a choice of proposed sites, and explains missing prerequisites. Genuine restrictions such as mandatory injury care, full helicopter fuel, stale plans, and a completed simulation remain visible. Action confirmations appear after successful backend responses. Long report/event lists load older entries on demand to keep live panels responsive.

Police comparison defaults to 40 matched steps and 8 reports; both limits and the replay seed can be adjusted. It runs against a frozen snapshot without disabling other police actions. The comparison request allows 90 seconds, station planning 60 seconds, and city creation 45 seconds instead of applying the generic short request timeout to long computations.

## Camera and graphics

- **Orbit city:** left-drag rotates around the city, right-drag pans, and the wheel zooms. Rotation is unrestricted around the vertical axis. The camera uses a normal upright Y axis.
- **Map overview:** an overhead starting position with the same orbit controls.
- **Walk streets:** drag to look, W/A/S/D to walk, Shift to move faster, Q/E to change height, or arrow keys to look. Typing into a form never moves the camera. At street height, building footprints stop movement through buildings.
- **Focus selected:** inspect the selected sector deliberately. Selecting a sector and polling simulation state do not reset the camera.
- **Reset:** return to the full city. Graphics quality is available under City Map or Ambulance: Economy reduces resolution and removes background traffic/shadows; Balanced uses native 1× resolution and cached shadows; High increases resolution.

Buildings, facade windows, parks, trees, street lamps, paving, road surfaces and markings use instanced batches. The scene no longer loads the large repeated GLB models. Buildings stand inside blocks beside the road intersections, leaving routes free for vehicles and walking. Static geometry and shadow maps are reused across simulation updates; unchanged polls preserve React references. Sector/road labels share a texture atlas. Vehicle positions and operational outcomes continue to come from Python.

Red markers identify emergencies; orange rings identify sectors without medical access when coverage is enabled. Roof pads identify helicopter bases. Empty sectors appear as selectable pocket parks. Road colors reflect closures, Gate restrictions and selected paths.

Route results clear when the city revision changes. Route Lab pauses this browser's playback; another frontend can still change the city. Invalid operations show backend errors until dismissed or the next action. Construction follows backend recommendations.

## Validation

```powershell
npm run build
node --test src/engine/*.test.js
npm run test:e2e
```

Playwright starts a separate backend on 8101 and Vite on 5175 and uses installed Microsoft Edge. Tests exercise the real API. Manual-incident regression tests explicitly disable automatic events to isolate assertions. Screenshots are written to `e2e-artifacts`.

`node tools/profile-scene.mjs` measures draw calls/FPS and saves a screenshot of the running app. The before/after samples in `e2e-artifacts/scene-before.json` and `scene-final.json` use the same 1440×1000 headless Edge software renderer: approximately 5,700 → 98 draw calls per frame and 12 → 60 FPS. These are local comparison measurements, not a guarantee for every GPU. The camera regression test caps default rendering at 250 draw calls and verifies orbit, pan, walking, mouse look and workspace/layer navigation.
