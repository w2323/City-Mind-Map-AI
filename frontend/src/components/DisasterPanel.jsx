export default function DisasterPanel({state,graph,busy,mode,onMode,center,centerLabel,onCenter,intensity,onIntensity,preview,road,onRoadSelect,onRoad,onGate,onClear}) {
  const label=id=>graph.nodes.find(n=>n.id===id)?.label||'—';
  const edge=graph.edges.find(e=>road&&Math.min(e.node_a,e.node_b)===Math.min(...road)&&Math.max(e.node_a,e.node_b)===Math.max(...road));
  return <section className="workspace-content" aria-label="Disaster controls">
    <h2>Disasters</h2><p className="panel-intro">Close a road, reopen access or preview a Gate of Death before applying it.</p>
    <div className="button-row">{['block','unblock'].map(key=><button key={key} aria-pressed={mode===key} onClick={()=>onMode(key)}>{key==='block'?'Block Road':'Unblock Road'}</button>)}</div>
    <button aria-pressed={mode==='gate'} onClick={()=>onMode('gate')}>Unleash Gate of Death</button>
    {mode==='gate'?<>
      <h3>Gate preview</h3><label>Center sector<input aria-label="Gate center sector" value={centerLabel} placeholder="H8" onChange={e=>onCenter(e.target.value.toUpperCase())}/></label>
      <label>Gate intensity<select aria-label="Gate intensity" value={intensity} onChange={e=>onIntensity(Number(e.target.value))}>{(state.disasters?.levels||[]).map(l=><option key={l.intensity} value={l.intensity}>{['First','Second','Third','Fourth','Fifth','Sixth','Seventh','Eighth'][l.intensity-1]} Gate of Death — radius {l.radius}</option>)}</select></label>
      <p>Selected center: {label(center)} · {preview?.road_count??'—'} affected roads</p><p>Gate restrictions allow ambulance traffic. Exposed vehicles and facilities may be unavailable.</p>
      <button disabled={busy||center==null} onClick={()=>onGate(center,intensity)}>Unleash selected gate</button>
    </>:<>
      <h3>Select a road</h3><p>Click a road surface in the city or select its endpoints below.</p>
      <label>Road segment<select aria-label="Road segment" value={road?`${Math.min(...road)}-${Math.max(...road)}`:''} onChange={e=>onRoadSelect(e.target.value.split('-').map(Number))}><option value="" disabled>Choose a road</option>{graph.edges.map(e=><option key={`${e.node_a}-${e.node_b}`} value={`${Math.min(e.node_a,e.node_b)}-${Math.max(e.node_a,e.node_b)}`}>{label(e.node_a)} – {label(e.node_b)}{e.blocked?' · closed':e.temporarily_blocked?' · ambulances only':''}</option>)}</select></label>
      <p>{edge?`Selected road: ${label(road[0])} – ${label(road[1])} · ${edge.blocked?'Fully blocked':edge.temporarily_blocked?'Ambulances only':'Open to all traffic'}`:'No road selected'}</p>
      <button disabled={busy||!edge||(mode==='block'?edge.blocked:!(edge.blocked||edge.temporarily_blocked))} onClick={()=>onRoad(mode,...road)}>{mode==='block'?'Block selected road':'Unblock selected road'}</button>
    </>}
    <h3>Network restrictions</h3><p>{state.disasters?.ambulance_only_roads||0} ambulance-only roads · {state.disasters?.fully_blocked_roads||0} fully closed</p>
    <button disabled={busy||!state.disasters?.gates?.length} onClick={onClear}>Clear gate restrictions</button>
    <h3>Disaster history</h3>{[...(state.disasters?.history||[])].reverse().slice(0,30).map((e,i)=><p key={i}>Step {e.step} · {e.message}</p>)}
  </section>;
}
