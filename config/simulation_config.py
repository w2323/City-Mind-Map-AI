# simulation_config.py — Centralized configuration for CityMind
# All tunable parameters in one place. No hardcoded values in modules.


class SimConfig:
    GATE_OF_DEATH_RADII = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    MAX_ACTIVE_GATES = 100
    HELICOPTER_FUEL_CAPACITY: float = 100.0
    HELICOPTER_FUEL_PER_CELL: float = 1.0
    HELICOPTER_SPEED: float = 1.5
    HELICOPTER_LOW_FUEL_PCT: float = 20.0
    HELICOPTER_RESERVE: float = 5.0
    HELICOPTER_PAD_COUNT: int = 6
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
    BANK = "BANK"
    EMPTY = "EMPTY"

    ALL_TYPES = [RESIDENTIAL, HOSPITAL, SCHOOL, INDUSTRIAL, POWER_PLANT, DEPOT, BANK, EMPTY]

    # ── CSP Layout Requirements (minimum counts) ────────────
    REQUIRED_COUNTS: dict = {
        "RESIDENTIAL": 70,
        "HOSPITAL": 6,
        "SCHOOL": 4,
        "INDUSTRIAL": 4,
        "POWER_PLANT": 2,
        "AMBULANCE_DEPOT": 3,
        "BANK": 3,
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
    MAX_EMERGENCIES: int = 1000
    NUM_CIVILIANS: int = 0          # civilians to rescue per mission

    # ── Crime Prediction ML (Challenge 5) ───────────────────
    KMEANS_K: int = 3
    KMEANS_MAX_ITER: int = 100
    DECISION_TREE_MAX_DEPTH: int = 5
    DECISION_TREE_MIN_SAMPLES: int = 5
    NUM_POLICE_OFFICERS: int = 10
    POLICE_STATIONS: int = 3
    POLICE_BANK_MAX_BLOCKS: int = 3
    POLICE_BANK_MIN_BLOCKS: int = 2
    BANK_HOSPITAL_MIN_BLOCKS: int = 4
    BANK_MIN_SEPARATION_BLOCKS: int = 7
    POLICE_HOSPITAL_MIN_BLOCKS: int = 2
    POLICE_BANK_PREFERRED_BLOCKS: int = 2
    POLICE_BANK_PREFERENCE_WEIGHT: float = 1.0
    POLICE_MAX_STATIONS: int = 12
    POLICE_MAX_UNITS: int = 40
    POLICE_NEW_STATION_UNITS: int = 2
    POLICE_GA_GENERATIONS: int = 20
    POLICE_GA_POPULATION: int = 18
    POLICE_RISK_WEIGHTS = {'HIGH': 3.0, 'MEDIUM': 2.0, 'LOW': 1.0, 'NONE': 1.0}
    POLICE_HANDLING_STEPS = {1: 2, 2: 3, 3: 5}
    POLICE_QUEUE_AGING_STEPS: int = 10
    POLICE_PATROL_AGING_STEPS: int = 25
    POLICE_PATROL_INTERVALS = {'HIGH': 1, 'MEDIUM': 8, 'LOW': 24, 'NONE': 24}
    POLICE_HIGH_PATROL_SHARE: float = 0.65
    POLICE_AUTO_PROBABILITY: float = 0.15
    POLICE_MAX_OPEN_REPORTS: int = 100
    POLICE_MAX_REPORTS: int = 1000
    CRIME_BASE_SCORE: float = 15
    CRIME_BANK_SCORE: float = 90
    CRIME_BANK_RADIUS: int = 2
    CRIME_INTERFACE_SCORE: float = 65
    CRIME_DENSE_RESIDENTIAL_COUNT: int = 5
    CRIME_REPORT_HALF_LIFE_STEPS: int = 20
    CRIME_REPORT_RADIUS: float = 3.0  # Euclidean grid cells around each incident
    CRIME_HIGH_THRESHOLD: float = 60
    CRIME_MEDIUM_THRESHOLD: float = 35

    # ── Simulation ──────────────────────────────────────────
    MAX_STEPS: int = 100
    AUTOMATIC_CITY_EVENTS: bool = True
    AUTO_MEDICAL_PROBABILITY: float = 0.20
    AUTO_ROAD_PROBABILITY: float = 0.15
    AUTO_MEDICAL_MAX_PENDING: int = 12
    AUTO_ROAD_MAX_CLOSURES: int = 3
    AUTO_ROAD_DURATION_STEPS = (8, 15)
    COVERAGE_COST_LIMIT: float = 10.0
    COVERAGE_TARGET_PCT: float = 95.0
    MEDIUM_RISK_HEALTH_WEIGHT: float = 0.5
    OPTIMIZATION_MAX_RUNS: int = 10
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
        "BANK": 25,
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
