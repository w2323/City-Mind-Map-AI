// ═══════════════════════════════════════════════════════════════════════
// CITYMIND — 3D City Map  (GraphCanvas3D)
// Rebuilt from scratch with perfect orthographic top-down alignment,
// smooth zoom, vibrant colours, and correct GLB model sizing.
// ═══════════════════════════════════════════════════════════════════════
import React, { useRef, useState, useMemo, useEffect, Suspense } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { MapControls, Text, Line } from '@react-three/drei';
import * as THREE from 'three';
import { GenericNode } from './Buildings3D';
import { Roads3D } from './Roads3D';
import * as PP from '../engine/ParticlePool';
import { getMST } from '../utils/pathfinding';

// ── Grid constants ─────────────────────────────────────────────────
const GRID_SIZE   = 15;        // 15 × 15 city grid
const CELL_SIZE   = 8;         // world-units between node centres
const HALF_GRID   = (GRID_SIZE - 1) * CELL_SIZE * 0.5; // centre offset

// ── Shared Geometries & Materials ────────────────────────────────
const sharedGeos = {
  heatmap: new THREE.PlaneGeometry(CELL_SIZE, CELL_SIZE),
  coverageCircle: new THREE.CircleGeometry(CELL_SIZE * 2.5, 32),
  coverageRing: new THREE.RingGeometry(CELL_SIZE * 2.5 - 0.2, CELL_SIZE * 2.5, 32),
  clusterCircle: new THREE.CircleGeometry(CELL_SIZE * 3, 32),
  foundation: new THREE.PlaneGeometry(CELL_SIZE - 0.4, CELL_SIZE - 0.4)
};

const sharedMats = {
  highRisk: new THREE.MeshBasicMaterial({ color: '#FF4757', transparent: true, opacity: 0.3, depthWrite: false }),
  medRisk: new THREE.MeshBasicMaterial({ color: '#FF8C42', transparent: true, opacity: 0.3, depthWrite: false }),
  lowRisk: new THREE.MeshBasicMaterial({ color: '#10B981', transparent: true, opacity: 0.3, depthWrite: false }),
  coverageBase: new THREE.MeshBasicMaterial({ color: '#0066FF', transparent: true, opacity: 0.15, depthWrite: false }),
  coverageRing: new THREE.MeshBasicMaterial({ color: '#0066FF', transparent: true, opacity: 0.5 }),
  cluster: new THREE.MeshBasicMaterial({ color: '#FF4757', transparent: true, opacity: 0.08, depthWrite: false }),
  foundation: new THREE.MeshStandardMaterial({ color: '#2a2d4d', roughness: 0.9, metalness: 0.1 })
};

// ── Camera Controller ──────────────────────────────────────────────
function CameraController({ streetView, resetTrigger, selectedNode, layout, onZoomChange }) {
  const { camera, controls } = useThree();
  const animating = useRef(false);
  const targetPos = useRef(new THREE.Vector3());
  const targetTarget = useRef(new THREE.Vector3());
  const lastZoomRef = useRef(0);

  // Cancel animation on any user interaction (drag / scroll)
  useEffect(() => {
    if (!controls) return;
    const stop = () => { animating.current = false; };
    controls.addEventListener('start', stop);
    return () => controls.removeEventListener('start', stop);
  }, [controls]);

  // Kick-off animation when view mode or selection changes
  useEffect(() => {
    if (!controls) return;
    if (selectedNode && layout?.nodes?.[selectedNode]) {
      const n = layout.nodes[selectedNode];
      const nx = n.col * CELL_SIZE;
      const nz = n.row * CELL_SIZE;
      targetPos.current.set(nx + 10, 15, nz + 10);
      targetTarget.current.set(nx, 0, nz);
      animating.current = true;
    } else if (streetView) {
      targetPos.current.set(HALF_GRID, 12, HALF_GRID + 30);
      targetTarget.current.set(HALF_GRID, 0, HALF_GRID);
      animating.current = true;
    } else {
      // Perfect top-down: camera directly above centre looking straight down
      targetPos.current.set(HALF_GRID, 150, HALF_GRID + 0.001);
      targetTarget.current.set(HALF_GRID, 0, HALF_GRID);
      animating.current = true;
    }
  }, [streetView, controls, resetTrigger, selectedNode, layout]);

  useFrame(() => {
    if (!controls) return;
    
    if (animating.current) {
      camera.position.lerp(targetPos.current, 0.08);
      controls.target.lerp(targetTarget.current, 0.08);
      camera.updateProjectionMatrix();
      if (camera.position.distanceTo(targetPos.current) < 0.5) {
        animating.current = false;
      }
    }
    controls.update();

    if (onZoomChange) {
      const dist = camera.position.distanceTo(controls.target);
      const z = Math.max(0.1, 150 / dist);
      if (Math.abs(lastZoomRef.current - z) > 0.05) {
        lastZoomRef.current = z;
        onZoomChange(z);
      }
    }
  });

  return null;
}

