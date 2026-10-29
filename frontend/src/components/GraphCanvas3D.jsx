import {memo,useCallback,useMemo,useRef,useEffect} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {Line,Text} from '@react-three/drei';
import * as THREE from 'three';
import CityEnvironment,{InstanceBatch} from './CityEnvironment';
import CityCamera from './CityCamera';
import SectorLabels from './SectorLabels';
import {Roads3D} from './Roads3D';
import PoliceUnits3D from './PoliceUnits3D';
import MedicalUnits3D from './MedicalUnits3D';
import CrimeAreas3D from './CrimeAreas3D';
import {plotPosition} from '../engine/cityGeometry';
import {toDisplayNode,toDisplayAir,gridReferences,gridLetter} from '../engine/gridReferences';
import {signalJunctions} from '../engine/trafficSignals';
import TrafficSignals3D from './TrafficSignals3D';
const EMPTY=[];
function StaticShadows({signature}) {
  const {gl}=useThree();
  useEffect(()=>{gl.shadowMap.autoUpdate=false;gl.shadowMap.needsUpdate=true;},[gl,signature]);
  return null;
}

function Telemetry({element,performanceElement}) {
  const frames=useRef({count:0,time:0});
  useFrame(({gl,clock})=>{
    const sample=frames.current;sample.count++;
    if(clock.elapsedTime-sample.time<1)return;
    const fps=Math.round(sample.count/(clock.elapsedTime-sample.time));
    if(element.current){element.current.dataset.drawCalls=gl.info.render.calls;element.current.dataset.triangles=gl.info.render.triangles;}
    if(performanceElement.current)performanceElement.current.textContent=`${fps} FPS`;
    sample.time=clock.elapsedTime;sample.count=0;
  });
  return null;
}

const SceneLayers=memo(function SceneLayers({state,stats,nodes,viewToggles}) {
  const items=useMemo(()=>{
    const covered=new Set(stats?.coveredNodes),police=new Set((state.police?.units||[]).map(u=>u.position));
    return Object.values(nodes).flatMap(n=>{
      let c;
      if(viewToggles.heatmap)c=n.risk_level==='HIGH'?'#e56d5b':n.risk_level==='MEDIUM'?'#dfb95e':'#6eab89';
      else if(viewToggles.population)c=new THREE.Color().setHSL(.58-n.population/1000,.65,.5).getStyle();
      else if(viewToggles.policeCoverage&&police.has(n.id))c='#a79ae5';
      else if(viewToggles.coverage&&covered.has(n.id))c='#62a3c5';
      if(!c)return [];
      const [x,z]=plotPosition(n);return [{p:[x,.18,z],s:[5.4,.02,5.4],c}];
    });
  },[nodes,state.police,stats?.coveredNodes,viewToggles]);
  return <InstanceBatch items={items} emissive opacity={.45}/>;
});

