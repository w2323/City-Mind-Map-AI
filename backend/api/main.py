from fastapi import FastAPI
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.simulation_engine import Simulation

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CityMind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global simulation state
sim = Simulation(seed=42)
sim.initialize()

# Health check endpoint
@app.get("/")
def root():
    return {"status": "CityMind backend running"}

@app.get("/state")
def get_state():
    return sim.state.to_dict()

@app.get("/graph")
def get_graph():
    return sim.graph.to_dict()

@app.post("/start")
def start_simulation():
    global sim
    sim = Simulation(seed=42)
    sim.initialize()
    return {"message": "Simulation restarted", "state": sim.state.to_dict()}

@app.post("/simulation/step")
def step_simulation():
    if not sim.state.is_complete:
        sim.step_forward()
    return {"message": f"Stepped to {sim.state.step}", "state": sim.state.to_dict(), "stats": sim.events.to_dict()}

@app.post("/simulation/flood_node/{node_id}")
def flood_node(node_id: int):
    sim.trigger_flood_at_node(node_id)
    # Step forward immediately so the router reroutes!
    if not sim.state.is_complete:
        sim.step_forward()
    return {"message": f"Flooded node {node_id} and stepped.", "state": sim.state.to_dict(), "stats": sim.events.to_dict()}
