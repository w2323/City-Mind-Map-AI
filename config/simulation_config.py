# simulation_config.py — Centralized configuration for CityMind
# All tunable parameters in one place. No hardcoded values in modules.


class SimConfig:
    """Single source of configuration for the entire CityMind system."""

    # ── Grid ────────────────────────────────────────────────
    GRID_ROWS: int = 15
    GRID_COLS: int = 15

    # ── Road Costs ──────────────────────────────────────────
    COST_STANDARD: float = 1.0
    COST_RESIDENTIAL: float = 0.8
    COST_DIAGONAL: float = 1.4

    # ── Risk Multipliers (applied to edge costs) ────────────
    RISK_MULTIPLIER: dict = {
        "HIGH": 2.0,
        "MEDIUM": 1.5,
        "LOW": 1.0,
        "NONE": 1.0,
    }

    # ── Node Type Constants ─────────────────────────────────
    RESIDENTIAL = "RESIDENTIAL"
    HOSPITAL = "HOSPITAL"
    SCHOOL = "SCHOOL"
    INDUSTRIAL = "INDUSTRIAL"
    POWER_PLANT = "POWER_PLANT"
    DEPOT = "AMBULANCE_DEPOT"
    EMPTY = "EMPTY"

    ALL_TYPES = [RESIDENTIAL, HOSPITAL, SCHOOL, INDUSTRIAL, POWER_PLANT, DEPOT, EMPTY]

    # ── CSP Layout Requirements (minimum counts) ────────────
    REQUIRED_COUNTS: dict = {
        "RESIDENTIAL": 70,
        "HOSPITAL": 6,
        "SCHOOL": 4,
        "INDUSTRIAL": 4,
        "POWER_PLANT": 2,
        "AMBULANCE_DEPOT": 3,
    }

    # ── CSP Constraint Thresholds ───────────────────────────
    HOSPITAL_HOP_LIMIT: int = 5     # C2: residential must be within N hops of hospital
    INDUSTRIAL_HOP_LIMIT: int = 2   # C3: power plant must be within N hops of industrial

    # ── Road Network (Challenge 2) ──────────────────────────
    REDUNDANCY_EDGES: int = 30      # extra edges added after MST

    # ── Genetic Algorithm (Challenge 3) ─────────────────────
    GA_NUM_AMBULANCES: int = 3      # Matches AMBULANCE_DEPOT count
    GA_POP_SIZE: int = 60
    GA_GENERATIONS: int = 200
    GA_MUTATION_RATE: float = 0.15
    GA_TOURNAMENT_SIZE: int = 5
    GA_ELITISM_COUNT: int = 2

    # ── GA Fast Re-evaluation (mid-simulation) ──────────────
    GA_FAST_POP_SIZE: int = 20
    GA_FAST_GENERATIONS: int = 30

    # ── Emergency Routing (Challenge 4) ─────────────────────
    NUM_CIVILIANS: int = 5          # civilians to rescue per mission

    # ── Crime Prediction ML (Challenge 5) ───────────────────
    KMEANS_K: int = 3
    KMEANS_MAX_ITER: int = 100
    DECISION_TREE_MAX_DEPTH: int = 5
    DECISION_TREE_MIN_SAMPLES: int = 5
    NUM_POLICE_OFFICERS: int = 10

    # ── Simulation ──────────────────────────────────────────
    MAX_STEPS: int = 100
    FLOOD_PROBABILITY: float = 0.30
    AMBULANCE_REEVAL_INTERVAL: int = 5   # re-evaluate ambulances every N steps
    RISK_REEVAL_INTERVAL: int = 5        # re-evaluate crime risk every N steps

    # ── Population Values (set after CSP layout) ────────────
    POPULATION_MAP: dict = {
        "RESIDENTIAL": (50, 200),     # random range
        "HOSPITAL": 20,
        "SCHOOL": 30,
        "INDUSTRIAL": 10,
        "POWER_PLANT": 5,
        "AMBULANCE_DEPOT": 5,
        "EMPTY": 0,
    }

    # ── Random Seed (None = non-deterministic) ──────────────
    SEED: int = None

    # ── Spatial Distribution Constraints (Hybrid Urban Generator) ──
    NUM_DISTRICTS: int = 4                     # Voronoi-like district regions
    MIN_INDUSTRIAL_HOSPITAL_DIST: int = 3      # Manhattan distance
    MIN_INDUSTRIAL_SCHOOL_DIST: int = 3        # Manhattan distance
    MIN_DEPOT_DEPOT_DIST: int = 5              # Min Manhattan between ambulance depots
    POWER_PLANT_INDUSTRIAL_DIST: int = 2       # Max hops from power plant to industrial
    EMPTY_RATIO_MIN: float = 0.15              # 15-30% empty nodes target
    EMPTY_RATIO_MAX: float = 0.30
    MAX_QUADRANT_INFRA_RATIO: float = 0.40     # No district holds >40% of all infra
    MAX_EMPTY_CLUSTER: int = 20                # Max connected-component size for EMPTY
