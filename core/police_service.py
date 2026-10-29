"""Operational police stations, physical patrols, reports and medical coordination.

All police road travel uses normal access: a Gate of Death grants no police
exception. Risk is a synthetic planning input, distinct from incident outcomes.
"""
import math
import random
from collections import Counter
from challenges.challenge4 import AStarRouter
from core.medical_network import MedicalCenterPlanner
from core.event_manager import EventType
from config.simulation_config import SimConfig
from core.bank_placement import in_direction,grid_distance

INCIDENT_TYPES = ('THEFT', 'VANDALISM', 'DISTURBANCE', 'INJURY')


class PoliceStationPlanner(MedicalCenterPlanner):
    """Genetic placement: reach first, weighted mean response and worst cost next."""
    def __init__(self, graph, count, seed=0, strategy='risk_weighted', demand=None):
        self.graph, self.rng = graph, random.Random(seed)
        self.targets = sorted(graph.nodes)
        self.bank_directions=getattr(graph,'bank_directions',{})
        eligible = [n.id for n in graph.nodes.values() if n.node_type in (SimConfig.EMPTY, SimConfig.RESIDENTIAL)]
        fallback=[n.id for n in graph.nodes.values() if n.node_type!=SimConfig.BANK]
        if self.bank_directions:
            hospitals=graph.get_nodes_of_type(SimConfig.HOSPITAL)
            eligible=[n for n in eligible if all(grid_distance(graph.nodes[n],h)>=SimConfig.POLICE_HOSPITAL_MIN_BLOCKS for h in hospitals)]
            fallback=[n for n in fallback if all(grid_distance(graph.nodes[n],h)>=SimConfig.POLICE_HOSPITAL_MIN_BLOCKS for h in hospitals)]
        self.candidates = sorted(eligible if len(eligible) >= count else fallback)
        self.count = min(count, len(self.candidates))
        if self.count < 1:
            raise ValueError('At least one police station is required')
        self.generations, self.pop_size = SimConfig.POLICE_GA_GENERATIONS, SimConfig.POLICE_GA_POPULATION
        self.distances = {n: graph.dijkstra(n, 'normal') for n in self.candidates}
        self.banks=[n.id for n in graph.get_nodes_of_type(SimConfig.BANK)]
        self.bank_blocks={c:{b:abs(graph.nodes[c].row-graph.nodes[b].row)+abs(graph.nodes[c].col-graph.nodes[b].col)
                             for b in self.banks} for c in self.candidates}
        self.bank_allowed={c:{b:(SimConfig.POLICE_BANK_MIN_BLOCKS<=self.bank_blocks[c][b]<=SimConfig.POLICE_BANK_MAX_BLOCKS
                               and math.isfinite(self.distances[c][b])
                               and (b not in self.bank_directions or in_direction(graph.nodes[b],graph.nodes[c],self.bank_directions[b])))
                              for b in self.banks} for c in self.candidates}
        self.weights = {n: (SimConfig.POLICE_RISK_WEIGHTS.get(graph.nodes[n].risk_level, 1)+min(10,(demand or {}).get(n,0))
                            if strategy == 'risk_weighted' else 1) for n in self.targets}
        self.best_fitness, self.is_infeasible = float('inf'), False

    def score(self, placement):
        nearest = {n: min(self.distances[c][n] for c in placement) for n in self.targets}
        finite = {n:d for n,d in nearest.items() if math.isfinite(d)}
        worst = max(finite.values(), default=0)
        mean = sum(d*self.weights[n] for n,d in finite.items())/max(1,sum(self.weights[n] for n in finite))
        missing_banks=0
        preference=0
        for bank in self.banks:
            blocks=[self.bank_blocks[c][bank] for c in placement
                    if self.bank_allowed[c][bank]]
            if not blocks:
                missing_banks+=1
            else:
                preference+=min(abs(d-SimConfig.POLICE_BANK_PREFERRED_BLOCKS) for d in blocks)
        return (missing_banks*(len(self.targets)+1)+len(nearest)-len(finite),
                mean+.05*worst+SimConfig.POLICE_BANK_PREFERENCE_WEIGHT*preference,worst)


