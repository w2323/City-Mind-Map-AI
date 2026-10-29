"""Explicit, multi-ambulance emergency dispatch on the shared city graph."""
import math
from challenges.challenge4 import AStarRouter
from config.simulation_config import SimConfig
from core.event_manager import EventType


class AmbulanceFleet:
    def __init__(self, graph, events, centers=None):
        self.graph, self.events = graph, events
        self.router = AStarRouter(graph, observe=False, travel_mode='ambulance')
        self.units = []
        self.emergencies = []
        self.network = None
        self.disasters = None
        self._seen_gates = set()
        homes = sorted(centers) if centers is not None else sorted(n.id for n in graph.get_nodes_of_type(SimConfig.DEPOT))
        for home in homes:
            self.add_center(home)

    def add_center(self, home):
        self.units.append({'id': f'AMB-{len(self.units)+1:02d}', 'depot': home, 'position': home,
                               'status': 'AVAILABLE', 'service_reason': None, 'gate_ids': [],
                               'phase': None, 'emergency_id': None, 'path': [], 'target': None})

    def refresh_service(self):
        active = {g['id'] for g in self.disasters.gates} if self.disasters else set()
        newly_unleashed = active - self._seen_gates
        for unit in self.units:
            # Vehicles caught when a Gate is unleashed remain disabled until it
            # clears. Unaffected ambulances retain their existing road privilege.
            gates = sorted((set(unit['gate_ids']) & active) |
                           (set(self.disasters.gates_at(unit['depot'])) |
                            (set(self.disasters.gates_at(unit['position'])) & newly_unleashed)
                            if self.disasters else set()))
            was_disabled = unit['status'] == 'OUT_OF_SERVICE'
            unit['gate_ids'] = gates
            if gates:
                unit.update(status='OUT_OF_SERVICE', path=[],
                            service_reason='Gate of Death includes medical center or ambulance location')
                if not was_disabled:
                    message = f"{unit['id']} is out of service: Gate of Death affects its medical center or location at {self.graph.nodes[unit['position']].label}."
                    if self.network:
                        self.network.notify(message, sorted({unit['depot'], unit['position']}))
                    else:
                        self.events.log(EventType.AMBULANCE, message)
            elif was_disabled:
                unit.update(status=unit['phase'] or 'AVAILABLE', service_reason=None)
                if self.network:
                    self.network.notify(f"{unit['id']} returned to service; pending assignment retained.", [unit['position']], 'info')
        self._seen_gates = active

    def road_reachable(self):
        """Road service from operational units, including busy units (queue vs outage)."""
        self.refresh_service()
        reached = {unit['depot'] for unit in self.units if unit['status'] != 'OUT_OF_SERVICE'}
        pending = list(reached)
        while pending:
            node = pending.pop()
            for neighbor in self.graph.get_neighbors(node, 'ambulance'):
                if neighbor not in reached:
                    reached.add(neighbor)
                    pending.append(neighbor)
        return reached

    def report(self, target, step, source='AUTOMATIC'):
        """Retain a medical call even when the fleet is temporarily busy."""
        if target not in self.graph.nodes:
            raise KeyError('Emergency node does not exist')
        if len(self.emergencies)>=SimConfig.MAX_EMERGENCIES:
            raise ValueError('Emergency history is full')
        if any(e['node_id']==target and e['status'] not in ('RESOLVED','ABORTED') for e in self.emergencies):
            raise ValueError('An ambulance is already responding to this node')
        emergency={'id':f'E-{len(self.emergencies)+1:04d}','node_id':target,'label':self.graph.nodes[target].label,
                   'ambulance_id':None,'status':'QUEUED','created_step':step,'resolved_step':None,
                   'dispatch_cost':None,'source':source}
        self.emergencies.append(emergency)
        self.events.log(EventType.AMBULANCE,f"{emergency['id']}: {source.lower()} medical emergency reported at {emergency['label']}.")
        self.assign_queued(step)
        return emergency

    def assign_queued(self, step):
        for emergency in self.emergencies:
            if emergency['status']=='QUEUED':
                try:
                    self.dispatch(emergency['node_id'],step,_emergency=emergency)
                except ValueError as exc:
                    emergency['reason']=str(exc)

    def dispatch(self, target, step, _emergency=None):
        self.refresh_service()
        if target not in self.graph.nodes:
            raise KeyError('Emergency node does not exist')
        if any(e is not _emergency and e['node_id'] == target and e['status'] not in ('RESOLVED', 'ABORTED') for e in self.emergencies):
            raise ValueError('An ambulance is already responding to this node')
        candidates = []
        for unit in self.units:
            if unit['status'] != 'AVAILABLE':
                continue
            path = self.router.astar(unit['position'], target)
            if path is not None:
                cost = sum(self.graph.get_edge_cost(a, b) for a, b in zip(path, path[1:]))
                candidates.append((cost, unit['id'], unit, path))
        if not candidates:
            raise ValueError('No available ambulance can reach this node. Wait for a unit to return or restore roads.')
        cost, _, unit, path = min(candidates, key=lambda item: item[:2])
        if _emergency is None and len(self.emergencies) >= SimConfig.MAX_EMERGENCIES:
            raise ValueError('Emergency history is full. Restart the city to begin a new session.')
        emergency = _emergency or {'id': f'E-{len(self.emergencies)+1:04d}', 'node_id': target, 'label': self.graph.nodes[target].label,
                     'ambulance_id': unit['id'], 'status': 'RESPONDING', 'created_step': step,
                     'resolved_step': None, 'dispatch_cost': round(cost, 6), 'source':'MANUAL'}
        emergency.update(ambulance_id=unit['id'],status='RESPONDING',dispatch_cost=round(cost,6))
        emergency.pop('reason',None)
        if _emergency is None:
            self.emergencies.append(emergency)
        unit.update(status='RESPONDING', phase='RESPONDING', target=target, emergency_id=emergency['id'], path=path)
        self.events.log(EventType.ROUTING, f"{emergency['id']}: {unit['id']} dispatched to {emergency['label']} (route cost {cost:.2f}).")
        if len(path) == 1:
            self._arrive(unit, step)
        return emergency

    def release_blocked_response(self, emergency, step):
        """Release a failed road assignment so its patient can request air rescue."""
        if emergency['status']!='RESPONDING':
            return False
        unit=next((u for u in self.units if u['emergency_id']==emergency['id'] and u['phase']=='RESPONDING'),None)
        if unit is None or self.router.astar(unit['position'],emergency['node_id']) is not None:
            return False
        emergency.update(status='ABORTED',reason='Road response lost access; patient requires reassignment')
        path=self.router.astar(unit['position'],unit['depot'])
        unit.update(status='RETURNING' if path else 'BLOCKED',phase='RETURNING',target=unit['depot'],
                    emergency_id=None,path=path or [])
        if unit['position']==unit['depot']:
            self._arrive(unit,step)
        self.events.log(EventType.ROUTING,f"{emergency['id']}: road assignment released after access was lost; patient remains unresolved.")
        return True

    def pickup(self, emergency, landing, step):
        """Assign an existing air patient to a real road pickup, without recounting it."""
        self.refresh_service()
        candidates = []
        for unit in self.units:
            if unit['status'] != 'AVAILABLE':
                continue
            path = self.router.astar(unit['position'], landing)
            if path is not None:
                candidates.append((sum(self.graph.get_edge_cost(a,b) for a,b in zip(path,path[1:])), unit['id'], unit, path))
        if not candidates:
            return False
        _, _, unit, path = min(candidates, key=lambda c: c[:2])
        emergency.update(status='PICKUP_EN_ROUTE', ambulance_id=unit['id'], landing_node=landing)
        unit.update(status='PICKUP', phase='PICKUP', target=landing, emergency_id=emergency['id'], path=path)
        if len(path) == 1:
            self._arrive(unit, step)
        return True

    def _arrive(self, unit, step):
        if unit['phase'] == 'PICKUP':
            emergency = next(e for e in self.emergencies if e['id'] == unit['emergency_id'])
            emergency['status'] = 'TRANSPORTING'
            unit.update(status='DELIVERING', phase='DELIVERING', target=unit['depot'])
            unit['path'] = self.router.astar(unit['position'], unit['depot']) or []
            self.events.log(EventType.ROUTING, f"{unit['id']} collected air patient at {self.graph.nodes[unit['position']].label}; transporting to medical center.")
            if unit['position'] != unit['depot']:
                return
        if unit['phase'] in ('RESPONDING', 'DELIVERING'):
            emergency = next(e for e in self.emergencies if e['id'] == unit['emergency_id'])
            emergency.update(status='RESOLVED', resolved_step=step)
            self.events.metrics.civilians_rescued += 1
            self.events.metrics.record_response_time(float(step-emergency['created_step']))
            self.events.log(EventType.ROUTING, f"{unit['id']} arrived at {emergency['label']}. Emergency resolved; returning to depot.")
            unit.update(status='RETURNING', phase='RETURNING', target=unit['depot'])
            unit['path'] = self.router.astar(unit['position'], unit['depot']) or []
            if unit['position'] != unit['depot']:
                return
        unit.update(status='AVAILABLE', phase=None, target=None, emergency_id=None, path=[])
        self.events.log(EventType.AMBULANCE, f"{unit['id']} is available at depot {self.graph.nodes[unit['depot']].label}.")

    def replan(self):
        self.refresh_service()
        for unit in self.units:
            if unit['status'] == 'OUT_OF_SERVICE' or unit['phase'] is None:
                continue
            path = self.router.astar(unit['position'], unit['target'])
            if unit['phase'] == 'PICKUP' and self.router.astar(unit['target'], unit['depot']) is None:
                path = None  # Do not collect a patient without a route back to care.
            if path is None:
                if unit['phase'] == 'PICKUP':
                    emergency = next(e for e in self.emergencies if e['id'] == unit['emergency_id'])
                    emergency.update(status='WAITING_HANDOFF', ambulance_id=None)
                    unit.update(phase='RETURNING', target=unit['depot'], emergency_id=None)
                    path = self.router.astar(unit['position'], unit['depot'])
                    unit.update(status='RETURNING' if path else 'BLOCKED', path=path or [])
                    continue
                unit.update(status='BLOCKED', path=[])
            else:
                # Compare the remaining journey, not path history.
                if unit['path'] and unit['path'] != path:
                    self.events.metrics.total_reroutes += 1
                unit.update(status=unit['phase'], path=path)
        self.events.metrics.civilians_unreachable = sum(u['status'] == 'BLOCKED' and u['phase'] == 'RESPONDING' for u in self.units)

    def advance(self, step):
        self.replan()
        self.assign_queued(step)
        for unit in self.units:
            if unit['phase'] is None or not unit['path']:
                continue
            if len(unit['path']) > 1:
                unit['position'] = unit['path'][1]
                unit['path'] = unit['path'][1:]
                self.refresh_service()
                if unit['status'] == 'OUT_OF_SERVICE':
                    continue
            if unit['position'] == unit['target']:
                self._arrive(unit, step)

    def to_dict(self):
        self.refresh_service()
        result = []
        for unit in self.units:
            home = self.graph.nodes[unit['depot']]
            distances = self.graph.dijkstra(home.id) if self.network is None else self.network.distances[home.id]
            reachable = {n for n,d in distances.items() if math.isfinite(d)}
            result.append({**unit, 'depot_label': home.label, 'position_label': self.graph.nodes[unit['position']].label,
                           'reachable_nodes': sorted(reachable) if unit['status'] != 'OUT_OF_SERVICE' else []})
        return result

    def compatibility_router(self):
        active = next((u for u in self.units if u['phase'] == 'RESPONDING'), None)
        active = active or next((u for u in self.units if u['phase']), None)
        pending = [e['node_id'] for e in self.emergencies if e['status'] not in ('RESOLVED', 'ABORTED')]
        latest = {e['node_id']: e for e in self.emergencies}
        return {'current_pos': active['position'] if active else None,
                'current_path': list(active['path']) if active else [],
                'civilians_remaining': pending,
                'civilians_deferred': [n for n,e in latest.items() if e['status'] == 'ABORTED'],
                'civilians_rescued': [e['node_id'] for e in self.emergencies if e['status'] == 'RESOLVED'],
                'total_reroutes': self.events.metrics.total_reroutes,
                'mission_start_id': active['depot'] if active else None,
                'mission_target_id': active['target'] if active else None}

    def summary(self):
        residential = {n.id for n in self.graph.get_nodes_of_type(SimConfig.RESIDENTIAL)}
        covered = self.road_reachable()
        return {'available': sum(u['status'] == 'AVAILABLE' for u in self.units), 'total': len(self.units),
                'queued':sum(e['status']=='QUEUED' for e in self.emergencies),
                'active': sum(e['status'] not in ('RESOLVED', 'ABORTED') for e in self.emergencies),
                'resolved': sum(e['status'] == 'RESOLVED' for e in self.emergencies),
                'coverage_pct': round(100*len(residential & covered)/len(residential),1) if residential else 100,
                'covered_nodes': sorted(covered), 'out_of_service': sum(u['status'] == 'OUT_OF_SERVICE' for u in self.units),
                'dispatch_policy': 'nearest reachable available ambulance', 'reachable_nodes': sorted(covered)}
