import {useState,useEffect,useRef} from 'react';
import {calculateRoute} from '../api/citymind';
import {referenceRoute} from '../engine/referenceRoute';
import './operations.css';

export default function RouteLab({state,selectedNode,onPaths,onClose}) {
  const [src,setSrc]=useState('');
  const [dst,setDst]=useState('');
  const [mode,setMode]=useState('normal');
  const [result,setResult]=useState(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const request=useRef(null);
  const identity=`${state.sim_id}:${state.revision}`;
  const current=useRef(identity);current.current=identity;
  const label=id=>state.graph.nodes.find(n=>n.id===id)?.label || id;
  useEffect(()=>{
    request.current?.abort();setBusy(false);setResult(null);onPaths([]);
    return ()=>{request.current?.abort();onPaths([]);};
  },[identity,src,dst,mode,onPaths]);
  async function run(e) {
    e.preventDefault();setError('');setResult(null);onPaths([]);
    const source=state.graph.nodes.find(n=>n.label===src.trim().toUpperCase());
    const target=state.graph.nodes.find(n=>n.label===dst.trim().toUpperCase());
    if(!source || !target) {setError('Enter valid source and destination sectors.');return;}
    const controller=new AbortController();request.current=controller;setBusy(true);
    try {
      const reference=referenceRoute(state.graph,source.id,target.id,mode);
      const backend=await calculateRoute(source.id,target.id,mode,controller.signal);
      if(controller.signal.aborted || current.current!==identity || `${backend.sim_id}:${backend.revision}`!==identity) return;
      setResult({reference,backend});
      onPaths([{path:reference.path,color:'#00ddcc'},{path:backend.path || [],color:'#cc88ff'}]);
    } catch(err) {if(!controller.signal.aborted)setError(err.response?.data?.detail || err.message);}
    finally {if(!controller.signal.aborted)setBusy(false);}
  }
  return <section className="operations-panel" aria-label="Route lab">
    <header><h2>Route lab</h2><button onClick={onClose} aria-label="Close route lab">×</button></header>
    <p>Compare backend A* with independent Dijkstra on the same city snapshot. Pause playback to inspect results.</p>
    <form onSubmit={run}>
      <label>Source sector<input aria-label="Route source" value={src} onChange={e=>setSrc(e.target.value.toUpperCase())}/></label>
      <button type="button" disabled={selectedNode==null} onClick={()=>setSrc(label(selectedNode))}>Selected sector as source</button>
      <label>Destination sector<input aria-label="Route destination" value={dst} onChange={e=>setDst(e.target.value.toUpperCase())}/></label>
      <button type="button" disabled={selectedNode==null} onClick={()=>setDst(label(selectedNode))}>Selected sector as destination</button>
      <label>Travel mode<select aria-label="Route travel mode" value={mode} onChange={e=>setMode(e.target.value)}><option value="normal">Normal / commercial</option><option value="ambulance">Ambulance</option></select></label>
      <button disabled={busy}>{busy?'Calculating…':'Calculate route'}</button>
      <button type="button" onClick={()=>{setSrc('');setDst('');setError('');}}>Clear route</button>
    </form>
    {error && <p role="alert">{String(error)}</p>}
    {result && <>
      <h3>Algorithm comparison</h3>
      <p>A*: {result.backend.reachable?`cost ${result.backend.path_cost}`:'Unreachable'}</p>
      <p>Dijkstra: {result.reference.reachable?`cost ${result.reference.path_cost.toFixed(4)}`:'Unreachable'}</p>
      <p>{result.backend.reachable===result.reference.reachable && (!result.reference.reachable || Math.abs(result.backend.path_cost-result.reference.path_cost)<.001)?'Verified: algorithms agree':'Warning: algorithm results differ'}</p>
      <p>{result.backend.path?.map(label).join(' → ')}</p>
      <h3>Per-road costs</h3><table><thead><tr><th>Road</th><th>Base</th><th>Risk ×</th><th>Cost</th></tr></thead><tbody>{result.reference.breakdown.map(e=><tr key={`${e.from}-${e.to}`}><td>{label(e.from)} → {label(e.to)}</td><td>{e.base}</td><td>{e.multiplier}</td><td>{e.cost.toFixed(2)}</td></tr>)}</tbody></table>
    </>}
  </section>;
}