class PoliceService:
    def __init__(self, graph, events, fleet=None, network=None, air=None, seed=0,
                 stations=None, unit_count=None, strategy='risk_weighted', station_count=None,dynamic_crime=False):
        self.graph, self.events = graph, events
        self.fleet, self.network, self.air = fleet, network, air
        self.seed, self.strategy = seed, strategy
        self.dynamic_crime=dynamic_crime
        self.rng = random.Random(seed)
        self.router = AStarRouter(graph, observe=False, travel_mode='normal')
        self.stations, self.units, self.reports = [], [], []
        self.patrol_enabled, self.automatic_incidents = True, False
        self.auto_probability = SimConfig.POLICE_AUTO_PROBABILITY
        self.last_visited, self.report_counts = {}, Counter()
        self.patrol_visits = Counter()
        self.patrol_destination_visits = Counter()
        self.response_times, self.metrics_history = [], []
        self.distance_travelled, self.reroutes = 0., 0
        self.plan = None
        self._coverage_key, self._covered = None, set()
        sites = stations if stations is not None else PoliceStationPlanner(graph, station_count or SimConfig.POLICE_STATIONS, seed, strategy).run()
        count = SimConfig.NUM_POLICE_OFFICERS if unit_count is None else unit_count
        for i,node in enumerate(sites):
            amount = count//len(sites)+(i < count%len(sites))
            self.add_station(node, amount)

    def log(self, message):
        self.events.log(EventType.POLICE, message)

    def add_station(self, node, count=None):
        count = SimConfig.POLICE_NEW_STATION_UNITS if count is None else count
        if node not in self.graph.nodes or any(s['node_id']==node for s in self.stations):
            raise ValueError('Choose a valid node without an existing police station')
        if self.graph.nodes[node].node_type==SimConfig.BANK:
            raise ValueError('Choose a separate police station plot; bank buildings must remain banks')
        if len(self.stations)>=SimConfig.POLICE_MAX_STATIONS or len(self.units)+count>SimConfig.POLICE_MAX_UNITS:
            raise ValueError('Police station or vehicle limit reached')
        station = {'id':f'PS-{len(self.stations)+1:02d}', 'node_id':node, 'label':self.graph.nodes[node].label}
        self.stations.append(station)
        for index in range(count):
            self.units.append({'id':f'POL-{len(self.units)+1:02d}', 'station_id':station['id'], 'home':node,
                               'position':node,'status':'AVAILABLE','phase':None,'target':None,'path':[],
                               'report_id':None,'reserve':index==0,'service_until':None,
                               'patrol_zone':None,'patrol_level':None})
        self._coverage_key = None
        self.log(f"Police station {station['id']} opened at {station['label']} with {count} patrol car(s).")
        return station

    def _report(self, report_id):
        return next(r for r in self.reports if r['id']==report_id)

    def report(self, node, kind, severity, step, medical=False, source='MANUAL'):
        if node not in self.graph.nodes or kind not in INCIDENT_TYPES or type(severity) is not int or severity not in (1,2,3):
            raise ValueError('Invalid node, incident type or severity')
        if any(r['node_id']==node and r['status']!='RESOLVED' for r in self.reports):
            raise ValueError('An active crime report already exists at this node')
        if len(self.reports)>=SimConfig.POLICE_MAX_REPORTS or sum(r['status']!='RESOLVED' for r in self.reports)>=SimConfig.POLICE_MAX_OPEN_REPORTS:
            raise ValueError('Crime report limit reached; resolve reports or restart the city')
        report = {'id':f'CR-{len(self.reports)+1:04d}','node_id':node,'label':self.graph.nodes[node].label,
                  'kind':kind,'severity':severity,'source':source,'created_step':step,'arrival_step':None,
                  'police_completed_step':None,'resolved_step':None,'unit_id':None,'police_status':'QUEUED',
                  'status':'QUEUED','reason':'Waiting for an available unit','medical_required':medical or kind=='INJURY',
                  'medical_emergency_id':None,'medical_status':'QUEUED' if medical or kind=='INJURY' else 'NONE'}
        self.reports.append(report)
        self.report_counts[node] += 1
        self.log(f"{report['id']}: {kind.title()} reported at {report['label']}, severity {severity}.")
        self.refresh(step)
        return report

    def configure(self, step, patrol_enabled=None, automatic_incidents=None, auto_probability=None):
        if auto_probability is not None and (not math.isfinite(auto_probability) or not 0<=auto_probability<=1):
            raise ValueError('Incident probability must be between 0 and 1')
        if patrol_enabled is not None:
            self.patrol_enabled = patrol_enabled
        if automatic_incidents is not None:
            self.automatic_incidents = automatic_incidents
        if auto_probability is not None:
            self.auto_probability = auto_probability
        self.refresh(step)

    def _park_patrols(self):
        """OFF cancels routine journeys in place, without cancelling real cases."""
        if not self.patrol_enabled:
            for unit in self.units:
                if unit['phase']=='PATROLLING':
                    unit.update(status='AVAILABLE',phase=None,target=None,path=[],report_id=None,service_until=None,
                                patrol_zone=None,patrol_level=None)

    @staticmethod
    def _can_dispatch(unit):
        # Completed responders need not reach home before taking another call.
        # A car cut off from its home can still serve its own road component.
        return (unit['report_id'] is None and unit['phase'] in (None,'PATROLLING','RETURNING')
                and unit['status'] in ('AVAILABLE','PATROLLING','RETURNING','BLOCKED'))

    def _return(self, unit):
        unit.update(report_id=None, target=unit['home'], phase='RETURNING', service_until=None)
        if unit['position']==unit['home']:
            unit.update(status='AVAILABLE',phase=None,target=None,path=[])
        else:
            path=self.router.astar(unit['position'],unit['home'])
            unit.update(path=path or [], status='RETURNING' if path else 'BLOCKED')

    def _arrive(self, unit, step):
        if unit['phase']=='RESPONDING':
            report=self._report(unit['report_id'])
            report.update(police_status='ON_SCENE',arrival_step=step,reason='Police handling the report')
            self.response_times.append(step-report['created_step'])
            unit.update(status='ON_SCENE',phase='ON_SCENE',path=[],
                        service_until=step+SimConfig.POLICE_HANDLING_STEPS[report['severity']])
            self.log(f"{unit['id']} arrived at {report['label']} for {report['id']}.")
        elif unit['phase']=='PATROLLING':
            self.last_visited[unit['position']]=step
            level=unit.get('patrol_level')
            if level!='TRANSIT':
                self.patrol_visits[level or self.graph.nodes[unit['position']].risk_level] += 1
                self.patrol_destination_visits[unit['position']] += 1
            # Periodic patrols return to their post between visits. Parking at
            # the medium sector forever would keep resetting its visit timer.
            if level in ('MEDIUM','LOW','NONE') and unit.get('patrol_zone') is None and unit['position']!=unit['home']:
                path=self.router.astar(unit['position'],unit['home'])
                if path:
                    unit.update(status='PATROLLING',phase='PATROLLING',target=unit['home'],path=path,patrol_level='TRANSIT')
                    return
            unit.update(status='AVAILABLE',phase=None,target=None,path=[])
        elif unit['phase']=='RETURNING':
            unit.update(status='AVAILABLE',phase=None,target=None,path=[])

    def _replan(self):
        for unit in self.units:
            if unit['phase'] not in ('RESPONDING','PATROLLING','RETURNING'):
                continue
            path=self.router.astar(unit['position'],unit['target'])
            if path is None:
                if unit['phase']=='RESPONDING':
                    report=self._report(unit['report_id'])
                    report.update(police_status='QUEUED',unit_id=None,reason='Assigned route lost road access')
                self._return(unit)
            else:
                if unit['path'] and unit['path']!=path:
                    self.reroutes += 1
                unit.update(path=path,status=unit['phase'])

    def _dispatch(self, step):
        pending=[r for r in self.reports if r['police_status'] in ('QUEUED','UNREACHABLE')]
        pending.sort(key=lambda r: (-(r['severity']+(step-r['created_step'])/SimConfig.POLICE_QUEUE_AGING_STEPS),r['created_step'],r['id']))
        for report in pending:
            candidates=[]
            for unit in self.units:
                if not self._can_dispatch(unit):
                    continue
                path=self.router.astar(unit['position'],report['node_id'])
                if path is not None:
                    cost=sum(self.graph.get_edge_cost(a,b,'normal') for a,b in zip(path,path[1:]))
                    candidates.append((cost,unit['id'],unit,path))
            if not candidates:
                # Distinguish occupied resources from a genuine road-access failure.
                reachable = report['node_id'] in self.covered_nodes() or any(
                    self.router.astar(u['position'],report['node_id']) is not None for u in self.units)
                report.update(police_status='QUEUED' if reachable else 'UNREACHABLE',
                              reason='All reachable cars are busy' if reachable else 'No permitted police route; full blocks and gates are excluded')
                continue
            cost,_,unit,path=min(candidates,key=lambda c:c[:2])
            report.update(police_status='RESPONDING',unit_id=unit['id'],dispatch_cost=round(cost,6),reason='Police dispatched')
            unit.update(status='RESPONDING',phase='RESPONDING',target=report['node_id'],path=path,report_id=report['id'])
            self.log(f"{report['id']}: {unit['id']} dispatched to {report['label']} by normal-access road cost {cost:.2f}.")
            if len(path)==1:
                self._arrive(unit,step)

    def _medical(self, report, step):
        if not report['medical_required']:
            return
        if self.fleet is None:
            report['medical_status']='UNAVAILABLE'
            return
        if self.network:
            self.network.refresh()
        emergency=next((e for e in self.fleet.emergencies if e['id']==report['medical_emergency_id']),None)
        if emergency is None:
            emergency=next((e for e in self.fleet.emergencies if e['node_id']==report['node_id'] and e['status'] not in ('RESOLVED','ABORTED')),None)
        if (emergency and emergency['status']=='RESPONDING' and self.network
                and report['node_id'] not in self.network.reachable):
            # An existing road response must not hide the helicopter action
            # indefinitely after the patient loses all medical road access.
            self.fleet.release_blocked_response(emergency,step)
        if emergency and emergency['status']!='ABORTED':
            unit = next((u for u in self.fleet.units if u['emergency_id']==emergency['id']), None)
            medical_status = 'OUT_OF_SERVICE' if unit and unit['status']=='OUT_OF_SERVICE' else emergency['status']
            report.update(medical_emergency_id=emergency['id'],medical_status=medical_status)
            return
        if self.network:
            if report['node_id'] not in self.fleet.road_reachable():
                report.update(medical_emergency_id=None,medical_status='HELICOPTER_REQUIRED')
                return
        try:
            emergency=self.fleet.dispatch(report['node_id'],step)
            report.update(medical_emergency_id=emergency['id'],medical_status=emergency['status'])
        except ValueError:
            report.update(medical_emergency_id=None,medical_status='QUEUED')

    def _statuses(self, step):
        for report in self.reports:
            if report['status']=='RESOLVED':
                continue
            self._medical(report,step)
            if report['police_status']=='COMPLETE':
                report['status']='RESOLVED' if report['medical_status'] in ('NONE','RESOLVED') else 'WAITING_MEDICAL'
                if report['status']=='RESOLVED':
                    report['resolved_step']=step
            else:
                report['status']=report['police_status']

    def medical_rescue(self, report_id, step):
        report=self._report(report_id)
        if not report['medical_required'] or report['medical_status']!='HELICOPTER_REQUIRED' or self.air is None:
            raise ValueError('This report does not currently require helicopter rescue')
        emergency=self.air.dispatch(report['node_id'],step)
        report.update(medical_emergency_id=emergency['id'],medical_status=emergency['status'])
        return emergency

    def refresh(self, step):
        self._update_crime(step)
        self._park_patrols()
        self._replan()
        self._dispatch(step)
        self._statuses(step)

    def _update_crime(self,step):
        if self.dynamic_crime:
            from core.crime_heatmap import update_crime_heatmap
            update_crime_heatmap(self.graph,self.reports,step)

    def _uniform_patrol(self, step):
        if not self.patrol_enabled:
            return
        claimed={u['target'] for u in self.units if u['target'] is not None}
        for unit in self.units:
            if unit['status']!='AVAILABLE' or unit['reserve']:
                continue
            distances=self.graph.dijkstra(unit['position'],'normal')
            choices=[n for n,d in distances.items() if n!=unit['position'] and n not in claimed and math.isfinite(d)]
            if not choices:
                continue
            def priority(n):
                risk=SimConfig.POLICE_RISK_WEIGHTS.get(self.graph.nodes[n].risk_level,1) if self.strategy=='risk_weighted' else 1
                age=(step-self.last_visited.get(n,0))/SimConfig.POLICE_PATROL_AGING_STEPS
                return (risk+min(3,self.report_counts[n]))/(1+distances[n])+age
            target=max(choices,key=lambda n:(priority(n),-n))
            path=self.router.astar(unit['position'],target)
            unit.update(status='PATROLLING',phase='PATROLLING',target=target,path=path)
            claimed.add(target)

    def _hotspots(self):
        """Group neighboring HIGH sectors into geographic patrol areas."""
        high = {n.id for n in self.graph.nodes.values() if n.risk_level=='HIGH'}
        by_point = {(n.row,n.col):n.id for n in self.graph.nodes.values() if n.id in high}
        zones=[]
        while high:
            root=min(high)
            high.remove(root)
            nodes, pending = {root}, [root]
            while pending:
                node=self.graph.nodes[pending.pop()]
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        neighbor=by_point.get((node.row+dr,node.col+dc))
                        if neighbor in high:
                            high.remove(neighbor)
                            nodes.add(neighbor)
                            pending.append(neighbor)
            zones.append({'id':f'HOT-{root:03d}','nodes':sorted(nodes)})
        return sorted(zones,key=lambda z:(-len(z['nodes']),z['id']))

    def _patrol(self, step):
        if not self.patrol_enabled:
            return
        if self.strategy!='risk_weighted':
            return self._uniform_patrol(step)
        pool=[u for u in self.units if not u['reserve'] and u['report_id'] is None
              and u['phase'] in (None,'PATROLLING') and u['status'] in ('AVAILABLE','PATROLLING')]
        maps={u['id']:self.graph.dijkstra(u['position'],'normal') for u in pool}
        zones=self._hotspots()
        assignments={}
        available=list(pool)
        # Reserve some routine capacity for periodic medium/low visits. Station
        # response reserves remain untouched and all real reports take priority.
        quota=min(len(pool),max(len(zones),math.ceil(len(pool)*SimConfig.POLICE_HIGH_PATROL_SHARE))) if zones else 0
        if any(n.risk_level!='HIGH' for n in self.graph.nodes.values()) and len(pool)>1:
            quota=min(quota,len(pool)-1)

        def assign(zone):
            if sum(z['id']==zone['id'] for z in assignments.values()) >= max(1,math.ceil(len(zone['nodes'])/3)):
                return False
            choices=[]
            for unit in available:
                distance=min(maps[unit['id']][n] for n in zone['nodes'])
                if math.isfinite(distance):
                    choices.append((unit.get('patrol_zone')!=zone['id'],distance,unit['id'],unit))
            if not choices:
                return False
            unit=min(choices,key=lambda c:c[:3])[3]
            available.remove(unit)
            assignments[unit['id']]=zone
            return True

        for zone in zones:
            if len(assignments)<quota:
                assign(zone)
        while len(assignments)<quota and available:
            counts=Counter(z['id'] for z in assignments.values())
            ordered=sorted(zones,key=lambda z:(-len(z['nodes'])/(counts[z['id']]+1),z['id']))
            if not any(assign(z) for z in ordered):
                break

        claimed=set()
        for unit in pool:
            zone=assignments.get(unit['id'])
            if zone is None:
                if unit.get('patrol_zone') and unit['phase']=='PATROLLING':
                    unit.update(status='AVAILABLE',phase=None,target=None,path=[])
                unit['patrol_zone']=None
                continue
            unit['patrol_zone']=zone['id']
            unit['patrol_level']='HIGH'
            if unit['phase']=='PATROLLING' and unit['target'] in zone['nodes']:
                claimed.add(unit['target'])
                continue
            choices=[n for n in zone['nodes'] if n!=unit['position'] and n not in claimed and math.isfinite(maps[unit['id']][n])]
            if not choices:
                # A single-sector hotspot gets a short outward-and-back circuit.
                choices=([n for n in self.graph.get_neighbors(unit['position'],'normal') if n not in claimed]
                         if unit['position'] in zone['nodes'] else
                         [n for n in zone['nodes'] if math.isfinite(maps[unit['id']][n])])
            target=max(choices,key=lambda n:((step-self.last_visited.get(n,-SimConfig.POLICE_PATROL_AGING_STEPS))/(1+maps[unit['id']][n]),-n)) if choices else unit['position']
            unit.update(status='PATROLLING',phase='PATROLLING',target=target,path=self.router.astar(unit['position'],target))
            claimed.add(target)

        claimed.update(u['target'] for u in pool if u['phase']=='PATROLLING' and u['id'] not in assignments)
        for unit in available:
            if unit['status']!='AVAILABLE':
                continue
            choices=[]
            for n,cost in maps[unit['id']].items():
                level=self.graph.nodes[n].risk_level
                if n==unit['position'] or n in claimed or level=='HIGH' or not math.isfinite(cost):
                    continue
                interval=SimConfig.POLICE_PATROL_INTERVALS.get(level,24)
                elapsed=step-self.last_visited.get(n,step-interval)
                if elapsed>=interval:
                    choices.append((elapsed/interval+SimConfig.POLICE_RISK_WEIGHTS.get(level,1)/(1+cost),-cost,-n,n))
            if choices:
                target=max(choices)[3]
                unit.update(status='PATROLLING',phase='PATROLLING',target=target,path=self.router.astar(unit['position'],target),
                            patrol_level=self.graph.nodes[target].risk_level,patrol_zone=None)
                claimed.add(target)
            elif unit['position']!=unit['home']:
                path=self.router.astar(unit['position'],unit['home'])
                if path:
                    unit.update(status='PATROLLING',phase='PATROLLING',target=unit['home'],path=path,patrol_level='TRANSIT')

    def patrol_coverage(self):
        zones=[]
        for zone in self._hotspots():
            assigned=[u for u in self.units if u.get('patrol_zone')==zone['id'] and u['phase']=='PATROLLING'
                      and u['status']=='PATROLLING' and self.patrol_enabled]
            zones.append({**zone,'labels':[self.graph.nodes[n].label for n in zone['nodes']],
                          'assigned_units':[u['id'] for u in assigned],
                          'present_units':[u['id'] for u in assigned if u['position'] in zone['nodes']]})
        return zones

    def _generate(self, step):
        if not self.automatic_incidents or self.rng.random()>=self.auto_probability:
            return
        occupied={r['node_id'] for r in self.reports if r['status']!='RESOLVED'}
        choices=[n.id for n in self.graph.nodes.values() if n.node_type in (SimConfig.RESIDENTIAL,SimConfig.BANK,SimConfig.INDUSTRIAL) and n.id not in occupied]
        if not choices:
            return
        weights=[SimConfig.POLICE_RISK_WEIGHTS.get(self.graph.nodes[n].risk_level,1) for n in choices]
        node=self.rng.choices(choices,weights=weights,k=1)[0]
        try:
            self.report(node,self.rng.choices(INCIDENT_TYPES,weights=[6,2,1,1],k=1)[0],self.rng.randint(1,3),step,source='AUTOMATIC')
        except ValueError:
            pass  # Bounded histories stop generation without dropping existing reports.

    def advance(self, step):
        self._update_crime(step)
        self._park_patrols()
        self._generate(step)
        self._replan()
        for unit in self.units:
            if unit['phase']=='ON_SCENE':
                if step>=unit['service_until']:
                    report=self._report(unit['report_id'])
                    report.update(police_status='COMPLETE',police_completed_step=step,reason='Police task completed')
                    self.log(f"{report['id']}: police task completed; medical task is tracked separately.")
                    self._return(unit)
                continue
            if unit['phase'] and unit['path']:
                if len(unit['path'])>1:
                    a,b=unit['path'][:2]
                    self.distance_travelled+=self.graph.get_edge_cost(a,b,'normal')
                    unit['position']=b
                    unit['path']=unit['path'][1:]
                if unit['position']==unit['target']:
                    self._arrive(unit,step)
        # Presence counts at intermediate nodes, on scene and at parked posts,
        # not only when a car reaches a planned patrol destination.
        for unit in self.units:
            self.last_visited[unit['position']]=step
        self._dispatch(step)
        self._statuses(step)
        self._update_crime(step)
        self._patrol(step)
        self.metrics_history.append({'step':step,**self.summary(step)})
        self.metrics_history=self.metrics_history[-200:]

    def covered_nodes(self):
        key=(tuple(s['node_id'] for s in self.stations),tuple((k,e.blocked,e.temporarily_blocked,e.cost) for k,e in self.graph.edges.items()),
             tuple(n.risk_level for n in self.graph.nodes.values()))
        if key!=self._coverage_key:
            self._station_distances={s['node_id']:self.graph.dijkstra(s['node_id'],'normal') for s in self.stations}
            self._covered={n for distances in self._station_distances.values() for n,d in distances.items() if math.isfinite(d)}
            self._coverage_key=key
        return self._covered

    def bank_protection(self):
        self.covered_nodes()
        result=[]
        for bank in self.graph.get_nodes_of_type(SimConfig.BANK):
            choices=[]
            for station in self.stations:
                node=self.graph.nodes[station['node_id']]
                blocks=abs(node.row-bank.row)+abs(node.col-bank.col)
                cost=self._station_distances[node.id][bank.id]
                direction=getattr(self.graph,'bank_directions',{}).get(bank.id)
                if (SimConfig.POLICE_BANK_MIN_BLOCKS<=blocks<=SimConfig.POLICE_BANK_MAX_BLOCKS and math.isfinite(cost)
                        and (direction is None or in_direction(bank,node,direction))):
                    choices.append((blocks,cost,station['id'],station))
            best=min(choices,key=lambda c:c[:3]) if choices else None
            result.append({'node_id':bank.id,'label':bank.label,'protected':best is not None,
                           'police_direction':getattr(self.graph,'bank_directions',{}).get(bank.id),
                           'station_id':best[3]['id'] if best else None,
                           'station_label':best[3]['label'] if best else None,
                           'grid_blocks':best[0] if best else None})
        return result

    def summary(self, step):
        statuses=Counter(r['status'] for r in self.reports)
        return {'reported':len(self.reports),'resolved':statuses['RESOLVED'],
                'police_handled':sum(r['police_status']=='COMPLETE' for r in self.reports),
                'unresolved':len(self.reports)-statuses['RESOLVED'],
                'queued':sum(r['police_status']=='QUEUED' for r in self.reports),
                'unreachable':sum(r['police_status']=='UNREACHABLE' for r in self.reports),
                'medical_pending':sum(r['medical_required'] and r['medical_status']!='RESOLVED' for r in self.reports),
                'available':sum(self._can_dispatch(u) for u in self.units),
                'patrolling':sum(u['status']=='PATROLLING' for u in self.units),
                'on_scene':sum(u['status']=='ON_SCENE' for u in self.units),
                'responding':sum(u['status']=='RESPONDING' for u in self.units),
                'total_units':len(self.units),'station_count':len(self.stations),
                'coverage_pct':round(100*len(self.covered_nodes())/max(1,len(self.graph.nodes)),1),
                'mean_response_steps':round(sum(self.response_times)/len(self.response_times),2) if self.response_times else None,
                'worst_response_steps':max(self.response_times,default=None),
                'arrivals_measured':len(self.response_times),'reroutes':self.reroutes,
                'travel_cost':round(self.distance_travelled,3),
                'oldest_wait_steps':max((step-r['created_step'] for r in self.reports if r['police_status'] in ('QUEUED','UNREACHABLE')),default=0),
                'response_in_progress':any(u['status'] in ('RESPONDING','ON_SCENE','RETURNING') for u in self.units)}

    def plan_stations(self):
        planner=PoliceStationPlanner(self.graph,len(self.stations),self.seed,self.strategy,self.report_counts)
        sites=planner.run()
        new_sites=[n for n in sites if n not in {s['node_id'] for s in self.stations}]
        # Additional stations for components cut off from the existing station network.
        remaining=set(self.graph.nodes)-self.covered_nodes()
        additions=[]
        unbuildable=[]
        unbuildable_components=0
        while remaining:
            root=min(remaining)
            component={n for n,d in self.graph.dijkstra(root,'normal').items() if math.isfinite(d)} & remaining
            candidates=[n for n in component if self.graph.nodes[n].node_type!=SimConfig.BANK]
            if not candidates:
                unbuildable.extend(sorted(component))
                unbuildable_components+=1
                remaining-=component
                continue
            best=candidates[0] if len(component)<=1 else None
            if best is None:
                maps={n:self.graph.dijkstra(n,'normal') for n in component}
                best=min(candidates,key=lambda n:(sum(maps[n][v]*planner.weights[v] for v in component),n))
            additions.append({'node_id':best,'label':self.graph.nodes[best].label,'gain':len(component)})
            remaining-=component
        additions.sort(key=lambda x:(-x['gain'],x['node_id']))
        choices=additions+[{'node_id':n,'label':self.graph.nodes[n].label,'gain':0} for n in new_sites if n not in {a['node_id'] for a in additions}]
        self.plan={'sites':sites,'labels':[self.graph.nodes[n].label for n in sites],
                   'additions':choices,'unserved_components':len(additions)+unbuildable_components,
                   'restore_road_nodes':unbuildable,
                   'fitness':round(planner.best_fitness,6),'feasible':not planner.is_infeasible,
                   'policy':'Cover banks within three grid blocks with open road access, then maximise city reach and minimise response cost; prefer two-block bank sites',
                   'basis':self._plan_basis()}
        return self.plan

    def _plan_basis(self):
        return (tuple((e.node_a,e.node_b,e.blocked,e.temporarily_blocked,e.cost) for e in self.graph.edges.values()),
                tuple((n.id,n.risk_level) for n in self.graph.nodes.values()),tuple(sorted(self.report_counts.items())),tuple(s['node_id'] for s in self.stations))

    def to_dict(self, step):
        from core.crime_heatmap import incident_areas
        plan={k:v for k,v in self.plan.items() if k!='basis'} if self.plan else None
        if plan:
            plan['stale']=self.plan['basis']!=self._plan_basis()
        per_node={n:{'risk':self.graph.nodes[n].risk_level,'reported':self.report_counts[n],
                     'routine_patrol_arrivals':self.patrol_destination_visits[n],
                     'last_police_visit_step':self.last_visited.get(n),
                     'unresolved':sum(r['node_id']==n and r['status']!='RESOLVED' for r in self.reports)}
                  for n in self.graph.nodes}
        return {'crime_areas':incident_areas(self.graph,self.reports,step),
                'patrol_policy':{'revisit_steps':dict(SimConfig.POLICE_PATROL_INTERVALS),
                    'high_coverage':'Dedicated moving circuits; incident responses take priority',
                    'visits_by_level':dict(self.patrol_visits),'hotspots':self.patrol_coverage()},
                'crime_report_radius':SimConfig.CRIME_REPORT_RADIUS,
                'banks':self.bank_protection(),'bank_max_blocks':SimConfig.POLICE_BANK_MAX_BLOCKS,
                'stations':self.stations,'units':[{**u,'position_label':self.graph.nodes[u['position']].label,
                    'target_label':self.graph.nodes[u['target']].label if u['target'] is not None else None,
                    'dispatch_available':self._can_dispatch(u)} for u in self.units],
                'reports':self.reports,'summary':self.summary(step),'node_statistics':per_node,
                'unserved_nodes':sorted(set(self.graph.nodes)-self.covered_nodes()),'recommendations':plan,
                'settings':{'patrol_enabled':self.patrol_enabled,'automatic_incidents':self.automatic_incidents,'auto_probability':self.auto_probability},
                'incident_types':list(INCIDENT_TYPES),'severity_levels':[1,2,3],
                'metrics_history':self.metrics_history,'risk_model':('Crime opportunity scenario plus incident areas; dense residential areas stay low outside reported crime footprints.' if self.dynamic_crime
                    else 'Frozen synthetic crime scores for comparison; observed reports are tracked separately.')}


