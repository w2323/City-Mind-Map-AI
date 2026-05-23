# CityMind Implementation Documentation

This document provides a comprehensive technical overview of the CityMind Urban Intelligence System, detailing the five core AI challenges, their implementation locations, and how to interact with them via the 3D Dashboard.

---

## Project Architecture
CityMind is built on a **Shared City Graph** architecture. Every AI module operates on the same underlying data structure, ensuring that a change in one part of the city (like a flood or a crime risk update) is immediately visible to all other modules.

- **Frontend:** React + Vite + Three.js (3D Visualization)
- **Backend:** FastAPI (Python)
- **Core Logic:** Custom Graph and Simulation Engine (`core/`)

---

## Challenge 1: City Layout Planning (CSP)
- **File:** `challenges/challenge1.py`
- **Algorithm:** **Constraint Satisfaction Problem (CSP)** with Backtracking, MRV (Minimum Remaining Values), and Forward Checking.
- **What it does:** Automatically arranges infrastructure (Hospitals, Schools, Industrial, etc.) on an empty grid while satisfying urban planning rules (e.g., Hospitals near residents, Industrial away from schools).
- **UI Trigger:** Triggered automatically upon **Simulation Initialization** (when the dashboard first loads or is reset).
- **Outcome:** A logically organized city layout that meets all mathematical constraints.

---

## Challenge 2: Road Network Optimization (MST)
- **File:** `challenges/challenge2.py`
- **Algorithm:** **Kruskal's Minimum Spanning Tree (MST)** + Redundancy Injection.
- **What it does:** Connects all city nodes using the minimum amount of road while ensuring a "2-connected" safety guarantee: there are always at least two independent paths between the Hospital and the Ambulance Depots.
- **UI Trigger:** Visible by default. You can toggle the road view in the **Left Panel** under **VIEW TOGGLES → ROAD NETWORK**.
- **Outcome:** A cost-efficient road network that can survive a single road failure.

---

## Challenge 3: Ambulance Placement (GA)
- **File:** `challenges/challenge3.py`
- **Algorithm:** **Genetic Algorithm (GA)** using Tournament Selection, Uniform Crossover, and Mutation.
- **What it does:** Optimizes the placement of 3 ambulances across the city's depots to minimize the "Worst-Case Response Time" (Minimax optimization) for all residential areas.
- **UI Trigger:** In the **Left Panel**, use the **AMBULANCE** dropdown. You can select "Optimized" to see the GA in action. Coverage can be visualized via **VIEW TOGGLES → AMBULANCE COVERAGE**.
- **Outcome:** Strategic placement of emergency vehicles that ensures help is never too far away from any citizen.

---

## Challenge 4: Emergency Routing (Dynamic A*)
- **File:** `challenges/challenge4.py`
- **Algorithm:** **A* Search** with an Admissible Euclidean Heuristic and Event-Driven Replanning.
- **What it does:** Calculates the shortest available path for an ambulance mission. If a road is blocked during the trip, the system immediately recalculates a new route from the ambulance's current tires to the target.
- **UI Trigger:** Play the simulation using the **Playback Controls** or click **NEXT STEP**. To trigger a reroute, use **⚡ ACTIVATE GOD MODE** and click any node to unleash a flood.
- **Outcome:** Real-time, optimal navigation that adapts to environmental disasters.

---

## Challenge 5: Crime Risk Prediction (ML)
- **File:** `challenges/challenge5.py`
- **Algorithm:** **K-Means Clustering** (Unsupervised) + **Decision Tree** (Supervised Classification).
- **What it does:** Analyzes population density and industrial proximity to predict "High", "Medium", and "Low" crime risk zones. These predictions are fed back into the graph as "Edge Cost Multipliers," making the ambulance and router avoid high-risk alleys.
- **UI Trigger:** Toggle the heatmap in the **Left Panel** via **VIEW TOGGLES → CRIME RISK HEATMAP**. 10 police officers are automatically deployed to the highest-risk nodes.
- **Outcome:** A data-driven safety layer that influences all other city decisions.

---

## Summary of Triggers & Interactions
| Action | AI Challenge Involved | Outcome |
| :--- | :--- | :--- |
| **Initial Load** | Challenge 1 & 2 | The city is planned and roads are built. |
| **God Mode Click** | Challenge 4 (A*) | Roads are blocked; ambulance reroutes live. |
| **Ambulance Dropdown**| Challenge 3 (GA) | Re-calculates optimal vehicle positions. |
| **View Heatmap** | Challenge 5 (ML) | Visualizes predicted crime risk clusters. |
| **Next Step** | Simulation Engine | Advances the timeline and physical movement. |
