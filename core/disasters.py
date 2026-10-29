"""Gate of Death restricts intersecting road segments to ambulance traffic."""
from config.simulation_config import SimConfig
from core.event_manager import EventType


def segment_distance(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length_sq = dx*dx+dy*dy
    t = max(0., min(1., ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length_sq)) if length_sq else 0.
    return ((point[0]-a[0]-t*dx)**2+(point[1]-a[1]-t*dy)**2)**.5


class DisasterManager:
    def __init__(self, graph, events):
        self.graph, self.events = graph, events
        self.gates = []
        self.history = []
        self._next_id = 1

    def gates_at(self, node):
        """Facility/vehicle exposure uses the circle, independently of road access."""
        point = self.graph.nodes[node]
        return [g['id'] for g in self.gates
                if (point.row-self.graph.nodes[g['node_id']].row)**2 +
                   (point.col-self.graph.nodes[g['node_id']].col)**2 <= (g['radius']+1e-9)**2]

    def preview(self, node, intensity):
        if type(node) is not int or node not in self.graph.nodes:
            raise ValueError('Unknown gate center node')
        if type(intensity) is not int or not 1 <= intensity <= 8:
            raise ValueError('Gate intensity must be an integer from 1 to 8')
        radius = SimConfig.GATE_OF_DEATH_RADII[intensity-1]
        center = self.graph.nodes[node]
        roads = []
        for key, edge in self.graph.edges.items():
            a, b = self.graph.nodes[edge.node_a], self.graph.nodes[edge.node_b]
            if segment_distance((center.row,center.col),(a.row,a.col),(b.row,b.col)) <= radius+1e-9:
                roads.append(list(key))
        return {'node_id': node, 'label': center.label, 'intensity': intensity,
                'radius': radius, 'affected_roads': sorted(roads), 'road_count': len(roads)}

    def unleash(self, node, intensity, step):
        if len(self.gates) >= SimConfig.MAX_ACTIVE_GATES:
            raise ValueError('Clear active gates before unleashing more')
        gate = {**self.preview(node,intensity), 'id': f'GATE-{self._next_id:04d}', 'created_step': step}
        self._next_id += 1
        for a,b in gate['affected_roads']:
            edge = self.graph.edges[(a,b)]
            edge.gate_ids.add(gate['id'])
            edge.temporarily_blocked = True
        self.gates.append(gate)
        self.graph.notify_access_changed()
        self.record('gate', step, f"Gate of Death {intensity} unleashed at {gate['label']}: radius {gate['radius']:g}, {gate['road_count']} roads restricted to ambulances.")
        return gate

    def record(self, action, step, message):
        self.history.append({'action':action,'step':step,'message':message})
        self.history = self.history[-200:]
        self.events.log(EventType.ROADS,message)

    def clear(self, step):
        changed = sum(e.temporarily_blocked for e in self.graph.edges.values())
        for edge in self.graph.edges.values():
            edge.temporarily_blocked = False
            edge.gate_ids.clear()
        self.gates.clear()
        self.graph.notify_access_changed()
        self.record('clear_gates',step,f'Gate restrictions cleared from {changed} roads. Full road blocks remain in effect.')
        return changed

    def to_dict(self):
        return {'gates': [{**gate, 'restricted_roads': sum(gate['id'] in e.gate_ids for e in self.graph.edges.values())} for gate in self.gates],
                'levels': [{'intensity':i,'radius':radius} for i,radius in enumerate(SimConfig.GATE_OF_DEATH_RADII,1)],
                'history':self.history,
                'ambulance_only_roads':sum(e.temporarily_blocked and not e.blocked for e in self.graph.edges.values()),
                'fully_blocked_roads':self.graph.count_blocked_edges(),
                'normal_open_roads':sum(e.allows('normal') for e in self.graph.edges.values())}