export default memo(function GraphCanvas3D({graph,state,stats,viewToggles,simSpeed=1,onSelectNode,selectedNode,booted,resetTrigger,focusTrigger=0,cameraMode='orbit',quality='balanced',roadMode,gatesNodeId,gatesPaths=EMPTY,godMode,onSelectRoad,selectedRoad,disasterMode,disasterCenter,gateIntensity}) {
  const telemetry=useRef(),performanceElement=useRef(),selectRef=useRef(onSelectNode);selectRef.current=onSelectNode;
  const select=useCallback(id=>selectRef.current?.(id),[]);
  const staticKey=graph?.nodes?.map(n=>`${n.id}:${n.node_type}:${n.population}`).join('|');
  const cityNodes=useMemo(()=>graph?.nodes?.map(n=>toDisplayNode({id:n.id,row:n.row,col:n.col,node_type:n.node_type,population:n.population,label:n.label}))||EMPTY,[staticKey]);
  const nodes=useMemo(()=>Object.fromEntries((graph?.nodes||EMPTY).map(n=>[n.id,toDisplayNode(n)])),[graph?.nodes]);
  const air=useMemo(()=>toDisplayAir(state?.air_rescue),[state?.air_rescue]);
  const axes=useMemo(()=>gridReferences(graph?.grid_rows||15,graph?.grid_cols||15),[graph?.grid_rows,graph?.grid_cols]);
  const edges=godMode?stats?.edgeList||EMPTY:stats?.roadViews?.[roadMode]||stats?.edgeList||EMPTY;
  const junctions=useMemo(()=>viewToggles.signals!==false?signalJunctions(stats?.edgeList||EMPTY,nodes):EMPTY,[stats?.edgeList,nodes,viewToggles.signals]);
  const routeKey=(state?.router?.current_path||EMPTY).join(',');
  const routeSet=useMemo(()=>{
    const set=new Set(),path=state?.router?.current_path||EMPTY;
    for(let i=1;i<path.length;i++)set.add(`${Math.min(path[i-1],path[i])}_${Math.max(path[i-1],path[i])}`);
    return set;
  },[routeKey]);
  const rows=graph?.grid_cols||15,cols=graph?.grid_rows||15,centerX=(cols-1)*4,centerZ=(rows-1)*4;
  const dpr=quality==='economy'?.75:quality==='high'?Math.min(window.devicePixelRatio,1.5):1;
  if(!booted||!graph)return null;
  const selected=nodes[selectedNode],target=nodes[gatesNodeId];
  const zones=[...(state.disasters?.gates||EMPTY),...(godMode&&disasterMode==='gate'&&disasterCenter!=null?[{id:'preview',node_id:disasterCenter,radius:state.disasters?.levels?.find(l=>l.intensity===gateIntensity)?.radius||0}]:[])];
  return <div className="city-viewport" data-testid="city-viewport" data-camera-mode={cameraMode} data-grid-columns={`1–${cols}`} data-grid-rows={`A–${gridLetter(rows-1)}`} data-signal-count={junctions.length} ref={telemetry}>
    <Canvas dpr={dpr} shadows={quality!=='economy'?'percentage':false} gl={{antialias:quality!=='economy',powerPreference:'high-performance'}} camera={{position:[centerX+110,110,centerZ+140],fov:50,near:.1,far:450}}>
      <color attach="background" args={['#b6cbd2']}/><fog attach="fog" args={['#b6cbd2',120,320]}/>
      <hemisphereLight args={['#d5e8f5','#81816b',2.2]}/>
      <directionalLight position={[-60,140,40]} intensity={2.6} color="#ffe2b6" castShadow shadow-mapSize={[quality==='high'?2048:1024,quality==='high'?2048:1024]} shadow-camera-left={-150} shadow-camera-right={150} shadow-camera-top={150} shadow-camera-bottom={-150} shadow-camera-far={400} shadow-bias={-.0003} shadow-normalBias={.035}/>
      <StaticShadows signature={`${staticKey}:${quality}`}/>
      <CityCamera mode={cameraMode} centerX={centerX} centerZ={centerZ} resetTrigger={resetTrigger} focusTrigger={focusTrigger} selected={selected} telemetryRef={telemetry} nodes={cityNodes}/>
      <Telemetry element={telemetry} performanceElement={performanceElement}/>
      <mesh rotation={[-Math.PI/2,0,0]} position={[centerX,-.035,centerZ]} receiveShadow><planeGeometry args={[400,400]}/><meshStandardMaterial color="#92a18d" roughness={1}/></mesh>
      <CityEnvironment nodes={cityNodes} onSelect={select}/>
      {viewToggles.roads!==false&&<Roads3D edges={edges} nodes={nodes} routeSet={routeSet} onSelectRoad={onSelectRoad} selectedRoad={selectedRoad} traffic={viewToggles.traffic!==false&&quality!=='economy'} speed={simSpeed} junctions={junctions}/>}
      {viewToggles.roads!==false&&<TrafficSignals3D junctions={junctions} telemetry={telemetry}/>}
      <SceneLayers nodes={nodes} state={state} stats={stats} viewToggles={viewToggles}/>
      <SectorLabels entries={axes} axes/>
      {(viewToggles.labels||viewToggles.ids)&&<SectorLabels nodes={cityNodes} ids={viewToggles.ids}/>}
      {viewToggles.costs&&<SectorLabels nodes={cityNodes} costs edges={edges}/>}
      <PoliceUnits3D key={state.sim_id} police={state.police} nodes={nodes} spacing={8} trails={viewToggles.trails}/>
      <MedicalUnits3D key={`medical-${state.sim_id}`} fleet={state.fleet} air={air} nodes={nodes} spacing={8} trails={viewToggles.trails}/>
      {viewToggles.heatmap&&<CrimeAreas3D areas={state.police?.crime_areas} nodes={nodes} spacing={8}/>}
      {gatesPaths.map((route,i)=>{const points=route.path.filter(id=>nodes[id]).map(id=>[nodes[id].col*8,.35,nodes[id].row*8]);return points.length>1?<Line key={i} points={points} color={route.color} lineWidth={3}/>:null;})}
      {zones.map(zone=>{const n=nodes[zone.node_id];return n&&zone.radius?<mesh key={zone.id} position={[n.col*8,.16,n.row*8]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[zone.radius*8-.2,zone.radius*8+.2,64]}/><meshBasicMaterial color="#9b61b9" side={THREE.DoubleSide}/></mesh>:null;})}
      {(state.emergencies||EMPTY).filter(e=>!['RESOLVED','ABORTED'].includes(e.status)).map(e=>{
        const n=nodes[e.node_id];return n?<group key={e.id} position={[n.col*8,3,n.row*8]}><mesh onClick={()=>select(n.id)}><octahedronGeometry args={[.7]}/><meshBasicMaterial color="#f26649"/></mesh><Text position={[0,1.5,0]} fontSize={.7} color="#512f28">{e.id}</Text></group>:null;
      })}
      {viewToggles.coverage&&(state.medical_network?.unreachable_nodes||EMPTY).map(id=>{const n=nodes[id];return n?<mesh key={id} position={[n.col*8,.16,n.row*8]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[1.2,1.4,16]}/><meshBasicMaterial color="#ef7e43"/></mesh>:null;})}
      {(selected||target)&&[selected,target].filter(Boolean).map((n,i)=>{
        const [x,z]=plotPosition(n);return <group key={i} position={[x,.2,z]}><mesh rotation={[-Math.PI/2,0,0]}><ringGeometry args={[2.8,2.95,4,1,Math.PI/4]}/><meshBasicMaterial color="#37bfae" side={THREE.DoubleSide}/></mesh><Text position={[0,12,0]} fontSize={1.2} color="#203c45">{n.label}</Text></group>;
      })}
    </Canvas>
    <span className="scene-performance" ref={performanceElement} aria-label="Scene frame rate">Measuring…</span>
    <span className="grid-reference-key" aria-label="Grid references">Columns 1–{cols} → · Rows A–{gridLetter(rows-1)} ↓</span>
  </div>;
});
