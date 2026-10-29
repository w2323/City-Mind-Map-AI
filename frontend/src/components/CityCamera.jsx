import {useEffect,useMemo,useRef} from 'react';
import {useFrame,useThree} from '@react-three/fiber';
import {OrbitControls} from '@react-three/drei';
import * as THREE from 'three';
import {PLOT_OFFSET} from '../engine/cityGeometry';

export default function CityCamera({mode,centerX,centerZ,resetTrigger,focusTrigger,selected,telemetryRef,nodes}) {
  const control=useRef(),keys=useRef(new Set()),drag=useRef(null),yaw=useRef(0),pitch=useRef(0);
  const {camera,gl}=useThree();
  const animated=useRef(false),position=useRef(new THREE.Vector3()),target=useRef(new THREE.Vector3());
  const vectors=useMemo(()=>({forward:new THREE.Vector3(),right:new THREE.Vector3(),movement:new THREE.Vector3(),up:new THREE.Vector3(0,1,0),euler:new THREE.Euler(0,0,0,'YXZ')}),[]);
  const center=useMemo(()=>[centerX,0,centerZ],[centerX,centerZ]);
  useEffect(()=>{
    if(!control.current)return;
    const useSelection=selected&&(focusTrigger||mode==='street');
    const x=useSelection?selected.col*8:centerX,z=useSelection?selected.row*8:centerZ;
    camera.up.set(0,1,0);
    if(mode==='street') {
      camera.position.set(x,1.8,z+2);yaw.current=0;pitch.current=0;camera.rotation.set(0,0,0);animated.current=false;
    } else if(mode==='map') {
      // Flush residual orbit damping, then align the coordinate grid exactly.
      const controls=control.current;
      controls.enableDamping=false;controls.update();
      camera.position.set(x,190,z+.05);controls.target.set(x,0,z);controls.update();
      controls.enableDamping=true;animated.current=false;
    } else {
      if(focusTrigger&&selected)position.current.set(x+16,15,z+20);
      else position.current.set(centerX+110,110,centerZ+140);
      target.current.set(x,0,z);animated.current=true;
    }
    // Selection alone never moves the camera; Focus is an explicit action.
  },[mode,resetTrigger,focusTrigger,centerX,centerZ,camera]);
  useEffect(()=>{
    const canvas=gl.domElement;
    canvas.tabIndex=0;
    const typing=event=>event.target instanceof HTMLElement&&!!event.target.closest('input,textarea,select,[contenteditable="true"]');
    const down=e=>{if(typing(e))return;if(['KeyW','KeyA','KeyS','KeyD','KeyQ','KeyE','ShiftLeft','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code)){keys.current.add(e.code);if(mode==='street')e.preventDefault();}};
    const up=e=>keys.current.delete(e.code);
    const clear=()=>{keys.current.clear();drag.current=null;};
    const stopDrag=()=>{drag.current=null;};
    const pointerDown=e=>{if(mode==='street'&&e.button===0){drag.current={x:e.clientX,y:e.clientY};canvas.focus({preventScroll:true});}};
    const pointerMove=e=>{if(!drag.current||mode!=='street')return;yaw.current-=(e.clientX-drag.current.x)*.004;pitch.current=THREE.MathUtils.clamp(pitch.current-(e.clientY-drag.current.y)*.004,-1.25,1.25);drag.current={x:e.clientX,y:e.clientY};};
    window.addEventListener('keydown',down);window.addEventListener('keyup',up);window.addEventListener('blur',clear);
    canvas.addEventListener('pointerdown',pointerDown);window.addEventListener('pointermove',pointerMove);window.addEventListener('pointerup',stopDrag);
    return ()=>{clear();window.removeEventListener('keydown',down);window.removeEventListener('keyup',up);window.removeEventListener('blur',clear);canvas.removeEventListener('pointerdown',pointerDown);window.removeEventListener('pointermove',pointerMove);window.removeEventListener('pointerup',stopDrag);};
  },[mode,gl]);
  useFrame((_,delta)=>{
    const dt=Math.min(delta,.05),controls=control.current;
    if(mode==='street') {
      const k=keys.current;
      yaw.current+=((k.has('ArrowLeft')?1:0)-(k.has('ArrowRight')?1:0))*dt;
      pitch.current=THREE.MathUtils.clamp(pitch.current+((k.has('ArrowUp')?1:0)-(k.has('ArrowDown')?1:0))*dt,-1.25,1.25);
      vectors.euler.set(pitch.current,yaw.current,0);camera.quaternion.setFromEuler(vectors.euler);
      camera.getWorldDirection(vectors.forward);vectors.forward.y=0;vectors.forward.normalize();vectors.right.crossVectors(vectors.forward,vectors.up);
      vectors.movement.set(0,0,0).addScaledVector(vectors.forward,(k.has('KeyW')?1:0)-(k.has('KeyS')?1:0)).addScaledVector(vectors.right,(k.has('KeyD')?1:0)-(k.has('KeyA')?1:0));
      if(vectors.movement.lengthSq()) {
        vectors.movement.normalize().multiplyScalar(dt*(k.has('ShiftLeft')?14:5));
        const walkable=(x,z)=>!nodes.some(n=>n.node_type!=='EMPTY'&&Math.abs(x-n.col*8-PLOT_OFFSET)<2.55&&Math.abs(z-n.row*8-PLOT_OFFSET)<2.55&&camera.position.y<12);
        if(walkable(camera.position.x+vectors.movement.x,camera.position.z))camera.position.x+=vectors.movement.x;
        if(walkable(camera.position.x,camera.position.z+vectors.movement.z))camera.position.z+=vectors.movement.z;
      }
      camera.position.y=THREE.MathUtils.clamp(camera.position.y+((k.has('KeyE')?1:0)-(k.has('KeyQ')?1:0))*dt*4,1.2,50);
      camera.position.x=THREE.MathUtils.clamp(camera.position.x,-15,centerX*2+20);camera.position.z=THREE.MathUtils.clamp(camera.position.z,-15,centerZ*2+20);
    } else if(controls&&animated.current) {
      const blend=1-Math.exp(-5*dt);camera.position.lerp(position.current,blend);controls.target.lerp(target.current,blend);controls.update();
      if(camera.position.distanceToSquared(position.current)<.02)animated.current=false;
    }
    if(telemetryRef.current) {
      telemetryRef.current.dataset.cameraPosition=camera.position.toArray().map(n=>n.toFixed(2)).join(',');
      telemetryRef.current.dataset.cameraDirection=[camera.quaternion.x,camera.quaternion.y,camera.quaternion.z,camera.quaternion.w].map(n=>n.toFixed(3)).join(',');
    }
  });
  return <OrbitControls ref={control} makeDefault enabled={mode!=='street'} target={center} enableDamping dampingFactor={.12} minDistance={2} maxDistance={260} minPolarAngle={mode==='map'?.00001:.03} maxPolarAngle={Math.PI/2-.015} zoomSpeed={1.1} rotateSpeed={.65} screenSpacePanning={false} mouseButtons={{LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN}} touches={{ONE:THREE.TOUCH.ROTATE,TWO:THREE.TOUCH.DOLLY_PAN}} onStart={()=>{animated.current=false;}} />;
}
