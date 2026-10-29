# Police, ambulance and helicopter operations

Ambulance coverage radii have been removed from the Python model, API and desktop controls. An ambulance responds according to road reachability, actual route cost and availability. Gate of Death and crime heatmap radii remain unchanged.

## Joint police and medical response

In **Police operations**, choose **INJURY**, or turn **MEDICAL ASSISTANCE** on for another incident type, then report a sector. The backend requests a police car and a real ambulance independently. The Python police map shows both fleets and their remaining routes. Its Fleet tab includes ambulances, and the report shows the medical task's status. React also shows the real medical fleet and routes.

If ambulances are busy, the medical request queues. If operational medical road service is unavailable, the report offers helicopter rescue. Police restrictions still apply independently: police cannot cross Gate-restricted roads. A report closes only when both its police and medical work are finished.

## Gate of Death and ambulance outages

When a Gate is unleashed, an ambulance caught inside the circle goes **OUT OF SERVICE**. The same applies to the ambulance belonging to a medical center inside the circle, even if that ambulance is elsewhere. The backend emits a notification naming the unit. The affected vehicle stays at its current position; its assignment is retained and cannot be counted as a completed rescue.

Unaffected ambulances retain permission to cross ambulance-only roads. This preserves the original Gate traffic rule. Full road blocks still prohibit all vehicles. Unblocking an individual road does not clear a facility's Gate exposure. Clearing Gate restrictions restores affected units and resumes their retained assignments. Overlapping Gates cannot accidentally re-enable a disabled ambulance.

The medical network's road-connectivity metric remains separate from service availability: intact roads do not mean that every ambulance is operational. Check the live fleet status and `dispatch_summary.out_of_service`.

## Multiple landing spots and assisted relocation

The city starts with six distributed landing pads on existing non-hospital building sectors. Purple **HP** markers show available sites; red markers show unavailable sites. Hospitals, ambulance depots and empty sectors are excluded. The placement uses a central building for the starting base and spreads the other pads across the city without changing zoning, hospital placements or roads. Optional building pads can be edited through **LANDING SITES**. A usable pad must be outside active Gate circles and retain medical road access. Its safety is independent of whether ambulances are currently busy or out of service.

If a Gate covers the helicopter's occupied pad, an **Assistant required** warning and **RELOCATE HELICOPTER** button appear. The helicopter stays landed until the operator clicks the button. It is available in Dispatch, Disaster control, and Police operations. React also displays a relocation alert and button. The backend chooses the closest safe non-hospital building pad with sufficient fuel and reserve. The helicopter physically flies there; fuel is charged for every distance flown, including empty repositioning.

If no suitable pad exists, or fuel is insufficient, relocation stays disabled and the backend explains why. Refuel while landed or restore a safe operational landing site. There is no invented flight or automatic success. When a Gate is cleared before takeoff, relocation is no longer required.

A helicopter already flying diverts if its destination becomes unsafe. If a new disaster removes every normal landing option, it makes an emergency landing on a non-hospital building within its remaining fuel, preferring a safe sector. A patient stays aboard and unresolved until a safe hospital delivery becomes possible. If the whole grid is unsafe, the emergency landing is explicitly flagged and assisted relocation remains required; the simulation does not report a completed rescue.

## Complete helicopter rescue cycle

The flight sequence is **safe building → emergency sector → nearest safe hospital → closest safe building**. Hospitals are patient-delivery destinations, never helicopter parking or relocation bases. Air eligibility still requires the absence of operational medical road service; merely busy ambulances do not unlock the helicopter.

Before takeoff, the budget includes the emergency leg, hospital delivery, final hospital-to-building flight and landing reserve. After pickup, the helicopter flies directly to the nearest usable hospital; it does not request an ambulance handoff. The rescue count increases once, on physical arrival at that hospital. The aircraft then flies empty to the closest safe building. It is READY for a new mission only after completing that return.

If the chosen hospital becomes unsafe in flight, the aircraft selects the next nearest feasible safe hospital. If none is available, it lands with the patient still aboard, reports WAITING_HOSPITAL, and resumes delivery when care and flight reserves permit. Assisted relocation never discards or duplicates the patient.

## API

- `POST /simulation/helicopter/relocate`: validate the current exposure and fuel budget, then begin physical relocation.
- `air_rescue.relocation`: whether assistance is required, whether relocation is currently possible, proposed target and reason.
- `air_rescue.landing_sites`: each pad's sector, geometric safety and current availability.
- `air_rescue.hospital_nodes`: usable hospital destinations, separate from building landing sites.
- `emergencies[].hospital_id` and `hospital_arrival_step`: actual air-patient delivery destination and time.
- `fleet[].status`, `service_reason`, `gate_ids`: live ambulance service state.
- The old ambulance radius endpoint has been removed.

Restart an already running backend and frontend to load these changes. From the inner project directory, launch the Python client with `python frontend-2d-pygame/main.py --auto-backend`.

## Verification

Regression coverage includes non-hospital pad validation, closest-building relocation, fuel accounting for all flight legs, hospital loss after pickup, retained patients during disaster diversion, single delivery counting and the final empty return. Live native controls and browser integration tests exercise the same Python state.

Current validation passed 231 Python tests, six browser tests, both native event-loop workflows and the React production build. All desktop screens were rendered; building-pad relocation and heatmap patrol views were visually inspected.
