"""Shared local prototype API. Run one worker; all model access is serialized."""
import os
import sys
import csv
import io
import random
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.simulation_engine import Simulation
from core.city_graph import CityGraph
from core.analytics import route, ambulance_routes, finite
from challenges.challenge3 import GAambulancePlacer
from core.medical_network import MedicalCenterPlanner
from config.simulation_config import SimConfig

_sim_lock = threading.RLock()
sim = Simulation(seed=SimConfig.SEED, verbose=False)
sim.initialize()
_revision = 0
_job = {"status": "idle", "generation": 0, "run": 0, "runs": 0, "fitness": None, "positions": []}
_cancel = threading.Event()
_resume = threading.Event()
_resume.set()
_worker = None


@asynccontextmanager
async def lifespan(app):
    yield
    _cancel.set()
    _resume.set()
    if _worker:
        _worker.join(timeout=5)
    sim.events.close()


app = FastAPI(title="CityMind API", lifespan=lifespan)
_origins = os.getenv("CITYMIND_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:4173,http://127.0.0.1:4173")
app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in _origins.split(",") if s.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.middleware("http")
async def protect_browser_mutations(request, call_next):
    # CORS alone does not stop cross-site simple POST requests from mutating
    # a local API. Native clients send no Origin header and remain supported.
    origin = request.headers.get("origin")
    if request.method == "POST" and origin and origin not in [s.strip() for s in _origins.split(",")]:
        return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    return await call_next(request)


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: int = Field(strict=True, ge=0)
    dst: int = Field(strict=True, ge=0)
    travel_mode: Literal['ambulance', 'normal', 'commercial'] = 'normal'


class OptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runs: int = Field(default=1, strict=True, ge=1, le=SimConfig.OPTIMIZATION_MAX_RUNS)


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int | None = Field(default=None, strict=True, ge=0, le=2**32-1)
    automatic_events: bool | None = Field(default=None,strict=True)


def snapshot():
    state = sim.state.to_dict()
    state["revision"] = _revision
    state["optimization"] = dict(_job)
    state["config"] = {"coverage_cost_limit": SimConfig.COVERAGE_COST_LIMIT,
                       "coverage_target_pct": SimConfig.COVERAGE_TARGET_PCT,
                       "optimization_max_runs": SimConfig.OPTIMIZATION_MAX_RUNS,
                       "ga_generations": SimConfig.GA_GENERATIONS,
                       "num_ambulances": len(sim.state.fleet.units) if sim.state.fleet else SimConfig.GA_NUM_AMBULANCES,
                       "kmeans_clusters": SimConfig.KMEANS_K}
    return state


def reply(**extra):
    # Render while locked: returned lists must not be serialized during mutation.
    state = snapshot()
    return JSONResponse({**extra, "sim_id": state["sim_id"], "state": state, "stats": state["events"]})


def invalidate_job():
    global _revision
    _revision += 1
    _cancel.set()
    _resume.set()
    if _job["status"] in ("running", "paused"):
        _job["status"] = "cancelled"


@app.get("/")
def root():
    return {"status": "CityMind backend running"}


@app.get("/state")
def get_state():
    with _sim_lock:
        return JSONResponse(snapshot())


@app.get("/graph")
def get_graph():
    with _sim_lock:
        return JSONResponse(sim.graph.to_dict())


@app.post("/start")
@app.post("/simulation/reset")
def start_simulation(options: ResetRequest | None = None):
    global sim, _job
    with _sim_lock:
        invalidate_job()
        replacement = Simulation(seed=options.seed if options else SimConfig.SEED, verbose=False,
                                 automatic_events=options.automatic_events if options else None)
        try:
            replacement.initialize()
        except Exception:
            replacement.events.close()
            raise
        sim.events.close()
        sim = replacement
        _job = {"status": "idle", "generation": 0, "run": 0, "runs": 0, "fitness": None, "positions": []}
        return reply(message="Simulation restarted")