def compare_strategies(graph, seed=42, steps=80, incident_count=12, station_count=None, unit_count=None):
    """Matched synthetic workload, frozen roads/risk and no mutations to the live city."""
    rng=random.Random(seed)
    nodes=[n.id for n in graph.nodes.values() if n.node_type==SimConfig.RESIDENTIAL] or sorted(graph.nodes)
    nodes=rng.sample(nodes,min(incident_count,len(nodes)))
    schedule=[{'step':rng.randrange(max(1,steps//2)),'node_id':n,'severity':rng.randint(1,3),
               'kind':rng.choice(INCIDENT_TYPES[:3])} for n in nodes]
    schedule.sort(key=lambda x:(x['step'],x['node_id']))
    class SilentEvents:
        def log(self,*args,**kwargs):
            pass
    results=[]
    for strategy in ('uniform','risk_weighted'):
        frozen=type(graph).from_dict(graph.to_dict())
        service=PoliceService(frozen,SilentEvents(),seed=seed,strategy=strategy,station_count=station_count,unit_count=unit_count)
        for step in range(steps):
            for incident in schedule:
                if incident['step']==step:
                    service.report(incident['node_id'],incident['kind'],incident['severity'],step)
            service.advance(step+1)
        results.append({'strategy':strategy,'stations':[s['label'] for s in service.stations],**service.summary(steps)})
    return {'seed':seed,'steps':steps,'incident_count':len(schedule),'schedule':schedule,'results':results,
            'note':'Identical synthetic reports, normal-road restrictions and vehicle counts. Mean response measures arrivals only; compare unresolved reports too.'}
