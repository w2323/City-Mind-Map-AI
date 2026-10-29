import {useState} from 'react';
export default function LeftPanel({stats,onOptimization,viewToggles,onToggleView,onStart,onStep,starting,stepping,simSpeed,onSpeedChange,placementMode,onPlacementModeChange,roadMode,onRoadModeChange,gatesNodeLabel,onGatesNodeChange,algoMode,onAlgoModeChange,onResetView,workspace='city',quality,onQualityChange}) {
  const [runs,setRuns]=useState(1);
  if(!stats)return null;
  const job=stats.optimization||{},busy=starting||stepping;
  const showMap=workspace==='city'||workspace==='heatmap',showGA=workspace==='city'||workspace==='ambulance';
  return <section className="workspace-content" aria-label={workspace==='ambulance'?'Ambulance planning':workspace==='heatmap'?'Map layers':'City controls'}>
    <h2>{workspace==='ambulance'?'Ambulance planning':workspace==='heatmap'?'Heatmap & coverage':'City map tools'}</h2>
    <p className="panel-intro">{workspace==='ambulance'?'Inspect deployed units, compare access and plan medical-center placement.':'Explore sectors, inspect roads and choose the layers you need.'}</p>
    {showMap&&<>
      <h3>Map layers</h3>
      {[['roads','Road Network'],['labels','Sector Labels'],['ids','Sector IDs'],['costs','Road Costs'],['heatmap','Crime Heatmap'],['population','Sector Population'],['coverage','Ambulance Coverage'],['policeCoverage','Police Presence'],['trails','Agent Trails'],['traffic','City Traffic'],['signals','Traffic Signals']].map(([key,label])=><label className="toggle-row" key={key}><span className="toggle-row__label">{label}</span><input className={`toggle-switch ${viewToggles[key]?'toggle-switch--on':''}`} type="checkbox" checked={!!viewToggles[key]} onChange={()=>onToggleView(key)}/></label>)}
      <p>Numbers run across columns; letters run down rows. A2 is beside A1, and B1 is below A1.</p>
      <p>Signals cycle at junctions and control background city traffic. Emergency vehicles follow the backend dispatch model.</p>
      <p>Medical coverage: {stats.coveragePct}% · {stats.deadZones} residential dead zones</p>
      <h3>Road network</h3>
      <label>Road view<select aria-label="Road view" value={roadMode} onChange={e=>onRoadModeChange(e.target.value)}>{['All roads','Optimized (MST)','Optimized (2-connected)','Comparison'].map(option=><option key={option}>{option}</option>)}</select></label>
      <label>Comparison view<select aria-label="Comparison view" value={algoMode} onChange={e=>onAlgoModeChange(e.target.value)}>{['Single Algorithm','Side-by-side Comparison','Multi-view'].map(option=><option key={option}>{option}</option>)}</select></label>
      <p>{stats.metrics.total_edges_active} open roads · {stats.bridgeCount} bridges · {stats.componentCount} components</p>
    </>}
    {showGA&&<>
      <h3>Medical-center optimization</h3>
      <div className="button-row"><button disabled={busy||job.status==='running'} onClick={()=>onOptimization('start',runs)}>{job.status==='paused'?'Resume':'Start'}</button><button disabled={busy||job.status!=='running'} onClick={()=>onOptimization('pause')}>Pause</button><button disabled={busy} onClick={()=>onOptimization('reset')}>Reset</button></div>
      <label>Optimization runs<input aria-label="Optimization runs" type="number" min="1" max={stats.config.optimization_max_runs} value={runs} onChange={e=>setRuns(Math.max(1,Math.min(stats.config.optimization_max_runs,Number(e.target.value)||1)))}/></label>
      <div className="info-card"><b>{job.status==='completed'?'OPTIMIZATION COMPLETE':`Status: ${job.status}`}</b><p>Generation {job.generation||0} / {stats.config.ga_generations} · Run {job.run||0}/{job.runs||runs}</p><p>Best cost: {job.fitness?.toFixed(3)??'Awaiting search'}</p></div>
      <h3>Ambulance route candidates</h3>
      <label>Target sector<input aria-label="Ambulance route target" placeholder="C4" value={gatesNodeLabel} onChange={e=>onGatesNodeChange(e.target.value.toUpperCase())}/></label>
      <label>Show routes<select aria-label="Ambulance route candidates" value={placementMode} onChange={e=>onPlacementModeChange(e.target.value)}><option>Current</option><option value="Optimizing...">Nearest deployed ambulance</option><option>Best found</option><option>All candidates</option></select></label>
      <p>Average response: {stats.metrics.avg_response_time} steps · Worst road cost: {stats.worstResponseCost??'Unreachable'}</p>
    </>}
    <h3>Experience</h3>
    <label>Graphics<select aria-label="Graphics quality" value={quality} onChange={e=>onQualityChange(e.target.value)}><option value="economy">Economy — fewer moving details</option><option value="balanced">Balanced</option><option value="high">High resolution</option></select></label>
    <label>Simulation speed · {simSpeed}×<input aria-label="Simulation speed" type="range" min=".25" max="4" step=".25" value={simSpeed} onChange={e=>onSpeedChange(Number(e.target.value))}/></label>
    <div className="button-row"><button onClick={onResetView}>Fit city</button><button disabled={busy||stats.isComplete} onClick={onStep}>Advance one step</button><button disabled={busy} onClick={onStart}>Restart city</button></div>
    <h3>Sector legend</h3>
    <div className="sector-legend">{[['Residential',stats.residential,'#c8bbaa'],['Medical centers',stats.hospitals,'#8ac9bf'],['Schools',stats.schools,'#ddc37d'],['Industrial',stats.industrial,'#a69889'],['Financial',stats.typeCounts?.BANK||0,'#8b9eaa']].map(([title,count,color])=><div key={title}><i style={{background:color}}/>{title}<b>{count}</b></div>)}</div>
  </section>;
}
