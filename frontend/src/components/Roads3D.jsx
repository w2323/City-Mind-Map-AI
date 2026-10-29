import {memo,useMemo,useRef,useLayoutEffect} from 'react';
import {useFrame} from '@react-three/fiber';
import * as THREE from 'three';
import {InstanceBatch} from './CityEnvironment';
import {signalPhase,advanceTraffic} from '../engine/trafficSignals';

const body=new THREE.BoxGeometry(1,.35,.48);
const cabin=new THREE.BoxGeometry(.5,.25,.42);

function Traffic({edges,nodes,spacing,speed=1,junctions}) {
  const bodies=useRef(),cabins=useRef();
  const progress=useRef(new Map());
  const signals=useMemo(()=>new Set(junctions.map(n=>n.id)),[junctions]);
  const cars=useMemo(()=>edges.filter(e=>!e.blocked&&!e.temporarily_blocked&&!e.candidate).filter((_,i)=>i%3===0).map((e,i)=>({a:nodes[e.nodeA],b:nodes[e.nodeB],key:`${e.nodeA}-${e.nodeB}`,phase:(i*.618)%1})),[edges,nodes]);
  const dummy=useMemo(()=>new THREE.Object3D(),[]);
  useLayoutEffect(()=>{
    const color=new THREE.Color();cars.forEach((_,i)=>bodies.current?.setColorAt(i,color.set(['#d2c2a6','#507986','#ced4d2','#ae6555','#6a777c'][i%5])));
    if(bodies.current?.instanceColor)bodies.current.instanceColor.needsUpdate=true;
  },[cars]);
  useFrame(({clock},delta)=>{
    if(!bodies.current||!cabins.current)return;
    cars.forEach((car,i)=>{
      if(!car.a||!car.b)return;
      const dx=(car.b.col-car.a.col)*spacing,dz=(car.b.row-car.a.row)*spacing;
      const previous=progress.current.get(car.key)??car.phase;
      const axis=Math.abs(dx)>=Math.abs(dz)?'horizontal':'vertical';
      const light=signals.has(car.b.id)?signalPhase(clock.elapsedTime,car.b.id)[axis]:'green';
      const t=advanceTraffic(previous,delta,speed,light);progress.current.set(car.key,t);
      const length=Math.hypot(dx,dz)||1;
      dummy.position.set(car.a.col*spacing+dx*t-dz/length*.38,.45,car.a.row*spacing+dz*t+dx/length*.38);
      dummy.rotation.set(0,-Math.atan2(dz,dx),0);dummy.scale.set(1,1,1);dummy.updateMatrix();bodies.current.setMatrixAt(i,dummy.matrix);
      dummy.position.y=.73;dummy.updateMatrix();cabins.current.setMatrixAt(i,dummy.matrix);
    });
    bodies.current.instanceMatrix.needsUpdate=true;cabins.current.instanceMatrix.needsUpdate=true;
  });
  if(!cars.length)return null;
  return <group><instancedMesh ref={bodies} args={[body,null,cars.length]} frustumCulled={false}><meshStandardMaterial roughness={.6}/></instancedMesh><instancedMesh ref={cabins} args={[cabin,null,cars.length]} frustumCulled={false}><meshStandardMaterial color="#344b56" roughness={.3}/></instancedMesh></group>;
}

export const Roads3D=memo(function Roads3D({edges,nodes,spacing=8,routeSet,onSelectRoad,selectedRoad,traffic=true,speed=1,junctions=[]}) {
  const batches=useMemo(()=>{
    const roads=[],paint=[],junctions=[];
    for(const n of Object.values(nodes))junctions.push({p:[n.col*spacing,.035,n.row*spacing],s:[2.6,.08,2.6],c:'#53616a'});
    edges.forEach((e,i)=>{
      const a=nodes[e.nodeA],b=nodes[e.nodeB];if(!a||!b)return;
      const dx=(b.col-a.col)*spacing,dz=(b.row-a.row)*spacing,length=Math.hypot(dx,dz),r=-Math.atan2(dz,dx);
      const key=`${Math.min(e.nodeA,e.nodeB)}_${Math.max(e.nodeA,e.nodeB)}`;
      let color=e.candidate?'#8b918a':e.blocked?'#a65b50':e.temporarily_blocked?'#b39353':routeSet?.has(key)?'#4f8999':'#53616a';
      if(selectedRoad&&key===`${Math.min(...selectedRoad)}_${Math.max(...selectedRoad)}`)color='#48d6c2';
      roads.push({p:[(a.col+b.col)*spacing/2,.035,(a.row+b.row)*spacing/2],s:[length,.08,e.candidate?.55:2.4],r,c:color,node:i});
      if(!e.candidate)for(let j=1;j<6;j++)paint.push({p:[a.col*spacing+dx*j/6,.085,a.row*spacing+dz*j/6],s:[.45,.012,.055],r,c:e.blocked?'#f5b3a0':'#c4c2ad'});
    });
    return {roads,paint,junctions};
  },[edges,nodes,spacing,routeSet,selectedRoad]);
  return <group>
    <InstanceBatch items={batches.junctions}/>
    <InstanceBatch items={batches.roads} onSelect={onSelectRoad?i=>onSelectRoad(edges[i]):undefined}/>
    <InstanceBatch items={batches.paint}/>
    {traffic&&<Traffic edges={edges} nodes={nodes} spacing={spacing} speed={speed} junctions={junctions}/>}
  </group>;
});
