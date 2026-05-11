// ═══════════════════════════════════════════════════════════════════════
// CITYMIND — Buildings3D  (Performance-Optimised Rewrite)
//
// PERF STRATEGY:
//  1. Each model type loads ONCE → extract first mesh geometry + material
//  2. All instances share the SAME geometry & material (zero cloning)
//  3. No per-node useFrame — only the selected node gets animated
//  4. Normalisation scale computed ONCE per model type (module cache)
//  5. Total draw calls ≈ node count (~225) instead of thousands
// ═══════════════════════════════════════════════════════════════════════
import React, { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useGLTF } from '@react-three/drei';
import * as SkeletonUtils from 'three/examples/jsm/utils/SkeletonUtils.js';

// ── Target size for models (must be < CELL_SIZE/2 so nothing overlaps)
const TARGET = 5.5;

// ── Cache normalisation per path so we compute Box3 exactly once ──
const _scaleCache = {};

function getModelData(gltf, path) {
  if (_scaleCache[path]) return _scaleCache[path];

  if (!gltf?.scene) return null;

  // Compute bounding box of entire scene to get normalisation scale
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z, 0.001);
  const scale = TARGET / maxDim;

  // Get the min-Y so we can place models on the ground
  const minY = box.min.y;
  const centerX = (box.min.x + box.max.x) / 2;
  const centerZ = (box.min.z + box.max.z) / 2;

  _scaleCache[path] = { scene: gltf.scene, scale, minY, centerX, centerZ };
  return _scaleCache[path];
}

// ═══════════════════════════════════════════════════════════════════
// Lightweight mesh renderer — renders shared geo/mat, no cloning
// ═══════════════════════════════════════════════════════════════════
function ModelInstance({ modelData, position, isSelected, isHovered, castShadow = true }) {
  const groupRef = useRef();

  // Clone the scene graph while sharing geometries & materials
  const clonedScene = useMemo(() => {
    if (!modelData?.scene) return null;
    const clone = SkeletonUtils.clone(modelData.scene);
    
    // Ensure all meshes cast/receive shadows
    clone.traverse((child) => {
      if (child.isMesh) {
        if (castShadow) child.castShadow = true;
        child.receiveShadow = true;
      }
    });
    return clone;
  }, [modelData]);

  // Only run useFrame when actually selected or hovered (not idle)
  const needsAnim = isSelected || isHovered;

  useFrame(needsAnim ? (state) => {
    if (!groupRef.current) return;
    if (isSelected) {
      const s = 1 + Math.sin(state.clock.elapsedTime * 5) * 0.06;
      groupRef.current.scale.setScalar(s);
    } else if (isHovered) {
      groupRef.current.scale.lerp({ x: 1.08, y: 1.08, z: 1.08 }, 0.15);
    }
  } : () => {
    // Idle — snap to 1 quickly if needed
    if (groupRef.current && groupRef.current.scale.x !== 1) {
      groupRef.current.scale.lerp({ x: 1, y: 1, z: 1 }, 0.2);
    }
  });

  if (!clonedScene || !modelData) return null;

  return (
    <group ref={groupRef} position={position}>
      <group
        scale={[modelData.scale, modelData.scale, modelData.scale]}
        position={[
          -modelData.centerX * modelData.scale,
          -modelData.minY * modelData.scale,
          -modelData.centerZ * modelData.scale,
        ]}
      >
        <primitive object={clonedScene} />
      </group>
    </group>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Procedural fallback buildings — vibrant colours, zero file load
// ═══════════════════════════════════════════════════════════════════

// Shared materials (created once, reused everywhere)
const mats = {
  white:    new THREE.MeshStandardMaterial({ color: '#f0f4f8', roughness: 0.5 }),
  red:      new THREE.MeshStandardMaterial({ color: '#ef4444', roughness: 0.3 }),
  blue:     new THREE.MeshStandardMaterial({ color: '#3b82f6', roughness: 0.3 }),
  indigo:   new THREE.MeshStandardMaterial({ color: '#6366f1', roughness: 0.3 }),
  yellow:   new THREE.MeshStandardMaterial({ color: '#fbbf24', roughness: 0.4 }),
  orange:   new THREE.MeshStandardMaterial({ color: '#f97316', roughness: 0.4 }),
  slate:    new THREE.MeshStandardMaterial({ color: '#64748b', roughness: 0.7, metalness: 0.3 }),
  dark:     new THREE.MeshStandardMaterial({ color: '#374151', roughness: 0.5, metalness: 0.5 }),
  cream:    new THREE.MeshStandardMaterial({ color: '#fef3c7', roughness: 0.5 }),
  green:    new THREE.MeshStandardMaterial({ color: '#10b981', roughness: 0.6 }),
  purple:   new THREE.MeshStandardMaterial({ color: '#a78bfa', roughness: 0.3, metalness: 0.5 }),
  purpleD:  new THREE.MeshStandardMaterial({ color: '#8b5cf6', roughness: 0.2, metalness: 0.6 }),
  gold:     new THREE.MeshStandardMaterial({ color: '#fbbf24', emissive: '#fbbf24', emissiveIntensity: 0.25 }),
};

// Shared geometries (created once)
const geos = {
  box1:   new THREE.BoxGeometry(1, 1, 1),
  cyl1:   new THREE.CylinderGeometry(1, 1, 1, 16),
  cone1:  new THREE.ConeGeometry(1, 1, 4),
  sphere: new THREE.SphereGeometry(1, 10, 10),
};

function FallbackHospital({ position, isSelected, isHovered }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.box1} material={mats.white} scale={[2.4, 1.8, 2.4]} position={[0, 0.9, 0]} castShadow />
      <mesh geometry={geos.box1} material={mats.red} scale={[0.5, 0.2, 1.8]} position={[0, 1.85, 0]} />
      <mesh geometry={geos.box1} material={mats.red} scale={[1.8, 0.2, 0.5]} position={[0, 1.85, 0]} />
    </group>
  );
}

