import {memo,useMemo,useEffect} from 'react';
import * as THREE from 'three';
const EMPTY=[];

// One atlas and one draw call for all grid references, instead of 225 text meshes.
export default memo(function SectorLabels({nodes=EMPTY,ids=false,costs=false,edges=EMPTY,entries:customEntries,axes=false}) {
  const resource=useMemo(()=>{
    const entries=customEntries||(costs?edges.map(e=>({x:(nodes.find(n=>n.id===e.nodeA)?.col+nodes.find(n=>n.id===e.nodeB)?.col)*4,z:(nodes.find(n=>n.id===e.nodeA)?.row+nodes.find(n=>n.id===e.nodeB)?.row)*4,text:String(e.cost)})):nodes.map(n=>({x:n.col*8,z:n.row*8,text:ids?String(n.id):n.label})));
    const grid=entries.length>256?32:16;
    const canvas=document.createElement('canvas');canvas.width=grid*64;canvas.height=grid*64;
    const ctx=canvas.getContext('2d');ctx.font=`bold ${axes?40:costs?28:32}px system-ui`;ctx.textAlign='center';ctx.textBaseline='middle';
    const positions=[],uv=[],indices=[];
    entries.forEach((e,i)=>{
      const col=i%grid,row=Math.floor(i/grid);ctx.fillStyle=axes?'#f4f8eef5':'#18313ff0';ctx.fillRect(col*64+2,row*64+12,60,40);ctx.fillStyle=axes?'#274c40':'#f2f6e9';ctx.fillText(e.text,col*64+32,row*64+32,56);
      const base=i*4,y=costs?.19:.16,w=axes?2.4:costs?1:1.8,h=axes?1.8:costs?.7:1.25;
      positions.push(e.x-w,y,e.z-h,e.x+w,y,e.z-h,e.x+w,y,e.z+h,e.x-w,y,e.z+h);
      const u=(col*64+2)/(grid*64),v=1-(row*64+12)/(grid*64),uw=60/(grid*64),vh=40/(grid*64);uv.push(u,v,u+uw,v,u+uw,v-vh,u,v-vh);indices.push(base,base+2,base+1,base,base+3,base+2);
    });
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geometry.setIndex(indices);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    return {geometry,texture};
  },[nodes,ids,costs,edges,customEntries,axes]);
  useEffect(()=>()=>{resource.geometry.dispose();resource.texture.dispose();},[resource]);
  return <mesh geometry={resource.geometry} renderOrder={20}><meshBasicMaterial map={resource.texture} transparent depthWrite={false} side={THREE.DoubleSide} fog={false}/></mesh>;
});
