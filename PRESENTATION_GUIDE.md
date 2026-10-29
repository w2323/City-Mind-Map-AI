# CityMind demonstration

Run `./run_3d.ps1` from this folder and open `http://127.0.0.1:5173/`. Keep the server terminal running. The React and Pygame clients share one Python simulation.

## Suggested walkthrough

1. Choose **Map overview**. Point out the numbered columns, lettered rows, sector references, and live traffic signals. Click a building or road to inspect it.
2. Choose **Orbit city**, drag to rotate, then **Walk streets**. Drag to look, use W/A/S/D to move, Shift for speed and Q/E for height. Return to Map overview for operations.
3. Open **Dispatch**, enter a valid sector and dispatch an ambulance. Watch the vehicle, route and emergency status update. Playback starts automatically; Pause remains available in the sidebar.
4. Open **Police** and report an incident. An Injury report includes medical assistance. Toggle patrols and automatic reports, then adjust the incident chance. Settings save when a slider is released.
5. Use **Plan police stations**. Planning pauses playback. Select a proposed site before opening it. If no construction is available, the panel explains why; recommendations are constrained by the backend.
6. Use **Disasters** to close a road, reopen it, or preview a Gate of Death. The Gate radius and affected-road count are shown before applying it. Clear restrictions to restore service. Respond to a helicopter relocation notice if its base is exposed.
7. Open **Route Lab**. Compare normal and ambulance access between the same sectors. A* and independent Dijkstra costs are compared on the same city snapshot.
8. Open **City Map / Heatmap** for population, crime, medical coverage, police presence, road costs and IDs. **Ambulance** includes optimization and route validation.
9. End with **Metrics** and CSV export, or **Diagnostics** to inspect graph/fleet checks. Event history and police reports can load older entries on demand.

## Control states

- A blank/invalid report sector cannot be dispatched. Choose a building or type its label.
- Injury reports require medical assistance.
- Station construction requires a fresh proposed site. A changed road/crime state requires replanning.
- Refueling requires a landed helicopter with fuel below 100%.
- A finished simulation requires **New city** for new incidents.
- Other clients can still change the shared model while this browser is paused.

Traffic signals govern background presentation traffic; dispatch outcomes, police operations, road access and emergency vehicle positions come from the backend. Synthetic crime scores describe the scenario and are not measured crime probabilities.