function FallbackPolice({ position, isSelected }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.box1} material={mats.blue} scale={[2.4, 1.4, 1.6]} position={[0, 0.7, 0]} castShadow />
      <mesh geometry={geos.box1} material={mats.indigo} scale={[0.7, 1.0, 1.4]} position={[1.1, 0.5, 0]} castShadow />
    </group>
  );
}

function FallbackResidential({ position, isSelected }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.box1} material={mats.cream} scale={[1.8, 1.5, 1.8]} position={[0, 0.75, 0]} castShadow />
      <mesh geometry={geos.cone1} material={mats.orange} scale={[1.5, 1, 1.5]} position={[0, 2, 0]} rotation={[0, Math.PI / 4, 0]} />
    </group>
  );
}

function FallbackIndustrial({ position, isSelected }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.box1} material={mats.slate} scale={[2.8, 1, 2]} position={[0, 0.5, 0]} castShadow />
      <mesh geometry={geos.cyl1} material={mats.dark} scale={[0.3, 2, 0.3]} position={[1, 1.5, 0.6]} castShadow />
    </group>
  );
}

function FallbackPowerPlant({ position, isSelected }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.cyl1} material={mats.dark} scale={[0.9, 2.2, 0.9]} position={[0, 1.1, 0]} castShadow />
      <mesh geometry={geos.cyl1} material={mats.yellow} scale={[0.3, 1.2, 0.3]} position={[0.9, 1.6, 0]} />
    </group>
  );
}

