"""Seeded bank relocation after medical planning, with varied police directions."""
import math
from config.simulation_config import SimConfig

DIRECTIONS={'EAST':(0,1),'WEST':(0,-1),'NORTH':(-1,0),'SOUTH':(1,0)}


def grid_distance(a,b):
    return abs(a.row-b.row)+abs(a.col-b.col)


def in_direction(bank,station,direction):
    dr,dc=DIRECTIONS[direction]
    return any((station.row-bank.row,station.col-bank.col)==(dr*d,dc*d)
               for d in range(SimConfig.POLICE_BANK_MIN_BLOCKS,SimConfig.POLICE_BANK_MAX_BLOCKS+1))


def place_banks(graph,centers,rng):
    """Reposition bank plots without changing medical sites, roads or residences."""
    old=[n for n in graph.nodes.values() if n.node_type==SimConfig.BANK]
    if not old:
        graph.bank_directions={}
        return
    hospital_nodes=[graph.nodes[n] for n in centers]
    eligible=[n for n in graph.nodes.values() if n.node_type in (SimConfig.EMPTY,SimConfig.BANK)
              and min(grid_distance(n,h) for h in hospital_nodes)>=SimConfig.BANK_HOSPITAL_MIN_BLOCKS]
    rng.shuffle(eligible)
    directions=list(DIRECTIONS)
    rng.shuffle(directions)
    station_plots=[n for n in graph.nodes.values() if n.node_type in (SimConfig.EMPTY,SimConfig.RESIDENTIAL,SimConfig.BANK)
                   and min(grid_distance(n,h) for h in hospital_nodes)>=SimConfig.POLICE_HOSPITAL_MIN_BLOCKS]
    distances={n.id:graph.dijkstra(n.id,'normal') for n in eligible}
    options={(b.id,d):[n.id for n in station_plots if in_direction(b,n,d) and math.isfinite(distances[b.id][n.id])]
             for b in eligible for d in directions}
    def choose(placed,assigned):
        if len(placed)==len(old):
            return placed,assigned
        for bank in eligible:
            sector=(bank.row>=SimConfig.GRID_ROWS//2,bank.col>=SimConfig.GRID_COLS//2)
            if any((b.row>=SimConfig.GRID_ROWS//2,b.col>=SimConfig.GRID_COLS//2)==sector for b in placed):
                continue
            if bank in placed or any(grid_distance(bank,b)<SimConfig.BANK_MIN_SEPARATION_BLOCKS for b in placed):
                continue
            for direction in directions:
                if direction in assigned.values():
                    continue
                if not options[bank.id,direction]:
                    continue
                result=choose(placed+[bank],{**assigned,bank.id:direction})
                if result:
                    return result
        return None
    selected=choose([],{})
    if selected is None:
        raise ValueError('Cannot spread banks away from fixed medical centers with distinct nearby police directions')
    banks,assigned=selected
    for node in old:
        node.node_type,node.population=SimConfig.EMPTY,0
    for node in banks:
        node.node_type,node.population=SimConfig.BANK,SimConfig.POPULATION_MAP[SimConfig.BANK]
    graph.bank_directions=assigned
