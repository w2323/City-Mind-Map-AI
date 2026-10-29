import {useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import {Text,Line} from '@react-three/drei';

function PatrolCar({unit,nodes,spacing}) {
  const ref=useRef();
  const node=nodes[unit.position];
  const initial=useRef([node ? node.col*spacing : 0,.55,node ? node.row*spacing : 0]);
  useFrame((_,dt)=>{
    if(ref.current && node) {
      const blend=1-Math.exp(-10*dt);
      const dx=node.col*spacing-ref.current.position.x,dz=node.row*spacing-ref.current.position.z;
      if(Math.abs(dx)+Math.abs(dz)>.04)ref.current.rotation.y=-Math.atan2(dz,dx);
      ref.current.position.x+=(node.col*spacing-ref.current.position.x)*blend;
      ref.current.position.z+=(node.row*spacing-ref.current.position.z)*blend;
    }
  });
  if(!node)return null;
  return <group ref={ref} position={initial.current} scale={.55}>
    <mesh><boxGeometry args={[2.8,1.0,1.5]} /><meshStandardMaterial color="#dce6fa" /></mesh>
    <mesh position={[0,.6,0]}><boxGeometry args={[1.4,.6,1.3]} /><meshStandardMaterial color="#4f46e5" /></mesh>
    <mesh position={[-.3,1,0]}><boxGeometry args={[.5,.25,.6]} /><meshBasicMaterial color="#ef4444" /></mesh>
    <mesh position={[.3,1,0]}><boxGeometry args={[.5,.25,.6]} /><meshBasicMaterial color="#22d3ee" /></mesh>
  </group>;
}

export default function PoliceUnits3D({police,nodes,spacing,trails=true}) {
  if(!police)return null;
  return <group>
    {(police.stations || []).map(s=>{
      const node=nodes[s.node_id];if(!node)return null;
      return <group key={s.id} position={[node.col*spacing,0,node.row*spacing]}>
        <mesh position={[2.2,1.1,2.2]}><boxGeometry args={[1.5,2.2,1.5]} /><meshStandardMaterial color="#4f46e5" /></mesh>
        <mesh position={[2.2,2.35,2.2]}><boxGeometry args={[1.8,.3,1.8]} /><meshStandardMaterial color="#c4b5fd" /></mesh>
        <Text position={[0,5,0]} rotation={[-Math.PI/2,0,0]} fontSize={2} color="#a78bfa">{s.id}</Text>
      </group>;
    })}
    {(police.units || []).map(unit=><PatrolCar key={unit.id} unit={unit} nodes={nodes} spacing={spacing} />)}
    {trails&&(police.units || []).filter(u=>['RESPONDING','PATROLLING'].includes(u.status) && u.path?.length>1).map(u=><Line key={u.id} points={u.path.map(id=>[nodes[id].col*spacing,.2,nodes[id].row*spacing])} color="#a78bfa" lineWidth={u.status==='RESPONDING'?2:1} />)}
    {(police.reports || []).filter(r=>r.status!=='RESOLVED').map(r=>{
      const node=nodes[r.node_id];if(!node)return null;
      return <Text key={r.id} position={[node.col*spacing,7,node.row*spacing]} rotation={[-Math.PI/2,0,0]} fontSize={2} color="#fb7185">{r.id}</Text>;
    })}
  </group>;
}
