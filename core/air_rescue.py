"""Building-based air rescue: pickup, hospital delivery, then safe-base return."""
import math
from config.simulation_config import SimConfig


class AirRescue:
    def __init__(self, graph, network, fleet):
        self.graph, self.network, self.fleet = graph, network, fleet
        self.events = fleet.events
        self.capacity = SimConfig.HELICOPTER_FUEL_CAPACITY
        self.fuel = self.capacity
        self.burn = SimConfig.HELICOPTER_FUEL_PER_CELL
        self.reserve = SimConfig.HELICOPTER_RESERVE
        self.low_pct = SimConfig.HELICOPTER_LOW_FUEL_PCT
        buildings = [n for n in network.reachable if self.is_building(n)]
        if not buildings:
            raise ValueError('Air rescue requires a road-served non-hospital building for its base.')
        self.home = min(buildings, key=lambda n: (sum(self.distance(self.point(n), self.point(v)) for v in graph.nodes), n))
        self.default_landings = [self.home]
        # Farthest-point placement gives the city distributed building pads.
        while len(self.default_landings) < min(SimConfig.HELICOPTER_PAD_COUNT, len(buildings)):
            self.default_landings.append(max((n for n in buildings if n not in self.default_landings),
                key=lambda n: (min(self.distance(self.point(n), self.point(p)) for p in self.default_landings), -n)))
        self.custom_landings = [self.home]
        self.position, self.landed_node = self.point(self.home), self.home
        self.status, self.target, self.emergency = 'READY', None, None
        self.carrying = False
        self.diversions = 0
        self.relocation_required = False
        self._exposure = ()
        self._emergency_landing = False

    def point(self, node):
        n = self.graph.nodes[node]
        return float(n.row), float(n.col)

    @staticmethod
    def distance(a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1])

    def is_building(self, node):
        return (node in self.graph.nodes and node not in self.network.centers and
                self.graph.nodes[node].node_type not in (SimConfig.HOSPITAL, SimConfig.DEPOT, SimConfig.EMPTY))

    def unsafe(self, node):
        return bool(self.fleet.disasters and self.fleet.disasters.gates_at(node))

    def landing_nodes(self):
        self.network.refresh()
        return sorted(n for n in set(self.default_landings) | set(self.custom_landings)
                      if self.is_building(n) and n in self.network.reachable and not self.unsafe(n))

    def hospitals(self):
        return sorted(n for n in self.network.centers if not self.unsafe(n))

    def nearest(self, position, permanent=False):
        return min(self.landing_nodes(), key=lambda n: (self.distance(position, self.point(n)), n), default=None)

    def required_reserve(self, position=None):
        position = self.position if position is None else position
        pad = self.nearest(position)
        return self.distance(position, self.point(pad))*self.burn+self.reserve if pad is not None else math.inf

    def hospital_plan(self, position, fuel=math.inf):
        """Nearest safe hospital with fuel for delivery AND a safe building return."""
        plans = []
        for hospital in self.hospitals():
            pad = self.nearest(self.point(hospital))
            if pad is None:
                continue
            distance = self.distance(position, self.point(hospital))
            cost = distance*self.burn+self.required_reserve(self.point(hospital))
            if cost <= fuel+1e-9:
                plans.append((distance, hospital, pad, cost))
        return min(plans, default=None)

    def refresh_safety(self):
        self.fleet.refresh_service()
        exposed = bool(self.landed_node is not None and
                       (self.unsafe(self.landed_node) or
                        (not self.carrying and self.landed_node not in self.landing_nodes())))
        signature = (self.landed_node, tuple(self.fleet.disasters.gates_at(self.landed_node))
                     if self.fleet.disasters and self.landed_node is not None else ()) if exposed else ()
        self.relocation_required = exposed
        if exposed and signature != self._exposure:
            self.network.notify('Assistant required to relocate the helicopter: its current landing building at '+
                self.graph.nodes[self.landed_node].label+' is unsafe or unavailable. Select RELOCATE HELICOPTER for the closest safe non-hospital building.', [self.landed_node])
        self._exposure = signature

    def relocation_plan(self):
        self.refresh_safety()
        candidates = [n for n in self.landing_nodes()
                      if self.distance(self.position, self.point(n))*self.burn+self.reserve <= self.fuel+1e-9]
        target = min(candidates, key=lambda n: (self.distance(self.position, self.point(n)), n), default=None)
        reason = ('Relocate to safe building '+self.graph.nodes[target].label+'.') if target is not None else 'No safe non-hospital landing building within fuel reserve. Restore a pad or refuel while landed.'
        return {'required': self.relocation_required, 'can_relocate': self.relocation_required and target is not None,
                'target': target, 'reason': reason}

    def relocate(self, step):
        plan = self.relocation_plan()
        if not plan['can_relocate']:
            raise ValueError(plan['reason'] if plan['required'] else 'Current helipad is safe; relocation is not required.')
        self.target, self.status, self.landed_node = plan['target'], 'RELOCATING', None
        self._emergency_landing = False
        self.relocation_required = False
        self.network.notify('Assistant initiated relocation to safe building '+self.graph.nodes[self.target].label+'; flight consumes fuel.', [self.target], 'info')
        return self.target

    def set_landings(self, nodes):
        self.network.refresh()
        if not nodes or len(nodes) > len(self.graph.nodes):
            raise ValueError('Provide at least one landing building.')
        if any(not self.is_building(n) or n not in self.network.reachable or self.unsafe(n) for n in nodes):
            raise ValueError('Landing spots must be safe non-hospital buildings with medical road access; hospitals and empty sectors cannot be helicopter bases.')
        self.custom_landings = sorted(set(nodes))
        if self.status in ('RETURNING', 'RELOCATING'):
            self._choose_landing()

    def eligibility(self, target):
        if target not in self.graph.nodes:
            raise ValueError('Unknown emergency sector.')
        self.refresh_safety()
        required = target not in self.fleet.road_reachable()
        if not required:
            return {'required': False, 'can_dispatch': False, 'reason': 'Medical centers can reach this node by road. Use an ambulance.'}
        if self.status != 'READY':
            return {'required': True, 'can_dispatch': False, 'reason': 'Helicopter is busy completing pickup, hospital delivery and return to base.'}
        if self.relocation_required:
            return {'required': True, 'can_dispatch': False, 'reason': self.relocation_plan()['reason']}
        plan = self.hospital_plan(self.point(target))
        if plan is None:
            return {'required': True, 'can_dispatch': False, 'reason': 'No safe hospital and non-hospital return building available. Restore medical access before rescue.'}
        outbound = self.distance(self.position, self.point(target))*self.burn
        budget = max(outbound+plan[3], outbound+self.capacity*self.low_pct/100+self.reserve)
        duplicate = any(e['node_id']==target and e['status'] not in ('RESOLVED','ABORTED') for e in self.fleet.emergencies)
        can_dispatch = self.fuel+1e-9 >= budget and not duplicate
        reason = 'Helicopter required: fly to emergency, nearest safe hospital, then closest safe building.'
        if duplicate:
            reason = 'A rescue is already assigned to this node.'
        elif self.fuel+1e-9 < budget:
            reason = f'Refuel before takeoff. Pickup, hospital delivery and base return need {budget:.1f} fuel including reserve.'
        return {'required': True, 'can_dispatch': can_dispatch, 'reason': reason, 'required_fuel': round(budget,3),
                'hospital': plan[1], 'return_pad': plan[2]}

    def dispatch(self, target, step):
        plan = self.eligibility(target)
        if not plan['can_dispatch']:
            raise ValueError(plan['reason'])
        if len(self.fleet.emergencies) >= SimConfig.MAX_EMERGENCIES:
            raise ValueError('Emergency history is full. Restart the city.')
        self.emergency = {'id': f'E-{len(self.fleet.emergencies)+1:04d}', 'node_id': target,
            'label': self.graph.nodes[target].label, 'ambulance_id': None, 'status': 'AIR_RESPONDING',
            'created_step': step, 'resolved_step': None, 'dispatch_cost': plan['required_fuel'], 'mode': 'AIR',
            'hospital_id': plan['hospital'], 'hospital_arrival_step': None}
        self.fleet.emergencies.append(self.emergency)
        self.target, self.status, self.landed_node = target, 'OUTBOUND', None
        self._emergency_landing = False
        self.network.notify('Helicopter dispatched to '+self.graph.nodes[target].label+'; hospital and return-building fuel reserved.', [target], 'info')
        return self.emergency

    def refuel(self):
        if self.landed_node is None:
            raise ValueError('Refueling is only possible after landing.')
        self.fuel = self.capacity

    def _choose_landing(self):
        pads = [n for n in self.landing_nodes()
                if self.distance(self.position,self.point(n))*self.burn+self.reserve <= self.fuel+1e-9]
        self._emergency_landing = not bool(pads)
        if not pads:
            # Disaster fallback still never treats a hospital as a parking pad.
            pads = [n for n in self.graph.nodes if self.is_building(n) and
                    self.distance(self.position,self.point(n))*self.burn <= self.fuel+1e-9]
        if not pads:
            return False
        self.target = min(pads, key=lambda n: (self.unsafe(n) if self._emergency_landing else False,
                                              self.distance(self.position,self.point(n)), n))
        if self._emergency_landing:
            self.network.notify('Disaster invalidated the normal flight plan. Emergency landing at building '+self.graph.nodes[self.target].label+'; any patient remains unresolved.', [self.target])
        return True

    def _to_hospital(self):
        plan = self.hospital_plan(self.position,self.fuel)
        if plan is None:
            return False
        self.target, self.status, self.landed_node = plan[1], 'TO_HOSPITAL', None
        self.emergency.update(status='AIRBORNE',hospital_id=plan[1])
        self._emergency_landing = False
        return True

    def _divert(self, reason):
        if self.status == 'OUTBOUND' and self.emergency and not self.carrying:
            self.emergency.update(status='ABORTED',reason=reason)
        self.status = 'RETURNING'
        if not self._choose_landing():
            self.status = 'AWAITING_SAFE_LANDING'
        self.diversions += 1
        self.network.notify(reason, [self.target] if self.target is not None else [])

    def advance(self, step):
        self.refresh_safety()
        if self.relocation_required:
            return
        if self.status == 'WAITING_HOSPITAL':
            if self._to_hospital():
                self.network.notify('Hospital access restored; resuming direct patient delivery.', [self.target], 'info')
            return
        if self.status == 'AWAITING_SAFE_LANDING':
            if self._choose_landing():
                self.status='RETURNING'
            return
        if self.status not in ('OUTBOUND','TO_HOSPITAL','RETURNING','RELOCATING'):
            return
        if self.status == 'TO_HOSPITAL':
            if not self._to_hospital():
                self._divert('No safe hospital within the remaining flight budget; landing with patient until care is restored.')
        elif self.status in ('RETURNING','RELOCATING'):
            invalid = self.unsafe(self.target) or (not self._emergency_landing and self.target not in self.landing_nodes())
            if invalid:
                self._divert('Landing building became unavailable; selecting the closest safe alternative.')
        if self.status == 'AWAITING_SAFE_LANDING':
            return
        destination = self.point(self.target)
        distance = self.distance(self.position,destination)
        travel = min(distance,SimConfig.HELICOPTER_SPEED)
        next_pos = destination if distance <= travel else tuple(a+(b-a)*travel/distance for a,b in zip(self.position,destination))
        next_fuel = self.fuel-travel*self.burn
        if self.status == 'OUTBOUND':
            plan = self.hospital_plan(self.point(self.target))
            remaining = self.distance(next_pos,self.point(self.target))*self.burn+(plan[3] if plan else math.inf)
            if self.fuel <= self.capacity*self.low_pct/100 or next_fuel < remaining-1e-9:
                self._divert('Fuel or hospital safety threshold reached before pickup; returning to a safe building.')
                return
        if next_fuel < -1e-8:
            self._divert('Flight destination no longer fits remaining fuel; selecting an emergency landing building.')
            return
        self.position, self.fuel = next_pos,max(0.,next_fuel)
        if travel+1e-9 < distance:
            return
        if self.status == 'OUTBOUND':
            self.carrying=True
            self.emergency['status']='AIRBORNE'
            if not self._to_hospital():
                self._divert('Patient collected, but hospital unavailable; protecting the landing reserve.')
            else:
                self.network.notify('Patient collected at '+self.emergency['label']+'; flying directly to hospital '+self.graph.nodes[self.target].label+'.', [self.target], 'info')
        elif self.status == 'TO_HOSPITAL':
            hospital=self.target
            self.emergency.update(status='RESOLVED',resolved_step=step,hospital_id=hospital,hospital_arrival_step=step)
            self.events.metrics.civilians_rescued += 1
            self.events.metrics.record_response_time(float(step-self.emergency['created_step']))
            self.carrying=False
            self.status='RETURNING'
            self.network.notify('Patient delivered to hospital '+self.graph.nodes[hospital].label+'; helicopter returning to closest safe building.', [hospital], 'info')
            if not self._choose_landing():
                self.status='AWAITING_SAFE_LANDING'
        else:
            self.landed_node=self.target
            self.status='WAITING_HOSPITAL' if self.carrying else 'READY'
            self.target=None
            if self.carrying:
                self.emergency.update(status='WAITING_HOSPITAL',landing_node=self.landed_node)
            self.refresh_safety()

    def to_dict(self):
        plan=self.relocation_plan()
        required=self.required_reserve()
        available=self.landing_nodes()
        sites=sorted(n for n in set(self.default_landings)|set(self.custom_landings) if self.is_building(n))
        return {'depot':self.home,'depot_label':self.graph.nodes[self.home].label,
            'position':list(self.position),'status':self.status,'target':self.target,'landed_node':self.landed_node,
            'carrying_patient':self.carrying,'landed_label':self.graph.nodes[self.landed_node].label if self.landed_node is not None else None,
            'target_label':self.graph.nodes[self.target].label if self.target is not None else None,
            'fuel':round(self.fuel,4),'capacity':self.capacity,'fuel_pct':round(100*self.fuel/self.capacity,1),
            'fuel_per_cell':self.burn,'low_fuel_pct':self.low_pct,'reserve':self.reserve,
            'required_landing_fuel':round(required,4) if math.isfinite(required) else None,
            'relocation':plan,'relocation_required':self.relocation_required,
            'landing_sites':[{'node_id':n,'label':self.graph.nodes[n].label,'kind':'BUILDING',
                              'safe':not self.unsafe(n),'available':n in available} for n in sites],
            'landing_nodes':available,'custom_landings':self.custom_landings,'default_landings':self.default_landings,
            'permanent_landings':sites,'hospital_nodes':self.hospitals(),'diversions':self.diversions,
            'mission_sequence':['BUILDING','EMERGENCY','HOSPITAL','BUILDING'],
            'emergency_id':self.emergency['id'] if self.emergency else None}
