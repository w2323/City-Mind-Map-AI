# ambulance_placement.py — Challenge 3: Ambulance Placement via Genetic Algorithm
# Minimax fitness: minimize worst-case citizen-to-ambulance response time.
#
# CRITICAL FIX: The GA no longer mutates node_type to DEPOT for ambulance positions.
# Ambulance positions are stored as a separate list on the SimulationState,
# preserving the CSP-assigned zone types on the graph.
#
# PERFORMANCE FIX: Dijkstra results are cached per node ID. Since the graph
# doesn't change during a GA run, the same node's shortest-path tree is
# reused across all chromosomes. This reduces Dijkstra calls from
# pop_size × generations × num_ambulances (~36,000) to at most 225 unique nodes.
#
# All algorithms implemented from scratch — no external GA frameworks.

import random
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


class GAambulancePlacer:
    """
    Genetic Algorithm for optimal ambulance placement.

    Objective: Minimize the maximum (worst-case) shortest-path distance
    from any RESIDENTIAL node to its nearest ambulance.

    Representation:
        Chromosome: list of N node IDs representing ambulance positions
        Fitness: lower is better (minimax distance)

    Operators:
        Selection: Tournament selection (k=5)
        Crossover: Uniform crossover
        Mutation: Random replacement per slot
        Elitism: Top 2 carried forward

    Performance:
        Dijkstra results are cached per node ID. The graph does not change
        during a single GA run, so the same node's shortest-path map is
        reused across all chromosomes that include that node.
    """

    def __init__(self, graph: CityGraph,
                 num_ambulances: int = None,
                 pop_size: int = None,
                 generations: int = None,
                 mutation_rate: float = None):
        self.graph = graph
        self.num_ambulances = num_ambulances or SimConfig.GA_NUM_AMBULANCES
        self.pop_size = pop_size or SimConfig.GA_POP_SIZE
        self.generations = generations or SimConfig.GA_GENERATIONS
        self.mutation_rate = mutation_rate or SimConfig.GA_MUTATION_RATE
        self.residential = [n.id for n in graph.get_nodes_of_type(SimConfig.RESIDENTIAL)]
        
        # Only place ambulances at AMBULANCE_DEPOT nodes
        depot_nodes = [n.id for n in graph.get_nodes_of_type(SimConfig.DEPOT)]
        self.available_nodes = depot_nodes if depot_nodes else list(graph.nodes.keys())
        
        self.population: list = []
        self.best_solution: list = None
        self.best_fitness: float = float("inf")

        # Dijkstra cache: node_id -> {dest_id: distance}
        # Since graph state is frozen during GA, we cache all Dijkstra results.
        # At most 225 entries (one per node), regardless of population or generations.
        self._dijkstra_cache: dict = {}

    # ── Cached Dijkstra ─────────────────────────────────────

    def _cached_dijkstra(self, node_id: int) -> dict:
        """
        Return Dijkstra shortest-path distances from node_id.
        Results are cached because the graph doesn't change during a GA run.
        This is the key performance optimization: instead of computing
        Dijkstra 36,000+ times, we compute it at most 225 times.
        """
        if node_id not in self._dijkstra_cache:
            self._dijkstra_cache[node_id] = self.graph.dijkstra(node_id)
        return self._dijkstra_cache[node_id]

    # ── Population initialization ───────────────────────────

    def initialize_population(self):
        """Create pop_size random chromosomes (each = list of node IDs).
        Uses choices (with replacement) to allow multiple ambulances at one depot."""
        self.population = []
        for _ in range(self.pop_size):
            chrom = random.choices(self.available_nodes, k=self.num_ambulances)
            self.population.append(chrom)

    # ── Fitness evaluation ──────────────────────────────────

    def fitness(self, chromosome: list) -> float:
        """
        Minimax fitness: worst-case response time from any residential node
        to its nearest ambulance. Lower is better.

        Uses cached Dijkstra which respects risk multipliers and blocked roads,
        so crime risk predictions automatically affect ambulance placement quality.
        """
        # Get shortest paths from each ambulance position (cached)
        dist_maps = [self._cached_dijkstra(amb_id) for amb_id in chromosome]

        max_dist = 0.0
        for res_id in self.residential:
            # Distance from this residential node to its nearest ambulance
            min_dist = min(
                dist_maps[i].get(res_id, float("inf"))
                for i in range(self.num_ambulances)
            )
            if min_dist > max_dist:
                max_dist = min_dist
        return max_dist

    # ── Selection ───────────────────────────────────────────

    def tournament_selection(self, fitness_cache: dict,
                             tournament_size: int = None) -> list:
        """Tournament selection: pick best from k random contestants."""
        k = tournament_size or SimConfig.GA_TOURNAMENT_SIZE
        contestants = random.sample(self.population, min(k, len(self.population)))
        return min(contestants,
                   key=lambda c: fitness_cache.get(tuple(c), self.fitness(c)))

    # ── Crossover ───────────────────────────────────────────

    def crossover(self, parent1: list, parent2: list) -> tuple:
        """Uniform crossover: for each slot, randomly pick from parent1 or parent2."""
        child1, child2 = [], []
        for i in range(self.num_ambulances):
            if random.random() < 0.5:
                child1.append(parent1[i])
                child2.append(parent2[i])
            else:
                child1.append(parent2[i])
                child2.append(parent1[i])
        # Duplicates are allowed since we can have multiple ambulances at the same depot.
        return child1, child2



    # ── Mutation ────────────────────────────────────────────

    def mutate(self, chromosome: list) -> list:
        """Per-slot mutation: each position has mutation_rate chance of random replacement."""
        result = list(chromosome)
        for i in range(len(result)):
            if random.random() < self.mutation_rate:
                result[i] = random.choice(self.available_nodes)
        return result

    # ── Main GA loop ────────────────────────────────────────

    def run(self) -> list:
        """
        Execute the genetic algorithm.
        Returns list of node IDs for optimal ambulance positions.

        IMPORTANT: Does NOT modify graph node types.
        Ambulance positions are returned as data, not written to graph.
        """
        self.initialize_population()

        # Evaluate initial population fitness
        fitness_cache = {}
        for c in self.population:
            key = tuple(c)
            if key not in fitness_cache:
                fitness_cache[key] = self.fitness(c)

        for gen in range(self.generations):
            new_population = []

            # Elitism: carry forward top chromosomes
            sorted_pop = sorted(
                self.population,
                key=lambda c: fitness_cache.get(tuple(c), float("inf"))
            )
            for i in range(min(SimConfig.GA_ELITISM_COUNT, len(sorted_pop))):
                new_population.append(list(sorted_pop[i]))

            # Track best solution across all generations
            top_fitness = fitness_cache.get(tuple(sorted_pop[0]), float("inf"))
            if top_fitness < self.best_fitness:
                self.best_fitness = top_fitness
                self.best_solution = list(sorted_pop[0])

            # Fill rest of population via selection + crossover + mutation
            while len(new_population) < self.pop_size:
                p1 = self.tournament_selection(fitness_cache)
                p2 = self.tournament_selection(fitness_cache)
                c1, c2 = self.crossover(p1, p2)
                c1 = self.mutate(c1)
                c2 = self.mutate(c2)
                new_population.append(c1)
                if len(new_population) < self.pop_size:
                    new_population.append(c2)

            self.population = new_population

            # Evaluate fitness for new chromosomes
            for c in self.population:
                key = tuple(c)
                if key not in fitness_cache:
                    fitness_cache[key] = self.fitness(c)

        # Final best solution check
        if self.best_solution is None:
            self.best_solution = list(self.population[0])

        return self.best_solution


# ──────────────────────────────────────────────────────────
# Entry points — called by simulation engine
# ──────────────────────────────────────────────────────────
def place_ambulances(graph: CityGraph) -> list:
    """Full GA run for initial ambulance placement."""
    placer = GAambulancePlacer(graph)
    return placer.run()


def place_ambulances_fast(graph: CityGraph) -> list:
    """Fast GA re-evaluation for mid-simulation repositioning."""
    placer = GAambulancePlacer(
        graph,
        pop_size=SimConfig.GA_FAST_POP_SIZE,
        generations=SimConfig.GA_FAST_GENERATIONS,
    )
    return placer.run()
