# Road controls and Gate of Death

Open **Disasters** in the Python/Pygame workspace. Flood controls and automatic
random flooding have been removed from the operator workflow.

## Three operations

1. **Block Road:** click the road link between its two nodes, then press
   **Block Selected Road**. It closes that link to everyone, including ambulances.
   Clicking a junction does not select a road.
2. **Unblock Road:** click a road link, then **Unblock Selected Road**. It clears
   both a full closure and any gate restriction on that individual link.
3. **Unleash Gate of Death:** select the center node and choose **First** through
   **Eighth Gate of Death**. Their radii are 1 through 8 grid cells. The purple
   circle previews the area. Press **Unleash Gate of Death** to apply it.

A road is affected when any part of its link touches or crosses the radius,
including a long road with both endpoints outside the circle. Nodes are not
disabled. Affected edges receive a separate `temporarily_blocked` flag:

| Road state | Normal / commercial traffic | Ambulances |
| --- | --- | --- |
| Open | Allowed | Allowed |
| Gate restriction (amber) | Prohibited | Allowed |
| Full block (red) | Prohibited | Prohibited |

Full road blocks take precedence over gate permission. Multiple gates may overlap.
Restrictions remain until the operator clears them or unblocks an individual road.
**Clear Gate Restrictions** removes all temporary restrictions while preserving
full road blocks. Unblocking a road creates an exception to every current gate
affecting that road; unleashing another gate may restrict it again.

Medical-center coverage, nearest-ambulance dispatch, and helicopter eligibility
use ambulance road access. A gate alone therefore does not produce a false
medical cutoff or unlock the helicopter. A full block can still cut off access.

## Demonstrate the difference

- Unleash the eighth gate at **H8** and inspect the amber road links and radius.
- In **Route Lab**, enter **H8** and **A1**. Use the routing button to switch
  between **Normal / Commercial** (the default) and **Ambulance**. Ambulances retain a road
  route; normal traffic cannot leave a center enclosed by restricted roads.
  Outside-to-outside journeys take a legal detour when one exists.
- Block one road link manually. Ambulances must avoid that full closure too.
- Clear gate restrictions and show that the manual full closure remains.

The React interface uses the same backend rules. Its **Disasters** panel has
road-link selection and eight gate intensities, and normal traffic animations
avoid restricted links. Backend configuration supplies radii to both interfaces.

## API

| Action | Endpoint | Body |
| --- | --- | --- |
| Preview affected roads | `POST /simulation/disasters/gate/preview` | `{"node_id":112,"intensity":8}` |
| Unleash gate | `POST /simulation/disasters/gate` | `{"node_id":112,"intensity":8}` |
| Clear gate restrictions | `POST /simulation/disasters/gates/clear` | none |
| Full road block | `POST /simulation/block_road/{a}/{b}` | none |
| Reopen road | `POST /simulation/unblock_road/{a}/{b}` | none |
| Route by travel type | `POST /simulation/route` | `{"src":112,"dst":0,"travel_mode":"normal"}` |

`travel_mode` accepts `ambulance`, `normal`, or `commercial`. General route requests
default to `normal`, so omitted travel types never grant ambulance access.
Ambulance dispatch and ambulance-ranking calculations explicitly use ambulance
mode. `GET /state` exposes active gates,
level radii, road counts, activity history, and edge permission flags. Preview
does not mutate the graph. Resetting the city clears all disasters.

Legacy flood endpoints remain for compatibility with existing API clients and
historical regression tests; neither frontend offers a flood operation.

Verified: **140 Python/API/Pygame regression tests passed**, including segment
intersection, travel permissions, real detours, overlap, full-block precedence,
serialization, normal-route replanning, road picking, all eight intensity buttons,
and unchanged medical coverage. A live Pygame check selected actual road links,
blocked/unblocked them, unleashed level eight, compared normal/ambulance routes,
and cleared temporary restrictions without reopening full closures.
The live Route Lab check also confirmed that its default normal calculation
excludes gate roads and that only explicitly switching to ambulance routing
allows the same journey through the gate. Default residential-to-residential
calculations take a legal outside detour or return unreachable when none exists.

Both browser integration tests also passed: the existing playback/optimization/
export flow and the new gate controls with normal-versus-ambulance routing.
The React production build passes. Its existing large-bundle warning remains.