@app.post("/simulation/step")
def step_simulation():
    with _sim_lock:
        stepped = not sim.state.is_complete and sim.state.step < sim.state.max_steps
        if stepped:
            invalidate_job()
            sim.step_forward()
        return reply(message=f"Stepped to {sim.state.step}", stepped=stepped)


@app.post("/simulation/flood_node/{node_id}")
def flood_node(node_id: int):
    with _sim_lock:
        if node_id not in sim.graph.nodes:
            raise HTTPException(404, "Node does not exist")
        invalidate_job()
        return reply(**sim.trigger_flood_at_node(node_id))


def change_road(a, b, blocked):
    with _sim_lock:
        if (min(a, b), max(a, b)) not in sim.graph.edges:
            raise HTTPException(404, "Road does not exist")
        invalidate_job()
        result = sim.block_road_manually(a, b) if blocked else sim.unblock_road_manually(a, b)
        return reply(**result)


@app.post("/simulation/block_road/{node_a}/{node_b}")
def block_road(node_a: int, node_b: int):
    return change_road(node_a, node_b, True)


@app.post("/simulation/unblock_road/{node_a}/{node_b}")
def unblock_road(node_a: int, node_b: int):
    return change_road(node_a, node_b, False)


@app.post("/simulation/route")
def calculate_route(request: RouteRequest):
    with _sim_lock:
        if request.src not in sim.graph.nodes or request.dst not in sim.graph.nodes:
            raise HTTPException(404, "Route endpoint does not exist")
        return JSONResponse({**route(sim.graph, request.src, request.dst, request.travel_mode), "sim_id": sim.state.sim_id, "revision": _revision})


class GateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node_id: int = Field(strict=True, ge=0)
    intensity: int = Field(strict=True, ge=1, le=8)


@app.post('/simulation/disasters/gate/preview')
def preview_gate(request: GateRequest):
    with _sim_lock:
        if request.node_id not in sim.graph.nodes:
            raise HTTPException(404, 'Gate center node does not exist')
        return JSONResponse({**sim.state.disasters.preview(request.node_id, request.intensity),
                             'sim_id':sim.state.sim_id,'revision':_revision})


@app.post('/simulation/disasters/gate')
def unleash_gate(request: GateRequest):
    with _sim_lock:
        if request.node_id not in sim.graph.nodes:
            raise HTTPException(404, 'Gate center node does not exist')
        try:
            gate = sim.state.disasters.unleash(request.node_id, request.intensity, sim.state.step)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        invalidate_job()
        if sim.state.fleet:
            sim.state.fleet.replan()
        if sim.state.air_rescue:
            sim.state.air_rescue.refresh_safety()
        if sim.state.police:
            sim.state.police.refresh(sim.state.step)
        return reply(gate=gate,message=f"Gate of Death {gate['intensity']} unleashed at {gate['label']}. Affected ambulances are out of service; check helicopter relocation alerts.")


@app.post('/simulation/disasters/gates/clear')
def clear_gates():
    with _sim_lock:
        changed = sim.state.disasters.clear(sim.state.step)
        if sim.state.fleet:
            sim.state.fleet.replan()
        if sim.state.air_rescue:
            sim.state.air_rescue.refresh_safety()
        if sim.state.police:
            sim.state.police.refresh(sim.state.step)
        invalidate_job()
        return reply(changed_roads=changed,message='Gate restrictions cleared. Fully blocked roads still require Unblock.')


@app.get("/simulation/ambulance_routes/{target}")
def get_ambulance_routes(target: int):
    with _sim_lock:
        if target not in sim.graph.nodes:
            raise HTTPException(404, "Target does not exist")
        return JSONResponse({**ambulance_routes(sim.state, target), "sim_id": sim.state.sim_id, "revision": _revision})


