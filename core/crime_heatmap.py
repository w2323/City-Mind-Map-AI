"""Explicit crime-opportunity scenario; scores are not real crime probabilities."""
import math
from config.simulation_config import SimConfig
from core.bank_placement import grid_distance


def incident_areas(graph,reports=(),step=0):
    """Authoritative footprints shared by scoring and both map renderers."""
    areas=[]
    for report in reports:
        center=graph.nodes.get(report['node_id'])
        if center is None:
            continue
        peak=85+5*report['severity']
        if report['status']=='RESOLVED':
            resolved=report.get('resolved_step')
            age=max(0,step-(resolved if resolved is not None else report['created_step']))
            peak*=2**(-age/SimConfig.CRIME_REPORT_HALF_LIFE_STEPS)
        if peak<=SimConfig.CRIME_BASE_SCORE:
            continue  # Its individual contribution has faded to background.
        areas.append({'report_id':report.get('id',f"node-{center.id}"),'node_id':center.id,'label':center.label,
                      'radius':SimConfig.CRIME_REPORT_RADIUS,'peak_score':peak,
                      'status':report['status'],'severity':report['severity']})
    return areas


def update_crime_heatmap(graph,reports=(),step=0):
    banks=graph.get_nodes_of_type(SimConfig.BANK)
    industrial=graph.get_nodes_of_type(SimConfig.INDUSTRIAL)
    residential=graph.get_nodes_of_type(SimConfig.RESIDENTIAL)
    areas=incident_areas(graph,reports,step)
    # Batch observer notifications as in the original model pipeline.
    routers={getattr(callback,'__self__',None) for callback in graph._risk_observers}
    routers=[r for r in routers if hasattr(r,'begin_batch_block')]
    for router in routers:
        router.begin_batch_block()
    try:
        for node in graph.nodes.values():
            nearby=sum(abs(n.row-node.row)<=1 and abs(n.col-node.col)<=1 for n in residential)
            dense=node.node_type==SimConfig.RESIDENTIAL and nearby>=SimConfig.CRIME_DENSE_RESIDENTIAL_COUNT
            bank_distance=min((grid_distance(node,b) for b in banks),default=999)
            industrial_distance=min((grid_distance(node,i) for i in industrial),default=999)
            residential_distance=min((grid_distance(node,r) for r in residential),default=999)
            score=SimConfig.CRIME_BASE_SCORE
            reasons=['Low background opportunity']
            if dense:
                reasons=['Dense residential area: low baseline under the configured scenario']
            elif bank_distance<=SimConfig.CRIME_BANK_RADIUS:
                score=SimConfig.CRIME_BANK_SCORE-10*bank_distance
                reasons=['Valuable bank asset' if bank_distance==0 else 'Near a valuable bank asset']
            elif industrial_distance<=2 and residential_distance<=2 and nearby<SimConfig.CRIME_DENSE_RESIDENTIAL_COUNT:
                score=SimConfig.CRIME_INTERFACE_SCORE-(industrial_distance-1)*10
                reasons=['Open industrial/residential interface']
            signal=0.
            nearby_reports=[]
            for area in areas:
                center=graph.nodes[area['node_id']]
                distance=math.hypot(node.row-center.row,node.col-center.col)
                if distance<=area['radius']:
                    # Smooth falloff: the outer boundary still receives a
                    # meaningful signal, while nodes outside receive none.
                    signal+=area['peak_score']*(1-distance/(area['radius']+2))
                    nearby_reports.append((distance,area))
            if signal:
                score=max(score,min(100,signal))
                if any(distance==0 and area['status']!='RESOLVED' for distance,area in nearby_reports):
                    reasons.append('Active crime report')
                if any(distance>0 for distance,area in nearby_reports):
                    nearest=min(nearby_reports,key=lambda item:item[0])
                    reasons.append(f"Within the {nearest[1]['radius']:g}-cell crime area around {nearest[1]['label']}")
                if any(area['status']=='RESOLVED' for distance,area in nearby_reports):
                    reasons.append('Recent reported crime; area influence fades with time')
            score=round(min(100,max(0,score)),2)
            level='HIGH' if score>=SimConfig.CRIME_HIGH_THRESHOLD else 'MEDIUM' if score>=SimConfig.CRIME_MEDIUM_THRESHOLD else 'LOW'
            node.crime_score,node.crime_reasons=score,reasons
            node.risk_features={'population_density':round(node.population/200,6),'nearby_residential_nodes':nearby,
                                'dense_residential':int(dense),'bank_proximity':round(1/(1+bank_distance),4) if banks else 0,
                                'industrial_interface':int(industrial_distance<=2 and residential_distance<=2 and not dense),
                                'reported_incident_signal':round(min(100,signal),2),
                                'nearby_report_count':len(nearby_reports),
                                'report_influence_radius':SimConfig.CRIME_REPORT_RADIUS}
            node.cluster_id=None
            graph.update_risk(node.id,level,score/100)
    finally:
        for router in routers:
            router.end_batch_block()
