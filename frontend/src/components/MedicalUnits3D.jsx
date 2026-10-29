import {useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import {Line,Text} from '@react-three/drei';
import {buildingHeight,plotPosition,PLOT_OFFSET} from '../engine/cityGeometry';

function Ambulance({unit,nodes,spacing}) {
  const ref=useRef();
  const n=nodes[unit.position];
  const initial=useRef([n?.col*spacing || 0,.7,n?.row*spacing || 0]);
  useFrame((_,dt)=>{
    if(ref.current && n) {
      const blend=1-Math.exp(-10*dt);
      const dx=n.col*spacing-ref.current.position.x,dz=n.row*spacing-ref.current.position.z;
      if(Math.abs(dx)+Math.abs(dz)>.04)ref.current.rotation.y=-Math.atan2(dz,dx);
      ref.current.position.x+=(n.col*spacing-ref.current.position.x)*blend;
      ref.current.position.z+=(n.row*spacing-ref.current.position.z)*blend;
    }
  });
  if(!n)return null;
  const off=unit.status==='OUT_OF_SERVICE';
  return <group ref={ref} position={initial.current} scale={.6}>
    <mesh><boxGeometry args={[3,1.6,1.8]} /><meshStandardMaterial color={off?'#64748b':'#fff'} /></mesh>
    <Text position={[0,1,0]} rotation={[-Math.PI/2,0,0]} fontSize={1.5} color="#ef4444">+</Text>
    <Text position={[0,2.5,0]} rotation={[-Math.PI/2,0,0]} fontSize={1} color={off?'#f87171':'#38bdf8'}>{unit.id}{off?' OFF':''}</Text>
  </group>;
}

function Helicopter({air,spacing,nodes}) {
  const body=useRef(),rotor=useRef();
  const height=air.landed_node!=null?buildingHeight(nodes[air.landed_node])+1.4:16;
  const initial=useRef([air.position[1]*spacing+PLOT_OFFSET,height,air.position[0]*spacing+PLOT_OFFSET]);
  useFrame((_,dt)=>{
    if(!body.current)return;
    const x=air.position[1]*spacing+PLOT_OFFSET,z=air.position[0]*spacing+PLOT_OFFSET;
    const dx=x-body.current.position.x,dz=z-body.current.position.z;
    const blend=1-Math.exp(-10*dt);
    body.current.position.x+=dx*blend;body.current.position.z+=dz*blend;
    body.current.position.y+=(height-body.current.position.y)*blend;
    if(Math.abs(dx)+Math.abs(dz)>.05)body.current.rotation.y=Math.atan2(dx,dz);
    if(rotor.current && air.landed_node==null)rotor.current.rotation.y+=dt*28;
  });
  return <group ref={body} position={initial.current}>
    <mesh><boxGeometry args={[2.5,1.5,4]} /><meshStandardMaterial color="#c4b5fd" /></mesh>
    <mesh position={[0,0,-3]}><boxGeometry args={[.5,.5,3]} /><meshStandardMaterial color="#8b5cf6" /></mesh>
    <mesh ref={rotor} position={[0,1,0]}><boxGeometry args={[8,.2,.4]} /><meshBasicMaterial color="#a78bfa" /></mesh>
  </group>;
}

export default function MedicalUnits3D({fleet=[],air={},nodes,spacing,trails=true}) {
  const target=nodes[air.target];
  return <group>
    {fleet.map(u=><Ambulance key={u.id} unit={u} nodes={nodes} spacing={spacing} />)}
    {trails&&fleet.filter(u=>u.status!=='OUT_OF_SERVICE' && u.path?.length>1).map(u=><Line key={u.id} points={u.path.map(id=>[nodes[id].col*spacing,.2,nodes[id].row*spacing])} color="#38bdf8" lineWidth={3} />)}
    {(air.landing_sites || []).map(site=>{
      const n=nodes[site.node_id];if(!n)return null;
      const [x,z]=plotPosition(n);
      return <group key={site.node_id} position={[x,buildingHeight(n),z]}>
        <mesh rotation={[-Math.PI/2,0,0]}><ringGeometry args={[1.7,2,24]} /><meshBasicMaterial color={site.available?'#c4b5fd':'#f87171'} /></mesh>
        <Text position={[0,.05,0]} rotation={[-Math.PI/2,0,0]} fontSize={1.5} color={site.available?'#c4b5fd':'#f87171'}>H</Text>
      </group>;
    })}
    {air.position && <Helicopter air={air} spacing={spacing} nodes={nodes} />}
    {trails&&target && air.position && <Line points={[[air.position[1]*spacing+PLOT_OFFSET,16,air.position[0]*spacing+PLOT_OFFSET],[target.col*spacing+PLOT_OFFSET,16,target.row*spacing+PLOT_OFFSET]]} color="#c4b5fd" lineWidth={2} />}
  </group>;
}
