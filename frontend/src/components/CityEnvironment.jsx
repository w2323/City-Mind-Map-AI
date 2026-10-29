import {memo,useMemo,useLayoutEffect,useRef} from 'react';
import * as THREE from 'three';
import {buildCity} from '../engine/cityGeometry';

const box=new THREE.BoxGeometry(1,1,1);
const canopy=new THREE.IcosahedronGeometry(.7,0);

export const InstanceBatch=memo(function InstanceBatch({items,geometry=box,onSelect,roughness=.86,metalness=0,emissive=false,opacity=1,castShadow=false}) {
  const ref=useRef();
  useLayoutEffect(()=>{
    const object=new THREE.Object3D(),color=new THREE.Color(),mesh=ref.current;
    if(!mesh)return;
    items.forEach((item,i)=>{
      object.position.set(...item.p);object.scale.set(...item.s);object.rotation.set(0,item.r || 0,0);object.updateMatrix();
      mesh.setMatrixAt(i,object.matrix);mesh.setColorAt(i,color.set(item.c));
    });
    mesh.instanceMatrix.needsUpdate=true;
    if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;
    mesh.computeBoundingSphere();
  },[items]);
  if(!items.length)return null;
  return <instancedMesh ref={ref} args={[geometry,null,items.length]} castShadow={castShadow} receiveShadow={!emissive} onClick={onSelect?e=>{
    if(e.delta>5)return;
    const id=items[e.instanceId]?.node;if(id!=null){e.stopPropagation();onSelect(id);}
  }:undefined}>
    {emissive?<meshBasicMaterial transparent={opacity<1} opacity={opacity} depthWrite={opacity===1} />:<meshStandardMaterial roughness={roughness} metalness={metalness} />}
  </instancedMesh>;
});

export default memo(function CityEnvironment({nodes,onSelect}) {
  const city=useMemo(()=>buildCity(nodes),[nodes]);
  return <group>
    {Object.entries(city).map(([key,items])=><InstanceBatch key={key} items={items} geometry={key==='leaves'?canopy:box} onSelect={['walls','grass','paving'].includes(key)?onSelect:undefined} roughness={key==='glass'?.28:.87} metalness={key==='glass'?.3:0} emissive={key==='lamps'} castShadow={['walls','roofs','leaves'].includes(key)} />)}
  </group>;
});
