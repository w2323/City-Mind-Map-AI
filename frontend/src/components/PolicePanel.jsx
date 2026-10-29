import { useEffect, useState } from 'react';
import { policeAction } from '../api/citymind';
import SettingRange from './SettingRange';

export default function PolicePanel({police={},fleet=[],air={},selectedNode,graph,onAction,onHelicopter,busy,onPlay,onPause,complete=false,onRestart}) {
  const [node,setNode]=useState('');
  const [kind,setKind]=useState('THEFT');
  const [severity,setSeverity]=useState(1);
  const [medical,setMedical]=useState(false);
  const [comparison,setComparison]=useState(null);
  const [comparing,setComparing]=useState(false);
  const [seed,setSeed]=useState('');
  const [comparisonSteps,setComparisonSteps]=useState(40),[comparisonReports,setComparisonReports]=useState(8);
  const [pendingAction,setPendingAction]=useState('');
  const [error,setError]=useState('');
  const [station,setStation]=useState('');
  const [reportFilter,setReportFilter]=useState('all'),[reportLimit,setReportLimit]=useState(40);
  const selectedLabel=graph?.nodes?.find(n=>n.id===selectedNode)?.label;
  useEffect(()=>{ if (selectedLabel) setNode(selectedLabel); },[selectedLabel]);
  const summary=police.summary || {};
  const settings=police.settings || {};
  const plan=police.recommendations;
  const choices=plan?.additions||[];
  const choicesKey=choices.map(s=>s.label).join(',');
  useEffect(()=>{setStation(current=>choices.some(s=>s.label===current)?current:choices[0]?.label||'');},[choicesKey]);
  const target=graph?.nodes?.find(n=>n.label===node.trim().toUpperCase());
  const stationReason=!plan?'Calculate station recommendations first.':plan.stale?'Roads or crime conditions changed. Recalculate station recommendations.':!choices.length?(plan.restore_road_nodes?.length?'Isolated financial sectors need their road access restored. A police station cannot be built inside a financial sector.':'Current stations already cover the recommended sites. No additional station is needed.'):'';
  const visibleReports=[...(police.reports||[])].reverse().filter(r=>reportFilter==='all'||(reportFilter==='active'?r.status!=='RESOLVED':r.status==='RESOLVED'));
  const action=async(name,payload)=>{setPendingAction(name);try{return await onAction(name,payload);}finally{setPendingAction('');}};
  const runResponse=async(name,payload)=>{ if(await action(name,payload)) onPlay(); };
  async function compare() {
    if(seed!==''&&(!Number.isInteger(Number(seed))||Number(seed)<0||Number(seed)>4294967295)){setError('Comparison seed must be a whole number between 0 and 4294967295.');return;}
    setComparing(true);setError('');
    try {
      setComparison(await policeAction('compare',{seed:seed===''?42:Number(seed),steps:comparisonSteps,incident_count:comparisonReports}));
    } catch(err) {setError(err.response?.data?.detail || err.message);}
    finally {setComparing(false);}
  }
  return <section className="police-panel" aria-label="Police operations" style={{position:'fixed',right:18,top:70,zIndex:110,width:390,maxHeight:'84vh',overflowY:'auto',padding:18,background:'rgba(11,20,36,.97)',border:'1px solid #8b5cf6',borderRadius:12,color:'#fff',fontSize:12}}>
    <h2 style={{marginTop:0}}>Police operations</h2>
    {busy&&<p role="status">{pendingAction==='plan'?'Calculating station recommendations…':'Saving your police action…'}</p>}
    {complete&&<div className="info-card"><p>Simulation finished. Start a new city to report more incidents.</p><button disabled={busy} onClick={onRestart}>Start a new city</button></div>}
    <p>{summary.available || 0}/{summary.total_units || 0} ready cars · {summary.unresolved || 0} unresolved · {summary.queued || 0} queued · {summary.unreachable || 0} unreachable</p>
    <form onSubmit={e=>{e.preventDefault();runResponse('report',{node,kind,severity,medical_required:medical});}}>
      <label>Report sector <input aria-label="Crime report sector" value={node} maxLength={10} onChange={e=>setNode(e.target.value.toUpperCase())} placeholder="C4" required /></label>
      <p><label>Incident type <select aria-label="Crime incident type" value={kind} onChange={e=>setKind(e.target.value)}>
        {(police.incident_types || []).map(type=><option key={type}>{type}</option>)}
      </select></label></p>
      <p><label>Severity <select aria-label="Crime severity" value={severity} onChange={e=>setSeverity(Number(e.target.value))}>
        {(police.severity_levels || []).map(level=><option key={level} value={level}>{level}</option>)}
      </select></label></p>
      <p><label><input type="checkbox" checked={medical || kind==='INJURY'} disabled={kind==='INJURY'} onChange={e=>setMedical(e.target.checked)} /> Medical assistance{kind==='INJURY'?' (required for injuries)':''}</label></p>
      <button disabled={busy || !target || complete} title={!target?'Enter a valid sector or select a building.':complete?'Start a new city before reporting.':undefined}>Report and dispatch police</button>
      {!target&&<p>Enter a sector such as C4, or click a building on the map.</p>}
      <p>Injury or Medical assistance dispatches police and an available ambulance together. Blue routes show ambulances; purple routes show police.</p>
    </form>
    <hr />
    <p><button disabled={busy} onClick={()=>settings.patrol_enabled?action('settings',{patrol_enabled:false}):runResponse('settings',{patrol_enabled:true})}>Patrols: {settings.patrol_enabled?'ON':'OFF'}</button>{' '}
      <button disabled={busy} onClick={()=>settings.automatic_incidents?action('settings',{automatic_incidents:false}):runResponse('settings',{automatic_incidents:true})}>Automatic reports: {settings.automatic_incidents?'ON':'OFF'}</button></p>
    <p>{settings.patrol_enabled?`High: dedicated continuous circuits. Medium: revisit after ${police.patrol_policy?.revisit_steps?.MEDIUM ?? 8} steps. Low: revisit after ${police.patrol_policy?.revisit_steps?.LOW ?? 24} steps. Reports take priority.`:'Patrols OFF: idle cars stay parked. Reports still dispatch; existing cases and their return trips continue.'}</p>
    <p>High areas with assigned patrol: {(police.patrol_policy?.hotspots || []).filter(z=>z.assigned_units.length).length}/{police.patrol_policy?.hotspots?.length || 0}; cars currently present in {(police.patrol_policy?.hotspots || []).filter(z=>z.present_units.length).length} areas. Closures and busy cars can leave coverage gaps.</p>
    <SettingRange label="Automatic incident chance" value={settings.auto_probability || 0} onCommit={value=>action('settings',{auto_probability:value})}/>
    <p>Mean response: {summary.mean_response_steps ?? '—'} steps · Police handled: {summary.police_handled || 0} · Medical pending: {summary.medical_pending || 0}</p>
    <p>Station road coverage: {summary.coverage_pct || 0}%</p>
    <p>Reported crime affects a radius of {police.crime_report_radius ?? '—'} sector units. Enable Crime Heatmap to see the area.</p>
    <h3>Station planning</h3>
    <p><button disabled={busy} onClick={()=>{onPause?.();action('plan');}}>Plan police stations</button></p>
    {!!choices.length&&<label>Recommended station site<select aria-label="Recommended station site" value={station} onChange={e=>setStation(e.target.value)}>{choices.map(s=><option key={s.node_id} value={s.label}>{s.label} · +{s.gain} unserved sectors</option>)}</select></label>}
    <button disabled={busy || !!stationReason || !station} title={stationReason || 'Build at the selected recommended site'} onClick={()=>{onPause?.();action('station',{node:station});}}>Open recommended station</button>
    {stationReason&&<p role="note">{stationReason}</p>}
    <p>Planning pauses playback so recommendations stay usable while you choose a site. Existing stations and cars stay in place.</p>
    {plan && <p>Proposed sites: {plan.labels.join(', ')}{plan.stale?' (recalculate before construction)':''}</p>}
    <h3>Compare police strategies</h3>
    <label>Comparison steps<input aria-label="Police comparison steps" type="number" min="20" max="200" value={comparisonSteps} disabled={comparing} onChange={e=>setComparisonSteps(Math.min(200,Math.max(20,Number(e.target.value)||20)))}/></label>
    <label>Identical reports<input aria-label="Police comparison report count" type="number" min="1" max="30" value={comparisonReports} disabled={comparing} onChange={e=>setComparisonReports(Math.min(30,Math.max(1,Number(e.target.value)||1)))}/></label>
    <p><input aria-label="Police comparison seed" type="number" min="0" max="4294967295" step="1" value={seed} placeholder="Optional replay seed" disabled={comparing} onChange={e=>setSeed(e.target.value)} size="17" />{' '}
      <button disabled={comparing} onClick={compare}>{comparing?'Comparing…':'Compare police strategies'}</button></p>
    {comparing&&<p role="status">Running both strategies through {comparisonSteps} steps with {comparisonReports} matched reports. The city remains interactive while the comparison runs.</p>}
    {error && <p role="alert">{String(error)}</p>}
    {comparison && <><p>Seed {comparison.seed} · {comparison.incident_count} identical reports · {comparison.steps} steps</p><table style={{width:'100%'}}><thead><tr><th>Strategy</th><th>Handled</th><th>Unresolved</th><th>Mean steps</th></tr></thead><tbody>
      {comparison.results.map(r=><tr key={r.strategy}><td>{r.strategy}</td><td>{r.police_handled}</td><td>{r.unresolved}</td><td>{r.mean_response_steps ?? '—'}</td></tr>)}
    </tbody></table><p>Mean includes arrivals only; compare unresolved reports too.</p></>}
    <h3>Stations and patrol fleet</h3>
    <p>Financial sectors: maximum {police.bank_max_blocks || 3} grid units from a road-accessible station.</p>
    {(police.banks || []).map(b=><div key={b.node_id}>Financial sector {b.label} · {b.protected?`${b.station_id} at ${b.station_label} · ${b.grid_blocks} units ${b.police_direction || ''}`:'NO NEARBY ROAD ACCESS'}</div>)}
    <p>{(police.stations || []).map(s=>`${s.id}: ${s.label}`).join(' · ')}</p>
    {(police.units || []).map(u=><div key={u.id}>{u.id} · {u.position_label} · {u.status} · {u.report_id || (u.target_label ? 'To '+u.target_label : 'Parked / awaiting report')}</div>)}
    <h3>Medical response fleet</h3>
    {fleet.map(u=><div key={u.id}>{u.id} · {u.position_label} · {u.status} · {u.emergency_id || 'Awaiting dispatch'}</div>)}
    <p>Helicopter: {air.status} · Fuel {air.fuel_pct}% · Safe pads: {(air.landing_sites || []).filter(s=>s.available).map(s=>s.label).join(', ') || 'None'}</p>
    <p>Flight: building → emergency → nearest safe hospital → closest safe building. Hospitals are delivery stops, never helicopter bases.</p>
    {air.relocation_required && <div role="alert"><p>{air.relocation?.reason}</p><button disabled={busy || !air.relocation?.can_relocate} onClick={async()=>{if(await onHelicopter('relocate'))onPlay();}}>Relocate helicopter</button></div>}
    <button disabled={busy || air.landed_node==null || air.fuel_pct>=100} title={air.landed_node==null?'The helicopter must land before refueling.':air.fuel_pct>=100?'Fuel is already full.':'Refuel at the current pad.'} onClick={()=>onHelicopter('refuel')}>Refuel helicopter</button>
    <p>{air.landed_node==null?'Refueling becomes available when the helicopter lands.':air.fuel_pct>=100?'Helicopter fuel is full.':'Refueling is available at this landing pad.'}</p>
    <h3>Crime reports</h3>
    <label>Report view<select aria-label="Police report view" value={reportFilter} onChange={e=>{setReportFilter(e.target.value);setReportLimit(40);}}><option value="all">All reports</option><option value="active">Active reports</option><option value="resolved">Resolved reports</option></select></label>
    <p>Showing {Math.min(reportLimit,visibleReports.length)} of {visibleReports.length} reports</p>
    {visibleReports.slice(0,reportLimit).map(r=><div key={r.id} style={{borderTop:'1px solid #dbe4d1',padding:'8px 0'}}>
      <strong>{r.id} · {r.label} · {r.kind} · severity {r.severity}</strong><div>{r.status} · {r.unit_id || 'Unassigned'}</div>
      <div>Police: {r.police_status} / Medical: {r.medical_status}</div><div>{r.reason}</div>
      {r.medical_status==='HELICOPTER_REQUIRED' && <button disabled={busy} onClick={()=>runResponse('medical',{report_id:r.id})}>Request medical helicopter</button>}
    </div>)}
    {reportLimit<visibleReports.length&&<button onClick={()=>setReportLimit(n=>n+40)}>Show older reports</button>}
    <p style={{color:'#a5b4cc'}}>Each sector represents multiple buildings or activities. Crime scores describe the area; police stations are service facilities within sectors.</p>
  </section>;
}
