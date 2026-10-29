import {useState} from 'react';
import {referenceRoute} from '../engine/referenceRoute';
import {exportMetrics} from '../api/citymind';
import './operations.css';

export default function DiagnosticsPanel({state,connected,onRefresh,onClose,mode='diagnostics'}) {
  const [checks,setChecks]=useState(null),[filter,setFilter]=useState('ALL'),[error,setError]=useState('');
  const [visible,setVisible]=useState(80);
  function inspect() {
    const {nodes,edges}=state.graph,ids=new Set(nodes.map(n=>n.id));
    const active=(state.fleet || []).filter(u=>u.path?.length>1);
    setChecks({revision:state.revision,items:[
      ['Unique sector IDs',ids.size===nodes.length],
      ['Valid road endpoints',edges.every(e=>ids.has(e.node_a)&&ids.has(e.node_b))],
      ['Finite positive road costs',edges.every(e=>Number.isFinite(e.cost)&&e.cost>0)],
      ['Fleet positions exist',state.fleet.every(u=>ids.has(u.position)&&ids.has(u.depot))],
      ['Active ambulance routes traverse open roads',active.every(u=>u.path.slice(1).every((b,i)=>edges.some(e=>!e.blocked&&((e.node_a===u.path[i]&&e.node_b===b)||(e.node_b===u.path[i]&&e.node_a===b)))))],
      ['Source-to-self route has zero cost',referenceRoute(state.graph,nodes[0].id,nodes[0].id).path_cost===0],
    ]});
  }
  const events=state.events.events || [];
  const filtered=[...events].reverse().filter(e=>filter==='ALL'||e.type===filter);
  return <section className="operations-panel" aria-label="Diagnostics and metrics">
    <header><h2>{mode==='metrics'?'Metrics & event history':'Diagnostics and metrics'}</h2><button aria-label="Close diagnostics" onClick={onClose}>×</button></header>
    <p>{connected?'Backend connected':'Backend disconnected'} · Step {state.step} · Revision {state.revision}</p>
    {mode!=='metrics'&&<button onClick={inspect}>Run diagnostics</button>}<button onClick={onRefresh}>Refresh state</button>
    {checks && <><p>Checked revision {checks.revision}{checks.revision!==state.revision?' (city has changed; run again)':''}</p>{checks.items.map(([name,pass])=><p key={name}>{pass?'PASS':'FAIL'} · {name}</p>)}</>}
    <h3>All simulation metrics</h3>
    <table><tbody>{Object.entries(state.events.metrics || {}).map(([name,value])=><tr key={name}><td>{name.replaceAll('_',' ')}</td><td>{typeof value==='object'?JSON.stringify(value):String(value ?? '—')}</td></tr>)}</tbody></table>
    <button onClick={()=>exportMetrics().catch(e=>setError(e.message))}>Download metrics CSV</button>
    {error && <p role="alert">{error}</p>}
    <h3>Event history</h3><label>Event category<select value={filter} onChange={e=>{setFilter(e.target.value);setVisible(80);}}>{['ALL',...new Set(events.map(e=>e.type))].map(type=><option key={type}>{type}</option>)}</select></label>
    <p>Showing {Math.min(visible,filtered.length)} of {filtered.length} events</p>
    {filtered.slice(0,visible).map((e,i)=><p key={`${e.step}-${e.type}-${e.message}-${i}`}>Step {e.step} · {e.type} · {e.message}</p>)}
    {visible<filtered.length&&<button onClick={()=>setVisible(v=>v+80)}>Load older events</button>}
  </section>;
}
