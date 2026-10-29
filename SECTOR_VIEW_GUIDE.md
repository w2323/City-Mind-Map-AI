# Sector view

Each existing A1–O15 grid location is now presented as an urban sector. A building symbol illustrates the sector's main activity; it does not mean the sector contains only one house or establishment.

| Display category | Sector meaning |
| --- | --- |
| Residential sector | Homes, apartments and local services |
| Financial sector (FIN / FINANCE) | Banks, jewellery shops and valuable businesses |
| Medical sector | Hospitals, clinics and pharmacies |
| Industrial sector | Factories, warehouses and industrial activity |
| Education sector | Schools and related services |
| Energy sector | Power generation and utilities |
| Open-space sector | Parks, public space or undeveloped land |

Police stations remain service facilities within their existing sectors. A station in a residential sector does not replace its residential land use. The existing medical centers, ambulances and helicopter continue to operate at their current sector references.

## Interface changes

Both frontends use sector language for inspectors, crime reporting and disaster locations. Pygame also uses sector language throughout route and coverage displays. React's top bar counts sectors. Financial locations have FIN badges in Pygame and FINANCE signs in React; inspectors explain what each sector represents.

The population heatmap is interpreted as the current synthetic population of each sector. The crime heatmap describes sector-wide opportunity and reported crime, including the existing circular influence on neighboring sectors. A high score does not mean every building experienced an incident. Existing populations are not multiplied or converted into invented household counts.

A radius of three sector units means the same geometric radius as three grid cells previously. This is a wording change, with no assumed conversion to metres. Location labels, numeric IDs and internal node_type values remain unchanged for API compatibility.

## Mechanics preserved

No files in core/, backend/, challenges/ or config/ were edited for this view change. Checksums verified all 21 Python source files in those directories remained identical. Road endpoints, connections, costs, pathfinding, dispatch, vehicle movement, placement, fuel, Gate permissions, crime scores, spatial radius and fading calculations remain as before.

The existing 210 Python/Pygame tests and five browser workflows verify compatibility. Native workflow checks exercise actual ambulance dispatch, helicopter handoff, radius controls, road block/unblock and Gate route permissions.

For presentation: "Each grid location represents a city sector with multiple buildings and activities. Existing graph routes connect those sectors, while our heatmaps and response services operate at sector level."
