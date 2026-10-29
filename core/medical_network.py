"""Road-connected medical coverage and reproducible genetic facility planning."""
import math
import random
from config.simulation_config import SimConfig
from core.event_manager import EventType


class MedicalCenterPlanner:
    """Maximise reachable nodes first, then minimise mean and worst road cost.

    Candidates are city nodes, not a randomly preselected set of depots. Elitism
    preserves the best placement; a greedy seed gives every component a chance.
    """
    def __init__(self, graph, count=None, rng=None, generations=35, pop_size=24):
        self.graph = graph
        self.rng = rng or random.Random(0)
        self.count = min(count or SimConfig.REQUIRED_COUNTS[SimConfig.HOSPITAL], len(graph.nodes))
        self.generations, self.pop_size = generations, pop_size
        self.candidates = sorted(n.id for n in graph.nodes.values() if n.node_type in
                                 (SimConfig.EMPTY, SimConfig.RESIDENTIAL, SimConfig.HOSPITAL, SimConfig.DEPOT))
        self.count = min(self.count, len(self.candidates))
        if not self.count:
            raise ValueError('No eligible nodes for medical-center placement')
        self.targets = sorted(graph.nodes)
        self.distances = {n: graph.dijkstra(n) for n in self.candidates}
        self.best_fitness = float('inf')
        self.is_infeasible = False

    def score(self, placement):
        nearest = [min(self.distances[c][n] for c in placement) for n in self.targets]
        finite = [d for d in nearest if math.isfinite(d)]
        missing = len(nearest)-len(finite)
        return (missing, sum(finite)/max(1, len(finite)), max(finite, default=0))

    def run(self, progress=None):
        greedy = []
        for _ in range(self.count):
            greedy.append(min((n for n in self.candidates if n not in greedy),
                              key=lambda n: (self.score(greedy+[n]), n)))
        population = [greedy] + [self.rng.sample(self.candidates, self.count) for _ in range(self.pop_size-1)]
        scores = {}
        def rank(p):
            key = tuple(sorted(p))
            if key not in scores:
                scores[key] = self.score(key)
            return scores[key]
        for generation in range(self.generations):
            population.sort(key=rank)
            score = rank(population[0])
            self.best_fitness = score[0]*1e9 + score[1] + score[2]*1e-6
            if progress:
                progress(generation+1, self.best_fitness, sorted(population[0]))
            next_population = population[:2]
            while len(next_population) < self.pop_size:
                parents = [min(self.rng.sample(population, min(4, len(population))), key=rank) for _ in range(2)]
                pool = list(dict.fromkeys(parents[0]+parents[1]))
                child = self.rng.sample(pool, self.count)
                if self.rng.random() < .45 and self.count < len(self.candidates):
                    child[self.rng.randrange(self.count)] = self.rng.choice([n for n in self.candidates if n not in child])
                next_population.append(child)
            population = next_population
        best = min(population, key=rank)
        score = rank(best)
        self.is_infeasible = bool(score[0])
        self.best_fitness = score[0]*1e9 + score[1] + score[2]*1e-6
        return sorted(best)


class MedicalNetwork:
    def __init__(self, graph, centers, events):
        self.graph, self.centers, self.events = graph, sorted(set(centers)), events
        self.notifications = []
        self._signature = None
        self.reachable = set()
        self.distances = {}
        self.recommendations = []
        self.refresh()

    def notify(self, message, nodes=(), kind='warning'):
        entry = {'id': (self.notifications[-1]['id']+1 if self.notifications else 1),
                 'message': message, 'node_ids': sorted(nodes),
                 'labels': [self.graph.nodes[n].label for n in sorted(nodes)], 'kind': kind}
        self.notifications.append(entry)
        self.notifications = self.notifications[-100:]
        self.events.log(EventType.AMBULANCE, message, level='warning' if kind == 'warning' else 'info')

    def refresh(self):
        signature = (tuple(self.centers), tuple((k, e.blocked, e.cost) for k, e in self.graph.edges.items()),
                     tuple((n.id, n.risk_level) for n in self.graph.nodes.values()))
        if signature == self._signature:
            return
        previous, initial = self.reachable, self._signature is None
        self.distances = {c: self.graph.dijkstra(c) for c in self.centers}
        self.reachable = {n for distances in self.distances.values() for n, cost in distances.items() if math.isfinite(cost)}
        self._signature = signature
        lost, restored = previous-self.reachable, self.reachable-previous
        if lost:
            self.notify('Medical centers cut off from: '+', '.join(self.graph.nodes[n].label for n in sorted(lost)), lost)
        if restored and not initial:
            self.notify('Medical road coverage restored: '+', '.join(self.graph.nodes[n].label for n in sorted(restored)), restored, 'info')
        # Each uncovered component needs its own facility. Within that component,
        # choose its exact road medoid: greatest reach, then least mean road cost.
        remaining = set(self.graph.nodes)-self.reachable
        self.recommendations = []
        while remaining:
            start = min(remaining)
            distances = self.graph.dijkstra(start)
            component = sorted(n for n in remaining if math.isfinite(distances[n]))
            local = {n: self.graph.dijkstra(n) for n in component}
            best = min(component, key=lambda n: (sum(local[n][v] for v in component)/len(component),
                                                 max(local[n][v] for v in component), n))
            self.recommendations.append({'node_id': best, 'label': self.graph.nodes[best].label,
                                         'covered_nodes': component, 'gain': len(component),
                                         'mean_cost': round(sum(local[best][v] for v in component)/len(component), 3),
                                         'isolated': len(component) == 1})
            remaining.difference_update(component)
        self.recommendations.sort(key=lambda r: (-r['gain'], r['mean_cost'], r['node_id']))
        if lost and self.recommendations:
            best = self.recommendations[0]
            self.notify(f"Suggested new medical center: {best['label']} reconnects service to {best['gain']} node(s).", best['covered_nodes'], 'recommendation')

    def to_dict(self):
        self.refresh()
        return {'centers': self.centers, 'center_labels': [self.graph.nodes[n].label for n in self.centers],
                'reachable_nodes': sorted(self.reachable), 'unreachable_nodes': sorted(set(self.graph.nodes)-self.reachable),
                'coverage_pct': round(100*len(self.reachable)/max(1, len(self.graph.nodes)), 1),
                'recommendations': self.recommendations, 'notifications': self.notifications,
                'placement_policy': 'Genetic algorithm: maximise road reach, then minimise mean and worst response cost'}
