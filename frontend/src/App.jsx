import {useState,useCallback,useEffect,useMemo} from 'react';
import {useSimulation} from './hooks/useSimulation';
import GraphCanvas3D from './components/GraphCanvas3D';
import CitySidebar,{WORKSPACES} from './components/CitySidebar';
import LeftPanel from './components/LeftPanel';
import TopBar from './components/TopBar';
import RightPanel from './components/RightPanel';
import HealthDashboard from './components/HealthDashboard';
import OperationsPanel from './components/OperationsPanel';
import PolicePanel from './components/PolicePanel';
import RouteLab from './components/RouteLab';
import CityEventsPanel from './components/CityEventsPanel';
import DiagnosticsPanel from './components/DiagnosticsPanel';
import DisasterPanel from './components/DisasterPanel';
import FleetAnalytics from './components/FleetAnalytics';
import {getAmbulanceRoutes,previewGate} from './api/citymind';
import './city.css';

export default function App() {
  const sim=useSimulation();
  const [workspace,setWorkspace]=useState('city'),[controlsOpen,setControlsOpen]=useState(false);
  const [selectedNode,setSelectedNode]=useState(null),[selectedRoad,setSelectedRoad]=useState(null);
  const [playing,setPlaying]=useState(false),[simSpeed,setSimSpeed]=useState(1);
  const [cameraMode,setCameraMode]=useState('orbit'),[resetTrigger,setResetTrigger]=useState(0),[focusTrigger,setFocusTrigger]=useState(0);
  const [quality,setQuality]=useState('balanced'),[dashOpen,setDashOpen]=useState(false);
  const [algoMode,setAlgoMode]=useState('Single Algorithm'),[roadMode,setRoadMode]=useState('Optimized (2-connected)');
  const [placementMode,setPlacementMode]=useState('Current'),[gatesNodeLabel,setGatesNodeLabel]=useState(''),[candidatePaths,setCandidatePaths]=useState([]),[routePaths,setRoutePaths]=useState([]),[notice,setNotice]=useState('');
  const [disasterMode,setDisasterMode]=useState('block'),[disasterCenter,setDisasterCenter]=useState(null),[disasterCenterLabel,setDisasterCenterLabel]=useState(''),[gateIntensity,setGateIntensity]=useState(1),[gatePreview,setGatePreview]=useState(null);
  const [viewToggles,setViewToggles]=useState({roads:true,coverage:false,heatmap:false,population:false,policeCoverage:false,trails:true,traffic:true,signals:true,labels:true,ids:false,costs:false});
  const godMode=workspace==='disasters';
  const closePanel=useCallback(()=>{setWorkspace('city');setControlsOpen(false);},[]);
  const play=useCallback(()=>setPlaying(true),[]);
  const togglePlay=useCallback(()=>setPlaying(p=>!p),[]);
  const navigate=useCallback(key=>{
    setWorkspace(key);setControlsOpen(key==='city');
    if(key==='routes')setPlaying(false);
    if(key==='heatmap')setViewToggles(v=>({...v,heatmap:true,population:false}));
  },[]);
  useEffect(()=>{
    const listener=e=>{
      if(e.target instanceof HTMLElement&&e.target.closest('input,textarea,select,[contenteditable="true"]'))return;
      const index=Number(e.key)-1;
      if(index>=0&&index<9)navigate(WORKSPACES[index][0]);
      if(e.key==='Escape')closePanel();
    };
    window.addEventListener('keydown',listener);return ()=>window.removeEventListener('keydown',listener);
  },[navigate,closePanel]);
  useEffect(()=>{
    if(!playing||!sim.connected||sim.stats?.isComplete||sim.stats?.optimization?.status==='running')return;
    const timer=setInterval(()=>sim.handleStep(),1000/simSpeed);return ()=>clearInterval(timer);
  },[playing,sim.connected,sim.stats?.isComplete,sim.stats?.optimization?.status,simSpeed,sim.handleStep]);
  useEffect(()=>{if(!sim.message)return;const timer=setTimeout(sim.clearMessage,6000);return ()=>clearTimeout(timer);},[sim.message]);
  useEffect(()=>{setSelectedNode(null);setSelectedRoad(null);setDisasterCenter(null);setDisasterCenterLabel('');setCandidatePaths([]);setNotice('');},[sim.state?.sim_id]);
  const onSelect=useCallback(id=>{
    if(godMode&&disasterMode==='gate'){setDisasterCenter(id);setDisasterCenterLabel(sim.graph?.nodes.find(n=>n.id===id)?.label||'');}
    else {setSelectedNode(id);setSelectedRoad(null);}
  },[godMode,disasterMode,sim.graph]);
  const toggleLayer=useCallback(key=>setViewToggles(v=>({...v,[key]:!v[key],...(key==='population'&&!v[key]?{heatmap:false}:key==='heatmap'&&!v[key]?{population:false}:{})})),[]);
  const candidateTarget=sim.graph?.nodes.find(n=>n.label===gatesNodeLabel.trim().toUpperCase());
  useEffect(()=>{
    setCandidatePaths([]);setNotice('');
    if(!candidateTarget||placementMode==='Current')return;
    const controller=new AbortController(),id=sim.state.sim_id,revision=sim.state.revision;
    getAmbulanceRoutes(candidateTarget.id,controller.signal).then(result=>{
      if(controller.signal.aborted||result.sim_id!==id||result.revision!==revision)return;
      if(!result.best){setNotice('No available ambulance can reach this sector.');return;}
      if(placementMode==='Optimizing...')setNotice(`${result.best.ambulance_id} at ${result.best.src_label} is closest, road cost ${result.best.path_cost}.`);
      const routes=placementMode==='All candidates'?result.candidates.filter(r=>r.reachable):[result.best];
      setCandidatePaths(routes.map((r,i)=>({path:r.path,color:['#229fba','#d17f45','#9170bd','#397653'][i%4]})));
    }).catch(e=>{if(!controller.signal.aborted)setNotice(e.message);});
    return ()=>controller.abort();
  },[candidateTarget?.id,placementMode,sim.state?.sim_id,sim.state?.revision]);
  useEffect(()=>{
    setGatePreview(null);if(!godMode||disasterMode!=='gate'||disasterCenter==null)return;
    const controller=new AbortController();previewGate(disasterCenter,gateIntensity,controller.signal).then(result=>{if(!controller.signal.aborted)setGatePreview(result);}).catch(e=>{if(!controller.signal.aborted)setNotice(e.message);});return ()=>controller.abort();
  },[godMode,disasterMode,disasterCenter,gateIntensity,sim.state?.sim_id,sim.state?.revision]);
  const paths=useMemo(()=>[...candidatePaths,...routePaths],[candidatePaths,routePaths]);
  const resetView=()=>{setSelectedNode(null);setFocusTrigger(0);setCameraMode('orbit');setResetTrigger(t=>t+1);};
  const restart=()=>{setPlaying(false);sim.handleStart();};
  if(!sim.state)return <div className="city-loading"><div className="loading-emblem">C·</div><h1>CityMind</h1><p>{sim.error||'Connecting to your city…'}</p>{sim.error&&<button onClick={sim.loadData}>Retry connection</button>}</div>;
  const state=sim.state,stats=sim.stats,busy=sim.acting||sim.starting;
  const hasPanel=workspace!=='city'||controlsOpen;
  const title=WORKSPACES.find(w=>w[0]===workspace)?.[2]||'City Map';
  const selectedRoadData=state.graph.edges.find(e=>selectedRoad&&Math.min(e.node_a,e.node_b)===Math.min(...selectedRoad)&&Math.max(e.node_a,e.node_b)===Math.max(...selectedRoad));
  const nodeLabel=id=>state.graph.nodes.find(n=>n.id===id)?.label;
  const renderCity=(overrides={})=><GraphCanvas3D graph={sim.graph} state={state} stats={stats} booted selectedNode={selectedNode} onSelectNode={onSelect} viewToggles={viewToggles} simSpeed={simSpeed} resetTrigger={resetTrigger} focusTrigger={focusTrigger} cameraMode={cameraMode} quality={quality} roadMode={roadMode} gatesNodeId={candidateTarget?.id} gatesPaths={paths} godMode={godMode} disasterMode={disasterMode} disasterCenter={disasterCenter} gateIntensity={gateIntensity} selectedRoad={selectedRoad} onSelectRoad={edge=>{setSelectedRoad([edge.nodeA,edge.nodeB]);if(!godMode)setSelectedNode(null);}} {...overrides}/>;
  return <div className={`city-app ${hasPanel?'has-workspace-panel':''} ${cameraMode==='street'?'is-walking':''}`}>
    <CitySidebar active={workspace} onNavigate={navigate} state={state} connected={sim.connected} playing={playing} onTogglePlaying={togglePlay} onStep={sim.handleStep} busy={busy} onRestart={restart} onControls={()=>{setWorkspace('city');setControlsOpen(v=>!v);}}/>
    <main className="city-main">
      <div className="city-scene">
        {algoMode==='Single Algorithm'?renderCity():<div className={`city-multiview ${algoMode==='Multi-view'?'four-views':''}`}>
          <div><span className="view-label">All roads</span>{renderCity({roadMode:'All roads',quality:'economy'})}</div>
          <div><span className="view-label">{roadMode}</span>{renderCity({quality:'economy'})}</div>
          {algoMode==='Multi-view'&&<><div><span className="view-label">Minimum spanning tree</span>{renderCity({roadMode:'Optimized (MST)',quality:'economy'})}</div><div><span className="view-label">Medical response</span>{renderCity({quality:'economy'})}</div></>}
        </div>}
      </div>
      <TopBar stats={stats} connected={sim.connected} onToggleDash={()=>setDashOpen(v=>!v)}/>
      <div className="city-heading"><span>LIVE CITY / CENTRAL DISTRICT</span><h1>{title==='City Map'?'A city in motion.':title}</h1><p>{state.graph.nodes.length} sectors · {state.fleet.length} medical units · {state.police?.units?.length||0} patrol vehicles</p></div>
      <div className="camera-dock" aria-label="Camera controls">
        {[['orbit','Orbit city'],['map','Map overview'],['street','Walk streets']].map(([key,label])=><button key={key} aria-pressed={cameraMode===key} onClick={()=>{setCameraMode(key);setResetTrigger(t=>t+1);}}>{label}</button>)}
        <span className="camera-divider"/><button onClick={resetView} title="Center View">↺ Reset</button>
        <button disabled={selectedNode==null} onClick={()=>setFocusTrigger(t=>t+1)}>Focus selected</button>
      </div>
      <div className="camera-hint">{cameraMode==='street'?<><b>STREET EXPLORER</b> Drag to look · W A S D to walk · Shift to move faster · Q / E height</>:<><b>EXPLORE IN 3D</b> Left-drag to orbit · Right-drag to pan · Scroll to zoom · Click a building to inspect</>}</div>
      {hasPanel&&<div className="workspace-host" key={workspace}>
        <button className="workspace-close" onClick={closePanel} aria-label="Close workspace">×</button>
        {workspace==='medical'&&<OperationsPanel key={state.sim_id} state={state} selectedNode={selectedNode} onSelectNode={onSelect} onDispatch={sim.handleDispatch} onHelicopter={sim.handleHelicopter} onCenter={sim.handleCenter} onPlay={play} playing={playing} onTogglePlaying={togglePlay} onStep={sim.handleStep} busy={busy} onClose={closePanel}/>}
        {workspace==='routes'&&<RouteLab state={state} selectedNode={selectedNode} onPaths={setRoutePaths} onClose={closePanel}/>}
        {workspace==='police'&&<PolicePanel key={state.sim_id} police={state.police} fleet={state.fleet} air={state.air_rescue} selectedNode={selectedNode} graph={sim.graph} onAction={sim.handlePolice} onHelicopter={sim.handleHelicopter} busy={busy} complete={state.is_complete} onPlay={play} onPause={()=>setPlaying(false)} onRestart={restart}/>}
        {workspace==='events'&&<CityEventsPanel events={state.city_events} busy={busy} onChange={sim.handleCityEvents} onPlay={play}/>}
        {(workspace==='metrics'||workspace==='diagnostics')&&<DiagnosticsPanel key={`${state.sim_id}-${workspace}`} mode={workspace} state={state} connected={sim.connected} onRefresh={sim.loadData} onClose={closePanel}/>}
        {workspace==='disasters'&&<DisasterPanel state={state} graph={sim.graph} busy={busy} mode={disasterMode} onMode={setDisasterMode} center={disasterCenter} centerLabel={disasterCenterLabel} onCenter={label=>{setDisasterCenterLabel(label);setDisasterCenter(sim.graph.nodes.find(n=>n.label===label)?.id??null);}} intensity={gateIntensity} onIntensity={setGateIntensity} preview={gatePreview} road={selectedRoad} onRoadSelect={setSelectedRoad} onRoad={sim.handleRoad} onGate={sim.handleGate} onClear={sim.handleClearGates}/>}
        {['city','ambulance','heatmap'].includes(workspace)&&<LeftPanel workspace={workspace} stats={stats} onOptimization={sim.handleOptimization} viewToggles={viewToggles} onToggleView={toggleLayer} onStart={restart} onStep={sim.handleStep} starting={sim.starting} stepping={sim.acting} simSpeed={simSpeed} onSpeedChange={setSimSpeed} placementMode={placementMode} onPlacementModeChange={setPlacementMode} roadMode={roadMode} onRoadModeChange={setRoadMode} gatesNodeLabel={gatesNodeLabel} onGatesNodeChange={setGatesNodeLabel} algoMode={algoMode} onAlgoModeChange={setAlgoMode} onResetView={resetView} quality={quality} onQualityChange={setQuality}/>}
        {workspace==='ambulance'&&<FleetAnalytics key={state.sim_id} state={state} targetLabel={gatesNodeLabel} onSelect={onSelect}/>}
      </div>}
      {selectedNode!=null&&<RightPanel selectedNode={selectedNode} graph={sim.graph} state={state} stats={stats} onClose={()=>setSelectedNode(null)}/>}
      {selectedRoadData&&!godMode&&<section className="road-inspector" aria-label="Road inspector"><button className="workspace-close" aria-label="Close road inspector" onClick={()=>setSelectedRoad(null)}>×</button><span className="eyebrow">ROAD SEGMENT</span><h2>{nodeLabel(selectedRoad[0])} — {nodeLabel(selectedRoad[1])}</h2><p>Base cost: {selectedRoadData.cost}</p><p>Normal traffic: {selectedRoadData.blocked||selectedRoadData.temporarily_blocked?'Closed':'Open'}</p><p>Ambulances: {selectedRoadData.blocked?'Closed':'Open'}</p><button onClick={()=>navigate('disasters')}>Manage road restrictions</button></section>}
      {selectedNode==null&&<div className="activity-card"><span className="eyebrow">CITY ACTIVITY</span>{[...stats.events].slice(-2).reverse().map((e,i)=><p key={i}><i/>{e.message}</p>)}<button onClick={()=>navigate('metrics')}>View event history ↗</button></div>}
      {state.air_rescue?.relocation_required&&<div className="city-alert" role="alert"><strong>Assistant required: helicopter helipad is inside Gate of Death.</strong><p>{state.air_rescue.relocation?.reason}</p><button disabled={busy||!state.air_rescue.relocation?.can_relocate} onClick={async()=>{if(await sim.handleHelicopter('relocate'))play();}}>Relocate helicopter</button></div>}
      {state.fleet.some(u=>u.status==='OUT_OF_SERVICE')&&<div className="fleet-warning" role="status">Out of service — Gate of Death: {state.fleet.filter(u=>u.status==='OUT_OF_SERVICE').map(u=>u.id).join(', ')}</div>}
      {(sim.error||notice||sim.message)&&<div className="city-notice" role={sim.error?'alert':'status'}>{String(sim.error||notice||sim.message)}<button onClick={()=>{sim.clearError();sim.clearMessage();setNotice('');}}>Dismiss</button></div>}
      {dashOpen&&<HealthDashboard stats={stats} onClose={()=>setDashOpen(false)}/>}
    </main>
  </div>;
}
