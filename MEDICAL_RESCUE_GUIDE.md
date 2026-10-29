# Medical coverage and helicopter rescue

The Python backend owns facility placement, coverage, notifications, dispatch,
helicopter fuel, building bases, hospital delivery and safe return. Pygame displays this
state and sends operator actions. All nine existing workspace screens remain.

## What changed and why

- **Medical centers have a reason to be there.** A genetic algorithm searches
  eligible city plots, prioritizing the number of road-reachable nodes, then
  average and worst response cost. Six centers are created by default, matching
  the existing hospital count, with one ambulance at each. It preserves school,
  industrial, and power-plant plots and relocates displaced residential zoning.
- **Coverage follows actual roads.** After closures, restoration, or
  risk changes, the backend recalculates coverage. Ambulance radii and their
  controls have been removed; dispatch uses road cost and operational availability.
- **Cutoffs produce useful advice.** An automatic coverage notice lists every
  node newly cut off from all medical centers. For each unserved connected area,
  the backend recommends the node with the lowest mean road cost to that area.
  The largest coverage gain is shown first. Opening the recommended center is an
  explicit operator action that creates a facility and ambulance in the model;
  it does not repair roads. Existing centers and vehicles never teleport when
  later optimization runs propose sites.
- **Helicopters fill a specific gap.** The rescue button unlocks for a selected
  node only when no medical center has a road route to it. Busy ambulances alone
  do not qualify. The helicopter starts at a road-served non-hospital building
  chosen for central access. Five additional building pads spread across the city.
- **Fuel is an actual resource.** Default capacity is 100 units and fuel starts
  full. Every grid cell flown costs one unit, including return and diversion
  flights. The backend rejects launches without pickup, hospital delivery and return fuel. It
  checks the 20% low-fuel threshold and preserves a five-unit margin above fuel
  needed to complete care and reach a safe building. Refueling requires landing.
- **Hospitals receive patients; buildings host helicopter bases.** The sequence
  is building → emergency → nearest safe hospital → closest safe building.
  Optional base sectors can be edited at runtime; hospitals and empty sectors
  are rejected as base locations. The patient is counted once, on physical
  arrival at the hospital. The helicopter then flies empty to its closest safe
  building. If a Gate covers its occupied base, the assistant relocation button
  appears. It selects the closest safe building, never a hospital. If all hospitals
  become unsafe during flight, the patient stays aboard at an emergency building
  landing until hospital delivery can resume.

Fuel safety applies to this distance-based simulation. It does not model wind,
weather, terrain suitability, loading fuel, or real aircraft certification.
Construction is immediate in the prototype. Sites, costs, fuel, and time use
model units. A genetic algorithm produces a good placement without proving a
global optimum. The rescue horizon extends while a mission is still active.

## Demonstration for the jury

1. Start the Python API and Pygame from the project directory:

   ```powershell
   python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
   ```

   In another terminal:

   ```powershell
   python frontend-2d-pygame/main.py
   ```

2. In Dispatch, explain that the medical centers were chosen by road access.
   Each has its own ambulance. There are no radius sliders or preset emergencies.
3. Enter an accessible node and press **GO**. The nearest available ambulance
   follows an open route, resolves the emergency, and returns to its center.
4. In Disasters, select and block each road link incident to a non-center node such as **O15**. The coverage notice
   lists affected nodes and recommends an additional center. Opening a center
   is optional; leave the node unserved to demonstrate air rescue.
5. Return to Dispatch, enter that node, and show that **HELICOPTER RESCUE** is now
   enabled. GO explains why an ambulance cannot reach it.
6. Open **LANDING SITES** to set comma-separated grid labels. The backend rejects
   hospitals, empty sectors and cut-off sites. Start the helicopter rescue and
   show fuel decreasing during pickup, hospital delivery and final building return.
   Then refuel on the ground.
7. Reopen **COVERAGE & ALERTS** to inspect recommendations and activity. Restore
   roads to demonstrate coverage recovery; a road-served target disables air
   rescue again.

Suggested explanation: "The system chooses where medical centers can serve the
city most effectively. When roads fail, it identifies exactly who loses access
and proposes where extra care is needed. Ambulances handle reachable emergencies;
helicopters bridge isolated areas, reserve fuel for the complete trip, deliver patients
directly to a safe hospital, and return to separate building bases."

## Backend interfaces

`GET /state` includes `medical_network` and `air_rescue` alongside the existing
fleet, emergency, graph, and analysis data. Existing APIs remain available.

| Action | Endpoint | Body |
| --- | --- | --- |
| Check air eligibility | `GET /simulation/helicopter/eligibility/{node_id}` | none |
| Air rescue | `POST /simulation/helicopter/dispatch` | `{"node":"O15"}` |
| Edit optional landing sites | `POST /simulation/helicopter/landings` | `{"nodes":["A1","H8"]}` |
| Refuel after landing | `POST /simulation/helicopter/refuel` | none |
| Open a current recommended center | `POST /simulation/medical_centers` | `{"node":"C4"}` |

Run regression tests with `python -m pytest tests frontend-2d-pygame/tests -q`.
The live native integration check is `python frontend-2d-pygame/tools/live_smoke.py`.
It starts an isolated localhost backend, drives Pygame events without a visible
window, and checks flight, fuel, building-pad edits, direct hospital delivery, return and refueling.
Screenshots are generated by `python frontend-2d-pygame/tools/render_screens.py`.

Current verification: **231 Python tests and six browser tests passed**. Native
Pygame checks completed hospital delivery, return to a separate building,
assistant relocation with fuel use, police dispatch and patrol-off regressions.
All nine desktop screens were rendered. See [RESCUE_OPERATIONS_GUIDE.md](RESCUE_OPERATIONS_GUIDE.md)
for the current flight lifecycle and [POLICE_OPERATIONS_GUIDE.md](POLICE_OPERATIONS_GUIDE.md)
for heatmap patrol intervals.

For road-link controls and eight ambulance-only gate intensities, see [DISASTER_CONTROLS_GUIDE.md](DISASTER_CONTROLS_GUIDE.md). Automatic flooding and frontend flood controls have been removed.
