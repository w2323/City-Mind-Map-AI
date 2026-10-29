# challenge3.py — Challenge 3: Ambulance Placement via Genetic Algorithm (GA)
#
# FIXES APPLIED:
# F4 — Candidate nodes expanded to DEPOT + HOSPITAL nodes for meaningful optimization
# F5 — is_infeasible flag added when best fitness is infinity (unreachable demand)

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

    F4 FIX: Candidate nodes expanded to DEPOT + HOSPITAL nodes.
    Previously candidates were only DEPOT (3 nodes for 3 ambulances),
    making the GA a permutation search with no meaningful optimization.
    With DEPOT + HOSPITAL (up to 9 nodes), the GA has genuine location choices.

    F5 FIX: is_infeasible flag set when best fitness remains infinity,
    indicating some residential demand areas are unreachable from all candidates.
    """

    def __init__(self, graph: CityGraph,
                 num_ambulances: int = None,
                 pop_size: int = None,
                 generations: int = None,
                 mutation_rate: float = None, rng=None):
        self.graph = graph
        self.rng = rng if rng is not None else random.Random()
        self.num_ambulances = num_ambulances or SimConfig.GA_NUM_AMBULANCES
        self.pop_size = pop_size or SimConfig.GA_POP_SIZE
        self.generations = generations or SimConfig.GA_GENERATIONS
        self.mutation_rate = mutation_rate if mutation_rate is not None else SimConfig.GA_MUTATION_RATE
        self.residential = [n.id for n in graph.get_nodes_of_type(SimConfig.RESIDENTIAL)]

        # F4 FIX: Expand candidate nodes to DEPOT + HOSPITAL for meaningful optimization.
        # Previously: only DEPOT nodes (same count as num_ambulances = no real optimization).
        # Now: DEPOT + HOSPITAL gives a larger search space while keeping medically appropriate locations.
        depot_nodes = [n.id for n in graph.get_nodes_of_type(SimConfig.DEPOT)]
        hospital_nodes = [n.id for n in graph.get_nodes_of_type(SimConfig.HOSPITAL)]
        combined = list(set(depot_nodes + hospital_nodes))

        if combined:
            self.available_nodes = combined
        else:
            # Fallback: use all nodes if neither type exists
            self.available_nodes = list(graph.nodes.keys())

        self.population: list = []
        self.best_solution: list = None
        self.best_fitness: float = float("inf")
        self.is_infeasible: bool = False  # F5: True if best fitness is infinity

        # Dijkstra cache: node_id -> {dest_id: distance}
        # Since graph state is frozen during GA, we cache all Dijkstra results.
        # At most 225 entries (one per node), regardless of population or generations.
        self._dijkstra_cache: dict = {}

    def _cached_dijkstra(self, node_id: int) -> dict:
        """
        Return Dijkstra shortest-path distances from node_id.
        Results are cached because the graph doesn't change during a GA run.
        """
        if node_id not in self._dijkstra_cache:
            self._dijkstra_cache[node_id] = self.graph.dijkstra(node_id)
        return self._dijkstra_cache[node_id]

    def initialize_population(self):
        """Create pop_size random chromosomes (each = list of node IDs).
        Ensures unique placement (no duplicates) if enough available nodes exist."""
        self.population = []
        for _ in range(self.pop_size):
            if len(self.available_nodes) >= self.num_ambulances:
                chrom = self.rng.sample(self.available_nodes, self.num_ambulances)
            else:
                chrom = self.rng.choices(self.available_nodes, k=self.num_ambulances)
            self.population.append(chrom)

    def fitness(self, chromosome: list) -> float:
        """
        Minimax fitness: worst-case response time from any residential node
        to its nearest ambulance. Lower is better.

        Uses cached Dijkstra which respects risk multipliers and blocked roads,
        so crime risk predictions automatically affect ambulance placement quality.

        F5: Returns float("inf") for infeasible placements (unreachable demand areas).
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
            if min_dist == float("inf"):
                return float("inf")  # F5: Infeasible — residential node unreachable
            if min_dist > max_dist:
                max_dist = min_dist
        return max_dist

    def tournament_selection(self, fitness_cache: dict,
                             tournament_size: int = None) -> list:
        """Tournament selection: pick best from k random contestants."""
        k = tournament_size or SimConfig.GA_TOURNAMENT_SIZE
        contestants = self.rng.sample(self.population, min(k, len(self.population)))
        return min(contestants,
                   key=lambda c: fitness_cache[tuple(c)])

    def crossover(self, parent1: list, parent2: list) -> tuple:
        """Crossover that ensures unique positions if enough nodes exist."""
        pool = list(set(parent1 + parent2))

        if len(pool) < self.num_ambulances:
            others = list(set(self.available_nodes) - set(pool))
            self.rng.shuffle(others)
            pool.extend(others)

        if len(pool) >= self.num_ambulances:
            child1 = self.rng.sample(pool, self.num_ambulances)
            child2 = self.rng.sample(pool, self.num_ambulances)
        else:
            child1 = self.rng.choices(pool, k=self.num_ambulances)
            child2 = self.rng.choices(pool, k=self.num_ambulances)

        return child1, child2

    def mutate(self, chromosome: list) -> list:
        """Mutation that tries to pick unused nodes to maintain uniqueness."""
        result = list(chromosome)
        for i in range(len(result)):
            if self.rng.random() < self.mutation_rate:
                candidates = [n for n in self.available_nodes if n not in result]
                if not candidates:
                    candidates = self.available_nodes
                result[i] = self.rng.choice(candidates)
        return result

    def run(self, progress=None) -> list:
        """
        Execute the genetic algorithm.
        Returns list of node IDs for optimal ambulance positions.

        F5 FIX: Sets is_infeasible=True if best fitness is still infinity after all generations.
        NOTE (F4): With expanded candidates (DEPOT + HOSPITAL), the GA has a real optimization
        problem. The returned placement is the best found, not guaranteed global optimum.

        IMPORTANT: Does NOT modify graph node types.
        Ambulance positions are returned as data, not written to graph.
        """
        if not self.available_nodes:
            self.is_infeasible = True
            return []

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

            best = min(self.population, key=lambda c: fitness_cache[tuple(c)])
            if self.best_solution is None or fitness_cache[tuple(best)] < self.best_fitness:
                self.best_solution = list(best)
                self.best_fitness = fitness_cache[tuple(best)]
            if progress is not None:
                progress(gen + 1, self.best_fitness, self.best_solution)

        # Final best solution check
        if self.best_solution is None:
            self.best_solution = list(self.population[0]) if self.population else []

        # F5 FIX: Set infeasibility flag if best fitness is still infinite
        if self.best_fitness == float("inf"):
            self.is_infeasible = True

        return self.best_solution


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
