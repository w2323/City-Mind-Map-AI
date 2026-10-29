import {memo,useMemo,useRef,useLayoutEffect} from 'react';
import {useFrame} from '@react-three/fiber';
import * as THREE from 'three';
import {InstanceBatch} from './CityEnvironment';
import {signalPhase} from '../engine/trafficSignals';
const bulb=new THREE.SphereGeometry(.085,8,6);

export default memo(function TrafficSignals3D({junctions,telemetry}) {
  const lights=useRef(),previousPhase=useRef('');
  const data=useMemo(()=>{
    const fixtures=[],crossings=[],bulbs=[];
    for(const n of junctions) {
      const x=n.col*8,z=n.row*8;
      for(const [axis,dx,dz] of [['horizontal',1.4,-1.4],['vertical',-1.4,1.4]]) {
        fixtures.push({p:[x+dx,1.25,z+dz],s:[.07,2.5,.07],c:'#455658'});
        fixtures.push({p:[x+dx,2.6,z+dz],s:axis==='horizontal'?[.18,.7,.28]:[.28,.7,.18],c:'#233c3c'});
        for(let i=0;i<3;i++)bulbs.push({node:n.id,axis,color:['red','amber','green'][i],p:axis==='horizontal'?[x+dx-.11,2.82-i*.21,z+dz]:[x+dx,2.82-i*.21,z+dz-.11]});
      }
      for(let i=0;i<5;i++) {
        crossings.push({p:[x-1+i*.5,.09,z-1.65],s:[.26,.02,.6],c:'#dee0c9'});
        crossings.push({p:[x-1.65,.09,z-1+i*.5],s:[.6,.02,.26],c:'#dee0c9'});
      }
    }
    return {fixtures,crossings,bulbs};
  },[junctions]);
  useLayoutEffect(()=>{
    if(!lights.current)return;const dummy=new THREE.Object3D();
    data.bulbs.forEach((item,i)=>{dummy.position.set(...item.p);dummy.updateMatrix();lights.current.setMatrixAt(i,dummy.matrix);});
    lights.current.instanceMatrix.needsUpdate=true;previousPhase.current='';
  },[data]);
  useFrame(({clock})=>{
    if(!lights.current)return;
    const key=Math.floor(clock.elapsedTime*2).toString();if(key===previousPhase.current)return;previousPhase.current=key;
    const color=new THREE.Color();
    const active={red:'#f47762',amber:'#ffd276',green:'#78e9a0'},inactive={red:'#633b32',amber:'#5c5133',green:'#335d42'};
    data.bulbs.forEach((item,i)=>lights.current.setColorAt(i,color.set(signalPhase(clock.elapsedTime,item.node)[item.axis]===item.color?active[item.color]:inactive[item.color])));
    if(lights.current.instanceColor)lights.current.instanceColor.needsUpdate=true;
    if(telemetry.current&&junctions[0])telemetry.current.dataset.signalPhase=JSON.stringify(signalPhase(clock.elapsedTime,junctions[0].id));
  });
  if(!junctions.length)return null;
  return <group><InstanceBatch items={data.fixtures}/><InstanceBatch items={data.crossings}/><instancedMesh ref={lights} args={[bulb,null,data.bulbs.length]} frustumCulled={false}><meshBasicMaterial/></instancedMesh></group>;
});
