<<<<<<< HEAD
# CityMind: Urban Intelligence Simulation

**CityMind** is a comprehensive AI-driven urban simulation and emergency management platform. It combines multiple core Artificial Intelligence algorithms into a unified, real-time responsive React 3D Dashboard and FastAPI backend.

This project implements **Five Core AI Challenges** integrated into a single shared graph environment:
1. **City Layout Planning (CSP Solver):** Zones the city satisfying urban planning constraints.
2. **Road Network Optimization (Kruskal's MST):** Builds cost-efficient roads with mandated redundancy.
3. **Ambulance Placement (Genetic Algorithm):** Optimizes emergency vehicle placement to minimize worst-case response times.
4. **Emergency Routing (Dynamic A*):** Dynamically recalibrates shortest paths around blocked/flooded roads in real-time.
5. **Crime Risk Prediction (Machine Learning):** Clusters and predicts risks, mapping a heatmap directly onto the pathfinding graph weights.

## 🚀 How to Run the Project

This system uses a decoupled architecture. You will need two terminal windows: one for the Python Backend and one for the React Frontend.

### 1. Start the Backend (FastAPI / AI Engine)
The backend requires Python 3.9+.
```bash
# Navigate to the project root
cd CityMind_Submission

# Install required Python dependencies
pip install -r requirements.txt

# Start the simulation engine and API
uvicorn main:app --reload --port 8000
```
*The backend will initialize the city graph, run the CSP layout, build the MST roads, train the ML models, and wait for frontend connections.*

### 2. Start the Frontend (React 3D Dashboard)
The frontend requires Node.js (v18+ recommended).
```bash
# Open a new terminal and navigate to the frontend folder
cd CityMind_Submission/frontend

# Install React dependencies (Vite, Three.js, etc.)
npm install

# Start the Vite development server
npm run dev
```

### 3. Launch the Simulation
Open the URL provided by Vite (usually `http://localhost:5173`) in your web browser. 
- Open the left-side control panel.
- Click **▶ START** to boot the 3D map engine and connect to the AI backend.
- Use **NEXT STEP** to advance the simulation, watch floods occur, and see the A* router and GA ambulances react dynamically in real-time!

---
*Note: All algorithms were written from scratch specifically for this project, satisfying the requirements without relying on black-box external solver frameworks.*
=======
# AI-Project
will be updated
>>>>>>> 89ae08c182fee46b640fa29a3b3ad0d56731f5cf