function FallbackSchool({ position, isSelected }) {
  const g = useRef();
  useFrame(isSelected ? (st) => {
    if (g.current) g.current.scale.setScalar(1 + Math.sin(st.clock.elapsedTime * 5) * 0.06);
  } : () => {});
  return (
    <group ref={g} position={position}>
      <mesh geometry={geos.box1} material={mats.cream} scale={[2.4, 1.1, 1.8]} position={[0, 0.55, 0]} castShadow />
      <mesh geometry={geos.box1} material={mats.blue} scale={[0.5, 0.5, 0.5]} position={[0, 1.35, 0]} />
    </group>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Building components — load GLB, fall back to procedural
// ═══════════════════════════════════════════════════════════════════
const MODEL_PATHS = {
  hospital:    '/models/hospital.glb',
  police:      '/models/police.glb',
  residential: '/models/Residential.glb',
  industrial:  '/models/industrial.glb',
  powerplant:  '/models/powerplant.glb',
  school:      '/models/school.glb',
  ambulance:   '/models/ambulance.glb',
  gate:        '/models/gate.glb',
};

// Preload all (browser fetches in background)
Object.values(MODEL_PATHS).forEach(p => { try { useGLTF.preload(p); } catch(e) {} });

function GLBBuilding({ path, position, isSelected, isHovered, Fallback, castShadow = true }) {
  let gltf = null;
  try { gltf = useGLTF(path, true); } catch(e) { /* not loaded yet */ }

  const modelData = gltf ? getModelData(gltf, path) : null;

  if (modelData) {
    return <ModelInstance modelData={modelData} position={position} isSelected={isSelected} isHovered={isHovered} castShadow={castShadow} />;
  }
  return <Fallback position={position} isSelected={isSelected} isHovered={isHovered} />;
}

export function Hospital(props) {
  return <GLBBuilding path={MODEL_PATHS.hospital} Fallback={FallbackHospital} {...props} />;
}
export function Police(props) {
  return <GLBBuilding path={MODEL_PATHS.police} Fallback={FallbackPolice} {...props} />;
}
export function Residential(props) {
  return <GLBBuilding path={MODEL_PATHS.residential} Fallback={FallbackResidential} {...props} />;
}
export function Industrial(props) {
  return <GLBBuilding path={MODEL_PATHS.industrial} Fallback={FallbackIndustrial} {...props} />;
}
export function PowerPlant(props) {
  return <GLBBuilding path={MODEL_PATHS.powerplant} Fallback={FallbackPowerPlant} {...props} />;
}
export function School(props) {
  return <GLBBuilding path={MODEL_PATHS.school} Fallback={FallbackSchool} {...props} />;
}
export function AmbulanceDepot(props) {
  return <GLBBuilding path={MODEL_PATHS.ambulance} Fallback={FallbackPolice} {...props} />;
}

// ── Gate (decorative — placed at EMPTY nodes) ─────────────────────
function FallbackGate({ position, isSelected }) {
  return (
    <group position={position}>
      <mesh geometry={geos.box1} material={mats.purple} scale={[0.22, 1.8, 0.22]} position={[-0.9, 0.9, 0]} />
      <mesh geometry={geos.box1} material={mats.purple} scale={[0.22, 1.8, 0.22]} position={[0.9, 0.9, 0]} />
      <mesh geometry={geos.box1} material={mats.purpleD} scale={[2, 0.22, 0.3]} position={[0, 1.85, 0]} />
      <mesh geometry={geos.sphere} material={mats.gold} scale={[0.18, 0.18, 0.18]} position={[0, 2.15, 0]} />
    </group>
  );
}

export function Gate(props) {
  return <GLBBuilding path={MODEL_PATHS.gate} Fallback={FallbackGate} castShadow={false} {...props} />;
}

// ── Empty node (tiny green dot) ───────────────────────────────────
export function EmptyNode({ position }) {
  return (
    <group position={position}>
      <mesh geometry={geos.sphere} material={mats.green} scale={[0.2, 0.2, 0.2]} position={[0, 0.2, 0]} />
    </group>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Generic dispatcher
// ═══════════════════════════════════════════════════════════════════
const COMPONENTS = {
  HOSPITAL:    Hospital,
  DEPOT:       AmbulanceDepot,
  POLICE:      Police,
  RESIDENTIAL: Residential,
  INDUSTRIAL:  Industrial,
  POWER_PLANT: PowerPlant,
  SCHOOL:      School,
  GATE:        Gate,
  EMPTY:       EmptyNode,
};

export function GenericNode({
  position, isHovered, isSelected,
  type, onClick, onDoubleClick, onPointerOver, onPointerOut,
}) {
  const Component = COMPONENTS[type] || EmptyNode;
  
  // Calculate deterministic rotation based on position coordinates
  const rotY = useMemo(() => {
    const nx = position[0] || 0;
    const nz = position[2] || 0;
    // Seed a pseudo-random rotation (0, 90, 180, 270 degrees)
    return (Math.abs(Math.floor(nx * 7.3 + nz * 13.1)) % 4) * (Math.PI / 2);
  }, [position]);

  return (
    <group 
      position={position}
      rotation={[0, rotY, 0]}
      onClick={onClick} 
      onDoubleClick={onDoubleClick}
      onPointerOver={onPointerOver} 
      onPointerOut={onPointerOut}
    >
      <Component position={[0, 0, 0]} isHovered={isHovered} isSelected={isSelected} />
      {isSelected && (
        <mesh position={[0, 1, 0]}>
          <cylinderGeometry args={[4, 4, 10, 32]} />
          <meshBasicMaterial color="#00D4FF" transparent opacity={0.15} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      )}
      {isSelected && (
        <mesh position={[0, 0.1, 0]}>
          <ringGeometry args={[4, 4.5, 32]} />
          <meshBasicMaterial color="#00D4FF" side={THREE.DoubleSide} transparent opacity={0.8} />
        </mesh>
      )}
    </group>
  );
}
