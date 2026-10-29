"""Seeded background incidents that drive the real dispatch and road systems."""
import math
import random
from config.simulation_config import SimConfig
from challenges.challenge2 import find_bridges


class CityEvents:
    def __init__(self, simulation, enabled=True):
        self.sim=simulation
        # Separate stream: enabling events never changes initial city/GA placement.
        self.rng=random.Random(f'city-events:{simulation._seed}' if simulation._seed is not None else None)
        self.medical_enabled=self.roads_enabled=bool(enabled)
        self.medical_probability=SimConfig.AUTO_MEDICAL_PROBABILITY
        self.road_probability=SimConfig.AUTO_ROAD_PROBABILITY
        self.sim.state.police.automatic_incidents=bool(enabled)
        self.history=[]
        self.road_leases={}
        self.generated_medical=self.generated_roads=0
        self.generated_crimes=0

    @property
    def enabled(self):
        return self.medical_enabled or self.roads_enabled or self.sim.state.police.automatic_incidents

    def configure(self, enabled=None, medical_enabled=None, roads_enabled=None, crime_enabled=None,
                  medical_probability=None, road_probability=None, crime_probability=None):
        for value in (medical_probability,road_probability,crime_probability):
            if value is not None and (not math.isfinite(value) or not 0<=value<=1):
                raise ValueError('Event probabilities must be between zero and one')
        for value in (enabled,medical_enabled,roads_enabled,crime_enabled):
            if value is not None and type(value) is not bool:
                raise ValueError('Event switches must be boolean')
        if enabled is not None:
            self.medical_enabled=self.roads_enabled=enabled
            self.sim.state.police.automatic_incidents=enabled
        if medical_enabled is not None:
            self.medical_enabled=medical_enabled
        if roads_enabled is not None:
            self.roads_enabled=roads_enabled
        if crime_enabled is not None:
            self.sim.state.police.automatic_incidents=crime_enabled
        if medical_probability is not None:
            self.medical_probability=medical_probability
        if road_probability is not None:
            self.road_probability=road_probability
        if crime_probability is not None:
            self.sim.state.police.auto_probability=crime_probability

    def record(self, kind, step, **data):
        if kind=='CRIME':
            self.generated_crimes+=1
        self.history.append({'kind':kind,'step':step,'source':'AUTOMATIC',**data})
        self.history=self.history[-200:]

    def release_road(self, key):
        """A manual action takes ownership, including a block that's already set."""
        self.road_leases.pop(key,None)

    def advance(self, step):
        # Previously created closures expire even after automatic events are OFF.
        for key,lease in list(self.road_leases.items()):
            if step>=lease['expires_step']:
                self.road_leases.pop(key,None)
                result=self.sim.unblock_road_manually(*key,source='AUTOMATIC')
                if result['changed']:
                    self.record('ROAD_REOPENED',step,road=list(key))
        if self.roads_enabled and self.rng.random()<self.road_probability:
            self._road(step)
        if self.medical_enabled and self.rng.random()<self.medical_probability:
            self._medical(step)

    def _road(self, step):
        if len(self.road_leases)>=SimConfig.AUTO_ROAD_MAX_CLOSURES:
            return
        bridges={tuple(sorted(edge)) for edge in find_bridges(self.sim.graph)}
        candidates=[key for key,e in self.sim.graph.edges.items()
                    if not e.blocked and not e.temporarily_blocked and key not in bridges]
        if not candidates:
            return
        key=self.rng.choice(candidates)
        if self.sim.block_road_manually(*key,source='AUTOMATIC')['changed']:
            expires=step+self.rng.randint(*SimConfig.AUTO_ROAD_DURATION_STEPS)
            self.road_leases[key]={'expires_step':expires,'created_step':step}
            self.generated_roads+=1
            self.record('ROAD_BLOCKED',step,road=list(key),expires_step=expires)

    def _medical(self, step):
        fleet=self.sim.state.fleet
        pending=[e for e in fleet.emergencies if e['status'] not in ('RESOLVED','ABORTED')]
        if len(pending)>=SimConfig.AUTO_MEDICAL_MAX_PENDING:
            return
        occupied={e['node_id'] for e in pending}
        reachable=fleet.road_reachable()
        choices=[n.id for n in self.sim.graph.nodes.values() if n.id in reachable and n.id not in occupied
                 and n.node_type in (SimConfig.RESIDENTIAL,SimConfig.BANK,SimConfig.SCHOOL,SimConfig.INDUSTRIAL)]
        if not choices:
            return
        target=self.rng.choice(choices)
        try:
            emergency=fleet.report(target,step)
        except ValueError:
            return  # Bounded history; never discard an existing patient.
        self.generated_medical+=1
        self.record('MEDICAL',step,node_id=target,label=self.sim.graph.nodes[target].label,emergency_id=emergency['id'])

    def to_dict(self):
        return {'enabled':self.enabled,'settings':{'medical_enabled':self.medical_enabled,'roads_enabled':self.roads_enabled,
                'crime_enabled':self.sim.state.police.automatic_incidents,'medical_probability':self.medical_probability,
                'road_probability':self.road_probability,'crime_probability':self.sim.state.police.auto_probability},
                'generated_medical':self.generated_medical,'generated_road_closures':self.generated_roads,
                'generated_crimes':self.generated_crimes,
                'active_road_closures':[{'road':list(key),**lease} for key,lease in sorted(self.road_leases.items())],
                'road_duration_steps':list(SimConfig.AUTO_ROAD_DURATION_STEPS),
                'max_road_closures':SimConfig.AUTO_ROAD_MAX_CLOSURES,'history':list(self.history)}
