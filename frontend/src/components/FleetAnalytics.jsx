import {useState} from 'react';
import {referenceRoute} from '../engine/referenceRoute';
export default function FleetAnalytics({state,targetLabel,onSelect}) {
  const [report,setReport]=useState(null);
  function validate() {
    const target=state.graph.nodes.find(n=>n.label===targetLabel.trim().toUpperCase());
    setReport({revision:state.revision,rows:state.fleet.map(unit=>{
      const valid=unit.path.slice(1).every((b,i)=>state.graph.edges.some(e=>!e.blocked&&((e.node_a===unit.path[i]&&e.node_b===b)||(e.node_b===unit.path[i]&&e.node_a===b))));
      const route=target?referenceRoute(state.graph,unit.position,target.id,'ambulance'):null;
      return {id:unit.id,valid,cost:route?.path_cost,reachable:route?.reachable};
    })});
  }
  return <section className="workspace-content" aria-label="Fleet analytics"><h3>Deployed medical fleet</h3>
    {state.fleet.map(u=><div className="info-card" key={u.id}><button onClick={()=>onSelect(u.position)}>{u.id} · {u.position_label}</button><p>{u.status} · Home {u.depot_label} · {u.emergency_id||'No assigned emergency'}</p></div>)}
    <h3>Route validation</h3><p>Check active ambulance paths against road closures. Enter a target above to compare road costs from every current unit position.</p><button onClick={validate}>Validate routes</button>
    {report&&<><p>Revision {report.revision}{report.revision!==state.revision?' · City changed; validate again.':''}</p>{report.rows.map(r=><p key={r.id}>{r.id}: {r.valid?'Path valid':'Road blocked'}{r.reachable!=null?` · ${r.reachable?`target cost ${r.cost.toFixed(3)}`:'Target unreachable'}`:''}</p>)}</>}
  </section>;
}