// ── Physics / particle tick ────────────────────────────────────────
function PhysicsEngine({ simSpeed }) {
  useFrame((_s, delta) => {
    PP.updateParticles(Math.min(delta, 0.05) * 60, simSpeed || 1);
  });
  return null;
}

// ── Main Component ─────────────────────────────────────────────────
export default function GraphCanvas3D({
  graph, state, stats, viewToggles, simSpeed,
  onSelectNode, selectedNode, booted, streetView, resetTrigger, onZoomChange, placementMode,
  roadMode, gatesNodeId, gatesPaths, godMode, coverageRadius
}) {
  const [hoveredNode, setHoveredNode] = useState(null);
  const [optimizingNodes, setOptimizingNodes] = useState([]);

  // ── Build layout once graph data arrives ──────────────────────
  const layout = useMemo(() => {
    if (!graph?.nodes) return null;

    const nodes = graph.nodes;
    const baseEdges = stats?.edgeList || [];
    const currentPath = state?.router?.current_path || [];

    // Route highlight set
    const routeSet = new Set();
    for (let i = 0; i < currentPath.length - 1; i++) {
      const a = Math.min(currentPath[i], currentPath[i + 1]);
      const b = Math.max(currentPath[i], currentPath[i + 1]);
      routeSet.add(`${a}_${b}`);
    }

    let displayEdges = baseEdges;

    if (roadMode === 'Optimized (MST)') {
      const { mst } = getMST(baseEdges, 225);
      displayEdges = mst;
    } else if (roadMode === 'Comparison') {
      const { mst, extra } = getMST(baseEdges, 225);
      for (const e of extra) {
        const a = Math.min(e.nodeA, e.nodeB);
        const b = Math.max(e.nodeA, e.nodeB);
        routeSet.add(`${a}_${b}`);
      }
      displayEdges = baseEdges;
    } else if (roadMode === 'All roads') {
      const allE = [];
      const grid = Array.from({length: 15}, () => Array(15).fill(null));
      for (const id in nodes) {
        const n = nodes[id];
        grid[n.row][n.col] = Number(id);
      }
      for (let r = 0; r < 15; r++) {
        for (let c = 0; c < 15; c++) {
          const u = grid[r][c];
          if (u === null) continue;
          if (c + 1 < 15 && grid[r][c+1] !== null) allE.push({ nodeA: u, nodeB: grid[r][c+1], blocked: false });
          if (r + 1 < 15 && grid[r+1][c] !== null) allE.push({ nodeA: u, nodeB: grid[r+1][c], blocked: false });
          if (r + 1 < 15 && c + 1 < 15 && grid[r+1][c+1] !== null) allE.push({ nodeA: u, nodeB: grid[r+1][c+1], blocked: false });
          if (r + 1 < 15 && c - 1 >= 0 && grid[r+1][c-1] !== null) allE.push({ nodeA: u, nodeB: grid[r+1][c-1], blocked: false });
        }
      }
      displayEdges = allE;
    }

    // Flat node list
    const nodeList = [];
    for (const id in nodes) {
      const n = nodes[id];
      nodeList.push({
        id: Number(id),
        row: n.row,
        col: n.col,
        type: n.node_type || 'EMPTY',
        pop: n.population_density || 0,
      });
    }

    // ── Spawn traffic particles ────────────────────────────────
    PP.resetPool();
    let idx = 0;
    for (let ei = 0; ei < displayEdges.length; ei++) {
      if (idx >= PP.MAX_PARTICLES) break;
      const e = displayEdges[ei];
      const nA = nodes[String(e.nodeA)];
      const nB = nodes[String(e.nodeB)];
      if (!nA || !nB) continue;

      const ax = nA.col * CELL_SIZE;
      const ay = nA.row * CELL_SIZE;
      const bx = nB.col * CELL_SIZE;
      const by = nB.row * CELL_SIZE;

      const key = `${Math.min(e.nodeA, e.nodeB)}_${Math.max(e.nodeA, e.nodeB)}`;
      const isRoute = routeSet.has(key);
      const count = isRoute ? 3 : 1;

      for (let j = 0; j < count; j++) {
        if (idx >= PP.MAX_PARTICLES) break;
        // Vibrant car colours
        let r = 0, g = 200, b = 255;
        if (isRoute)               { r = 255; g = 71;  b = 87;  }
        else if (Math.random() > 0.6) { r = 16;  g = 185; b = 129; }
        else if (Math.random() > 0.5) { r = 139; g = 92;  b = 246; }

        PP.spawnParticle(
          ax, ay, bx, by,
          0.0012 + Math.random() * 0.002,
          2 + Math.random(), r, g, b, ei, 0,
        );
        idx++;
      }
    }

    return { nodes, edges: displayEdges, routeSet, nodeList };
  }, [graph, state, stats, roadMode]);

  const depots = useMemo(() => {
    if (!graph?.nodes) return [];
    return Object.entries(graph.nodes)
      .filter(([_, n]) => n.node_type === 'AMBULANCE_DEPOT' || n.node_type === 'DEPOT')
      .map(([id]) => Number(id));
  }, [graph]);

  useEffect(() => {
    if (placementMode === 'Optimizing...' && depots.length > 0) {
      const interval = setInterval(() => {
         const shuffled = [...depots].sort(() => 0.5 - Math.random());
         setOptimizingNodes(shuffled.slice(0, 3));
      }, 150);
      return () => clearInterval(interval);
    }
  }, [placementMode, depots]);

  if (!booted || !layout) return null;
  const { nodes, edges, routeSet, nodeList } = layout;

  return (
    <div style={{
      width: '100%', height: '100%',
      position: 'absolute', top: 0, left: 0,
      zIndex: 0, background: 'linear-gradient(135deg, #0c0c1e 0%, #121228 100%)',
    }}>
      <Canvas
        dpr={[1, 1]}
        performance={{ min: 0.5 }}
        camera={{ position: [HALF_GRID, 100, HALF_GRID + 0.001], fov: 50, near: 0.5, far: 500 }}
      >
        <ambientLight intensity={0.8} color="#ffffff" />
        <directionalLight
          position={[HALF_GRID + 60, 100, HALF_GRID + 20]}
          intensity={1.8}
          color="#fffaf0"
        />
        <hemisphereLight skyColor="#88bbff" groundColor="#222244" intensity={0.5} />

        {/* ── Controls (smooth zoom via damping) ───────────────── */}
        <MapControls
          makeDefault
          enableDamping
          dampingFactor={0.10}
          zoomSpeed={1.4}
          panSpeed={1.2}
          rotateSpeed={0.8}
          maxPolarAngle={Math.PI / 2 - 0.01}
          minDistance={2}
          maxDistance={500}
        />
        <CameraController streetView={streetView} resetTrigger={resetTrigger} selectedNode={selectedNode} layout={layout} onZoomChange={onZoomChange} />

        {/* ── Particle physics tick ────────────────────────────── */}
        <PhysicsEngine simSpeed={simSpeed} />

        {/* ── Scene (wrapped in Suspense for async GLB loads) ─── */}
        <Suspense fallback={null}>
          <group>
            {/* ── Ground ──────────────────────────────────────── */}
            <mesh
              rotation={[-Math.PI / 2, 0, 0]}
              position={[HALF_GRID, -0.05, HALF_GRID]}
            >
              <planeGeometry args={[GRID_SIZE * CELL_SIZE + 40, GRID_SIZE * CELL_SIZE + 40]} />
              <meshStandardMaterial color="#1e2040" roughness={0.95} />
            </mesh>

            {/* ── Grid-lines (very subtle) ────────────────────── */}
            <gridHelper
              args={[
                (GRID_SIZE - 1) * CELL_SIZE,
                GRID_SIZE - 1,
                '#252850',
                '#252850',
              ]}
              position={[HALF_GRID, 0.01, HALF_GRID]}
            />

            {/* ── Grid Markings (Alphanumeric) ────────────────────── */}
            {Array.from({ length: GRID_SIZE }).map((_, i) => (
              <React.Fragment key={`mark-${i}`}>
                {/* Column labels (A-O) along the top edge */}
                <Text
                  position={[i * CELL_SIZE, 0.5, -CELL_SIZE]}
                  rotation={[-Math.PI / 2, 0, 0]}
                  fontSize={4}
                  color="#88bbff"
                  anchorX="center"
                  anchorY="middle"
                >
                  {String.fromCharCode(65 + i)}
                </Text>
                {/* Row labels (1-15) along the left edge */}
                <Text
                  position={[-CELL_SIZE, 0.5, i * CELL_SIZE]}
                  rotation={[-Math.PI / 2, 0, 0]}
                  fontSize={4}
                  color="#88bbff"
                  anchorX="center"
                  anchorY="middle"
                >
                  {i + 1}
                </Text>
              </React.Fragment>
            ))}

            {/* ── Roads & traffic ─────────────────────────────── */}
            {viewToggles?.roads !== false && (
              <Roads3D
                edges={edges}
                nodes={nodes}
                spacing={CELL_SIZE}
                ox={0} oy={0}
                routeSet={routeSet}
              />
            )}

            {/* ── Gates of Death Paths ─────────────────────────── */}
            {gatesPaths && gatesPaths.map((gp, idx) => {
              const points = gp.path.map(id => {
                const n = nodes[id];
                return new THREE.Vector3(n.col * CELL_SIZE, 0.4, n.row * CELL_SIZE);
              });
              if (points.length < 2) return null;
              return (
                <Line
                  key={`gp-${idx}`}
                  points={points}
                  color={gp.color}
                  lineWidth={4}
                  transparent
                  opacity={0.9}
                />
              );
            })}

            {/* ── Agent Trails ─────────────────────────── */}
            {viewToggles?.trails && state?.router?.current_path && state.router.current_path.length > 1 && (
              <Line
                points={state.router.current_path.map(id => {
                  const n = nodes[id];
                  return new THREE.Vector3(n.col * CELL_SIZE, 0.6, n.row * CELL_SIZE);
                })}
                color="#00ffcc"
                lineWidth={6}
                transparent
                opacity={0.8}
              />
            )}

            {/* ── Buildings / nodes ───────────────────────────── */}
            {nodeList.map(n => {
              const displayType = n.type === 'EMPTY' ? 'GATE' : n.type;
              const nx = n.col * CELL_SIZE;
              const nz = n.row * CELL_SIZE;

              return (
                <group key={n.id}>
                  {/* Subtle foundation tile */}
                  {displayType !== 'GATE' && (
                    <mesh position={[nx, 0.02, nz]} rotation={[-Math.PI / 2, 0, 0]} geometry={sharedGeos.foundation} material={sharedMats.foundation} />
                  )}
                  <GenericNode
                    type={displayType}
                    position={[nx, 0, nz]}
                    scale={1}
                    isHovered={hoveredNode === n.id}
                    isSelected={selectedNode === n.id}
                    onClick={(e) => { e.stopPropagation(); onSelectNode(n.id); }}
                    onDoubleClick={(e) => { e.stopPropagation(); onSelectNode(n.id); }}
                    onPointerOver={(e) => {
                      e.stopPropagation();
                      setHoveredNode(n.id);
                      document.body.style.cursor = godMode ? 'crosshair' : 'pointer';
                    }}
                    onPointerOut={() => {
                      setHoveredNode(null);
                      document.body.style.cursor = 'default';
                    }}
                  />
                  {/* Ambulance Coverage Rings */}
                  {((placementMode === 'All candidates' && (displayType === 'AMBULANCE_DEPOT' || displayType === 'DEPOT')) ||
                    (placementMode === 'Optimizing...' && optimizingNodes.includes(n.id)) ||
                    ((!placementMode || placementMode === 'Current' || placementMode === 'Best found') && viewToggles?.coverage && state?.ambulances?.includes(n.id))
                  ) && (
                    <mesh position={[nx, 0.05, nz]} rotation={[-Math.PI / 2, 0, 0]} geometry={sharedGeos.coverageCircle} material={sharedMats.coverageBase} scale={[coverageRadius / 5, coverageRadius / 5, 1]}>
                      <mesh position={[0, 0, 0.1]} geometry={sharedGeos.coverageRing} material={sharedMats.coverageRing} />
                    </mesh>
                  )}
                  {viewToggles?.clusters && displayType === 'RESIDENTIAL' && (n.id % 3 === 0) && (
                    <mesh position={[nx, 0.1, nz]} rotation={[-Math.PI / 2, 0, 0]} geometry={sharedGeos.clusterCircle} material={sharedMats.cluster} />
                  )}
                  {gatesNodeId === n.id && (
                    <mesh position={[nx, 0.08, nz]} rotation={[-Math.PI / 2, 0, 0]} geometry={sharedGeos.coverageCircle} scale={[coverageRadius / 5, coverageRadius / 5, 1]}>
                      <meshBasicMaterial color="#ff0055" transparent opacity={0.6} depthWrite={false} />
                    </mesh>
                  )}
                  {viewToggles?.heatmap && (
                    <mesh position={[nx, 0.03, nz]} rotation={[-Math.PI / 2, 0, 0]} geometry={sharedGeos.heatmap} material={
                      state?.risk_predictions?.[n.id] === 'HIGH' ? sharedMats.highRisk : 
                      state?.risk_predictions?.[n.id] === 'MEDIUM' ? sharedMats.medRisk : sharedMats.lowRisk
                    } />
                  )}
                </group>
              );
            })}
          </group>
        </Suspense>
      </Canvas>
    </div>
  );
}
