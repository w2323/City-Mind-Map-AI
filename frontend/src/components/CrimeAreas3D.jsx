import {Text} from '@react-three/drei';

export default function CrimeAreas3D({areas=[],nodes,spacing}) {
  return <group>
    {areas.map(area=>{
      const node=nodes[area.node_id];
      if(!node)return null;
      const radius=area.radius*spacing;
      const strength=Math.max(0,Math.min(1,area.peak_score/100));
      const color=area.peak_score>=60?'#ff4757':'#ff8c42';
      return <group key={area.report_id} position={[node.col*spacing,.12,node.row*spacing]}>
        <mesh rotation={[-Math.PI/2,0,0]}>
          <circleGeometry args={[radius,64]} />
          <meshBasicMaterial color={color} transparent opacity={.05*strength} depthWrite={false} />
        </mesh>
        <mesh rotation={[-Math.PI/2,0,0]} position={[0,.01,0]}>
          <ringGeometry args={[Math.max(0,radius-.13),radius+.13,64]} />
          <meshBasicMaterial color={color} transparent opacity={.8*strength} depthWrite={false} />
        </mesh>
        <Text position={[0,.04,-radius-1.2]} rotation={[-Math.PI/2,0,0]} fontSize={1.1} color={color}>
          Sector {area.label} / {area.radius} units
        </Text>
      </group>;
    })}
  </group>;
}
