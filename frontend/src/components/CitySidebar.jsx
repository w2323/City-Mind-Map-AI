export const WORKSPACES=[
  ['medical','01','Dispatch','MEDICAL DISPATCH'],['city','02','City Map','CITY MAP'],['routes','03','Route Lab','ROUTE LAB'],
  ['disasters','04','Disasters','DISASTERS'],['ambulance','05','Ambulance','AMBULANCE'],['heatmap','06','Heatmap','HEATMAP'],
  ['police','07','Police','POLICE OPERATIONS'],['metrics','08','Metrics','METRICS'],['diagnostics','09','Diagnostics','DIAGNOSTICS'],['events','10','City Events','CITY EVENTS'],
];
export default function CitySidebar({active,onNavigate,state,connected,playing,onTogglePlaying,onStep,busy,onRestart,onControls}) {
  return <aside className="city-sidebar">
    <div className="city-brand"><span className="brand-mark">C<span>·</span></span><div><strong>CITYMIND</strong><small>CITY OPERATIONS</small></div></div>
    <div className="sidebar-district"><span className={`connection-dot ${connected?'is-live':''}`}/><span>Central district</span><small>{connected?'CONNECTED':'OFFLINE'}</small></div>
    <div className="sidebar-caption">WORKSPACES</div>
    <nav aria-label="City workspaces">{WORKSPACES.map(([key,number,title,label])=><button key={key} aria-label={label} aria-current={active===key?'page':undefined} onClick={()=>onNavigate(key)}><span className="nav-number">{number}</span><span>{title}</span>{active===key&&<i/>}</button>)}</nav>
    <div className="sidebar-bottom">
      <div className="sidebar-step"><span>SIMULATION</span><b>{state.step}<small> / {state.max_steps}</small></b></div>
      <progress value={state.step} max={state.max_steps}/>
      <div className="sidebar-playback"><button disabled={state.is_complete&&!playing} onClick={onTogglePlaying} aria-label={playing?'PAUSE PLAYBACK':'PLAY SIMULATION'}>{playing?'Ⅱ Pause':'▶ Play'}</button><button disabled={busy||state.is_complete} onClick={onStep} aria-label="NEXT STEP">Step →</button></div>
      <button className="sidebar-secondary" title="Open Controls" onClick={onControls}>City & camera controls <span>↗</span></button>
      <button className="sidebar-secondary" disabled={busy} onClick={onRestart}>New city <span>↻</span></button>
    </div>
  </aside>;
}