@app.get("/metrics/export")
def export_metrics():
    with _sim_lock:
        data = snapshot()
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["sim_id", "step", "metric", "value"])
        values = {**data["events"]["metrics"], **{k: v for k, v in data["analysis"].items() if isinstance(v, (int, float, bool))}}
        values.update({"dispatch_"+k: v for k,v in data.get("dispatch_summary",{}).items() if isinstance(v,(int,float,bool))})
        values.update({k if k.startswith('police_') else 'police_'+k:v for k,v in data.get('police',{}).get('summary',{}).items() if isinstance(v,(int,float,bool))})
        for key, value in values.items():
            writer.writerow([data["sim_id"], data["step"], key, value])
        return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="citymind-metrics.csv"'})


class Cancelled(Exception):
    pass


def optimize(graph, identity, revision, job, cancel, resume):
    global _revision
    def progress(generation, fitness, positions):
        while not resume.wait(timeout=0.1):
            if cancel.is_set():
                raise Cancelled()
        if cancel.is_set():
            raise Cancelled()
        with _sim_lock:
            job["generation"] = generation
            if job["fitness"] is None or (finite(fitness) is not None and fitness < job["fitness"]):
                job["fitness"] = finite(fitness)
                job["positions"] = list(positions)
    try:
        best_fitness = float("inf")
        best = None
        best_feasible = False
        for run in range(1, job["runs"] + 1):
            with _sim_lock:
                job["run"] = run
            placer = (MedicalCenterPlanner(graph, count=sum(n.node_type == SimConfig.HOSPITAL for n in graph.nodes.values()),
                                           rng=random.Random(run), generations=SimConfig.GA_GENERATIONS)
                      if job.get('medical_centers') else GAambulancePlacer(graph, rng=random.Random(run)))
            positions = placer.run(progress=progress)
            if best is None or placer.best_fitness < best_fitness:
                best, best_fitness = positions, placer.best_fitness
                best_feasible = not placer.is_infeasible
        with _sim_lock:
            if cancel.is_set() or sim.state.sim_id != identity or _revision != revision:
                raise Cancelled()
            sim.state.optimized_placements = best
            if sim.state.fleet is None:
                sim.state.ambulances = best
            sim.events.metrics.ga_best_fitness = best_fitness
            sim.events.metrics.ambulance_repositions += 1
            _revision += 1
            job.update(status="completed", positions=best, fitness=finite(best_fitness), feasible=best_feasible)
    except Cancelled:
        with _sim_lock:
            job["status"] = "cancelled"
    except Exception:
        import logging
        logging.exception("Ambulance optimization failed")
        with _sim_lock:
            job.update(status="failed", error="Optimization failed; see backend log")


@app.post("/simulation/optimization/start")
def start_optimization(request: OptimizationRequest):
    global _job, _cancel, _resume, _worker
    with _sim_lock:
        if _job["status"] == "paused":
            _job["status"] = "running"
            _resume.set()
            return reply()
        if _worker and _worker.is_alive():
            raise HTTPException(409, "An optimization is already running or stopping")
        _cancel, _resume = threading.Event(), threading.Event()
        _resume.set()
        _job = {"status": "running", "generation": 0, "run": 1, "runs": request.runs, "fitness": None, "positions": [],
                "medical_centers": sim.state.medical_network is not None}
        frozen = CityGraph.from_dict(sim.graph.to_dict())
        _worker = threading.Thread(target=optimize, args=(frozen, sim.state.sim_id, _revision, _job, _cancel, _resume), daemon=True)
        _worker.start()
        return reply()


@app.post("/simulation/optimization/{action}")
def control_optimization(action: Literal["pause", "reset"]):
    global _job
    with _sim_lock:
        if action == "pause":
            if _job["status"] != "running":
                raise HTTPException(409, "No running optimization")
            _resume.clear()
            _job["status"] = "paused"
        else:
            _cancel.set()
            _resume.set()
            _job = {"status": "idle", "generation": 0, "run": 0, "runs": 0, "fitness": None, "positions": []}
        return reply()


class EmergencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node: str = Field(min_length=1, max_length=20)


