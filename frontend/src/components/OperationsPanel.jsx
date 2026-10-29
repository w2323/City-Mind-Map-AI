import {useState} from 'react';
import './operations.css';

export default function OperationsPanel({state, selectedNode, onSelectNode, onDispatch, onHelicopter, onCenter, onPlay, playing, onTogglePlaying, onStep, busy, onClose}) {
  const [label, setLabel] = useState('');
  const [landings, setLandings] = useState(null);
  const nodes = state.graph.nodes;
  const targetLabel = label || nodes.find(n=>n.id===selectedNode)?.label || '';
  const target = nodes.find(n=>n.label===targetLabel.trim().toUpperCase());
  const air = state.air_rescue || {};
  const network = state.medical_network || {};
  const summary = state.dispatch_summary || {};
  const emergencies = state.emergencies || [];
  const requiresAir = target && !(summary.reachable_nodes || []).includes(target.id);
  const duplicate = emergencies.some(e=>e.node_id===target?.id && !['RESOLVED','ABORTED'].includes(e.status));
  async function respond(action) { if(await action()) onPlay(); }
  return <section className="operations-panel" aria-label="Medical operations">
    <header><h2>Medical operations</h2><button aria-label="Close medical operations" onClick={onClose}>×</button></header>
    <p>{summary.available || 0}/{summary.total || 0} available · {summary.active || 0} active · {summary.resolved || 0} resolved</p>
    <button disabled={state.is_complete} onClick={onTogglePlaying}>{playing?'Pause response playback':'Play response playback'}</button>
    <button disabled={busy || state.is_complete} onClick={onStep}>Advance one step</button>
    <form onSubmit={e=>{e.preventDefault();respond(()=>onDispatch(targetLabel));}}>
      <label>Emergency sector<input aria-label="Emergency sector" value={targetLabel} placeholder="C4" onChange={e=>setLabel(e.target.value.toUpperCase())} /></label>
      <button type="button" disabled={selectedNode==null} onClick={()=>setLabel(nodes.find(n=>n.id===selectedNode)?.label || '')}>Use selected sector</button>
      <button disabled={busy || state.is_complete || !target || requiresAir || duplicate}>Dispatch ambulance</button>
      <button type="button" disabled={busy || state.is_complete || !requiresAir || duplicate || air.status!=='READY'} onClick={()=>respond(()=>onHelicopter('dispatch',{node:targetLabel}))}>Helicopter rescue</button>
      <p>{requiresAir?'No medical road access. Request helicopter rescue.':'Select a sector on the map or enter its label.'}</p>
    </form>
    <h3>Helicopter</h3><p>{air.status} · Fuel {air.fuel_pct}%</p>
    <button disabled={busy || air.landed_node==null || air.fuel_pct>=100} onClick={()=>onHelicopter('refuel')}>Refuel</button>
    <button disabled={busy || !air.relocation?.can_relocate} onClick={()=>respond(()=>onHelicopter('relocate'))}>Relocate to safe pad</button>
    <label>Landing sectors (comma separated)<input aria-label="Landing sectors" value={landings ?? (air.custom_landings || []).map(id=>nodes.find(n=>n.id===id)?.label).filter(Boolean).join(', ')} placeholder="A1, H8" onChange={e=>setLandings(e.target.value.toUpperCase())} /></label>
    <button disabled={busy || !landings?.trim()} onClick={()=>onHelicopter('landings',{nodes:landings.split(',').map(s=>s.trim()).filter(Boolean)})}>Apply landing sites</button>
    <p>Building pads: {(air.landing_sites || []).map(s=>`${s.label}${s.available?'':' (unavailable)'}`).join(', ')}. Hospitals are delivery stops.</p>
    <h3>Coverage and placement</h3>
    <p>{network.coverage_pct || 0}% medical road coverage · {network.unreachable_nodes?.length || 0} unserved sectors</p>
    {(network.recommendations || []).map(r=><div key={r.node_id}><button onClick={()=>onSelectNode(r.node_id)}>Inspect {r.label}</button> +{r.gain} sectors <button disabled={busy} onClick={()=>onCenter(r.label)}>Open medical center at {r.label}</button></div>)}
    {!network.recommendations?.length && <p>No additional medical center recommended.</p>}
    {(network.notifications || []).slice(-5).reverse().map(n=><p key={n.id}>{n.message}</p>)}
    <h3>Live fleet</h3>
    {(state.fleet || []).map(u=><p key={u.id}><button onClick={()=>onSelectNode(u.position)}>{u.id} · {u.position_label}</button> {u.status} · {u.emergency_id || 'No assigned call'}</p>)}
    <h3>Emergency queue</h3>
    {[...emergencies].reverse().map(e=><p key={e.id}><button onClick={()=>onSelectNode(e.node_id)}>{e.id} · {nodes.find(n=>n.id===e.node_id)?.label}</button> {e.status} · {e.ambulance_id || 'Awaiting unit'} {e.reason}</p>)}
  </section>;
}