@app.post("/simulation/emergencies")
def dispatch_emergency(request: EmergencyRequest):
    with _sim_lock:
        if sim.state.is_complete:
            raise HTTPException(409, "Simulation is complete. Restart the city before dispatching.")
        label = request.node.strip().upper()
        target = next((n.id for n in sim.graph.nodes.values() if n.label.upper() == label), None)
        if target is None:
            raise HTTPException(404, "Unknown node. Enter a grid label such as C4.")
        if sim.state.fleet is None:
            raise HTTPException(409, "Fleet is not initialized")
        if sim.state.medical_network:
            sim.state.medical_network.refresh()
            if target not in sim.state.fleet.road_reachable():
                raise HTTPException(409, 'Helicopter depot required: no medical center can reach this node by road. Select HELICOPTER RESCUE.')
        try:
            emergency = sim.state.fleet.dispatch(target, sim.state.step)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        invalidate_job()
        return reply(message=f"{emergency['ambulance_id']} dispatched to {label}", emergency=emergency)


class LandingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nodes: list[str] = Field(min_length=1, max_length=SimConfig.GRID_ROWS*SimConfig.GRID_COLS)


def node_label(label):
    target = next((n.id for n in sim.graph.nodes.values() if n.label == label.strip().upper()), None)
    if target is None:
        raise HTTPException(404, 'Unknown grid node.')
    return target


def air_service():
    if sim.state.air_rescue is None:
        raise HTTPException(409, 'Air rescue is not initialized.')
    return sim.state.air_rescue


@app.get('/simulation/helicopter/eligibility/{target}')
def helicopter_eligibility(target: int):
    with _sim_lock:
        if target not in sim.graph.nodes:
            raise HTTPException(404, 'Unknown grid node.')
        return JSONResponse(air_service().eligibility(target))


@app.post('/simulation/helicopter/dispatch')
def dispatch_helicopter(request: EmergencyRequest):
    with _sim_lock:
        if sim.state.is_complete:
            raise HTTPException(409, 'Restart the city before dispatching.')
        try:
            emergency = air_service().dispatch(node_label(request.node), sim.state.step)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        invalidate_job()
        return reply(message='Helicopter rescue dispatched with landing fuel reserved.', emergency=emergency)


@app.post('/simulation/helicopter/landings')
def edit_landings(request: LandingRequest):
    with _sim_lock:
        try:
            air_service().set_landings([node_label(label) for label in request.nodes])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        invalidate_job()
        return reply(message='Building landing sites updated. Hospitals are reserved for patient delivery; Gate-affected bases are unavailable.')


@app.post('/simulation/helicopter/relocate')
def relocate_helicopter():
    with _sim_lock:
        try:
            target = air_service().relocate(sim.state.step)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        invalidate_job()
        return reply(message=f"Helicopter relocating to safe landing spot {sim.graph.nodes[target].label}.")


@app.post('/simulation/helicopter/refuel')
def refuel_helicopter():
    with _sim_lock:
        try:
            air_service().refuel()
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        invalidate_job()
        return reply(message='Helicopter refueled to full capacity.')


@app.post('/simulation/medical_centers')
def add_medical_center(request: EmergencyRequest):
    with _sim_lock:
        network = sim.state.medical_network
        if network is None or sim.state.fleet is None:
            raise HTTPException(409, 'Medical network is not initialized.')
        network.refresh()
        node = node_label(request.node)
        if node not in [r['node_id'] for r in network.recommendations]:
            raise HTTPException(409, 'Choose a current recommended site for an unserved component.')
        sim.graph.nodes[node].node_type = SimConfig.HOSPITAL
        sim.graph.nodes[node].population = SimConfig.POPULATION_MAP[SimConfig.HOSPITAL]
        network.centers.append(node)
        network.centers.sort()
        sim.state.fleet.add_center(node)
        sim.refresh_risk()
        network.refresh()
        sim.state.optimized_placements = list(network.centers)
        network.notify(f'Medical center opened at {sim.graph.nodes[node].label} with a new ambulance.', [node], 'info')
        invalidate_job()
        return reply(message=f'Medical center opened at {request.node.strip().upper()}.')


class CrimeReportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node: str = Field(min_length=1,max_length=20)
    kind: Literal['THEFT','VANDALISM','DISTURBANCE','INJURY'] = 'THEFT'
    severity: int = Field(default=1,strict=True,ge=1,le=3)
    medical_required: bool = Field(default=False,strict=True)


class PoliceSettingsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    patrol_enabled: bool | None = Field(default=None,strict=True)
    automatic_incidents: bool | None = Field(default=None,strict=True)
    auto_probability: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)


class CityEventSettingsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool | None = Field(default=None,strict=True)
    medical_enabled: bool | None = Field(default=None,strict=True)
    roads_enabled: bool | None = Field(default=None,strict=True)
    crime_enabled: bool | None = Field(default=None,strict=True)
    medical_probability: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)
    road_probability: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)
    crime_probability: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)


@app.post('/simulation/events/settings')
def city_event_settings(request: CityEventSettingsRequest):
    with _sim_lock:
        if sim.state.city_events is None:
            raise HTTPException(409,'City events are not initialized')
        sim.state.city_events.configure(**request.model_dump(exclude_none=True))
        invalidate_job()
        return reply(message='Automatic city events updated. Existing calls and scheduled road repairs remain active.')


class PoliceCompareRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    seed: int = Field(default=42,strict=True,ge=0,le=2**32-1)
    steps: int = Field(default=80,strict=True,ge=20,le=200)
    incident_count: int = Field(default=12,strict=True,ge=1,le=30)


def police_service():
    if sim.state.police is None:
        raise HTTPException(409,'Police service is not initialized')
    return sim.state.police


@app.post('/simulation/police/reports')
def report_crime(request: CrimeReportRequest):
    with _sim_lock:
        if sim.state.is_complete:
            raise HTTPException(409,'Restart the city before reporting another incident')
        try:
            report=police_service().report(node_label(request.node),request.kind,request.severity,
                                          sim.state.step,request.medical_required)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        invalidate_job()
        return reply(report=report,message=f"{report['id']} reported at {report['label']}: {report['status'].replace('_',' ').lower()}.")


@app.post('/simulation/police/settings')
def police_settings(request: PoliceSettingsRequest):
    with _sim_lock:
        police_service().configure(sim.state.step,**request.model_dump(exclude_none=True))
        invalidate_job()
        return reply(message='Police patrol and automatic incident settings updated')


@app.post('/simulation/police/stations/plan')
def plan_police_stations():
    with _sim_lock:
        police_service().plan_stations()
        invalidate_job()
        return reply(message='Police station recommendations calculated; existing stations and vehicles stay in place')


@app.post('/simulation/police/stations')
def open_police_station(request: EmergencyRequest):
    with _sim_lock:
        service=police_service()
        if service.plan is None or service.plan['basis']!=service._plan_basis():
            raise HTTPException(409,'Calculate fresh police station recommendations first')
        node=node_label(request.node)
        if node not in [r['node_id'] for r in service.plan['additions']]:
            raise HTTPException(409,'Choose a currently recommended police station site')
        try:
            station=service.add_station(node)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        service.refresh(sim.state.step)
        invalidate_job()
        return reply(station=station,message=f"Police station opened at {station['label']} with new patrol cars")


@app.post('/simulation/police/reports/{report_id}/medical_rescue')
def police_medical_rescue(report_id: str):
    with _sim_lock:
        try:
            emergency=police_service().medical_rescue(report_id,sim.state.step)
        except StopIteration:
            raise HTTPException(404,'Crime report does not exist')
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        invalidate_job()
        return reply(emergency=emergency,message='Helicopter assigned to the crime report medical task')


@app.post('/simulation/police/compare')
def compare_police(request: PoliceCompareRequest):
    from core.police_service import compare_strategies
    with _sim_lock:
        service=police_service()
        frozen=CityGraph.from_dict(sim.graph.to_dict())
        identity,revision=sim.state.sim_id,_revision
        station_count,unit_count=len(service.stations),len(service.units)
    result=compare_strategies(frozen,request.seed,request.steps,request.incident_count,station_count,unit_count)
    return JSONResponse({**result,'sim_id':identity,'revision':revision})
