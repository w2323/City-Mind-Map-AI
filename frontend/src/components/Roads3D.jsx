// ═══════════════════════════════════════════════════════════════════════
// CITYMIND — Roads3D  (Performance-Optimised Rewrite)
//
// PERF STRATEGY:
//  1. Road geometries are computed once and memoised
//  2. Car InstancedMesh uses a single pre-allocated Object3D (no alloc)
//  3. Car geometry normalised once at load, cached via useMemo
//  4. Colour buffer written in-place, no new arrays per frame
// ═══════════════════════════════════════════════════════════════════════
import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { useGLTF, Text } from '@react-three/drei';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import * as PP from '../engine/ParticlePool';

// ── Bezier helper ─────────────────────────────────────────────────
function bezierCurve(ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const side = ((Math.floor(ax) ^ Math.floor(ay) ^ Math.floor(bx) ^ Math.floor(by)) % 2) === 0 ? 1 : -1;
  const cx = (ax + bx) / 2 - dy * 0.18 * side;
  const cy = (ay + by) / 2 + dx * 0.18 * side;
  return new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(ax, 0.05, ay),
    new THREE.Vector3(cx, 0.05, cy),
    new THREE.Vector3(bx, 0.05, by),
  );
}

// ═══════════════════════════════════════════════════════════════════
// Road lines
// ═══════════════════════════════════════════════════════════════════

// Pre-create shared materials (never reallocated)
const roadMat = new THREE.LineBasicMaterial({ color: '#4a5568', transparent: true, opacity: 0.45 });
const routeMat = new THREE.LineBasicMaterial({ color: '#ef4444', transparent: true, opacity: 0.85 });
const blockedMat = new THREE.LineBasicMaterial({ color: '#3b82f6', transparent: true, opacity: 0.85 });

export function Roads3D({ edges, nodes, spacing, ox, oy, routeSet }) {
  const roadData = useMemo(() => {
    return edges.map(e => {
      const nA = nodes[String(e.nodeA)];
      const nB = nodes[String(e.nodeB)];
      if (!nA || !nB) return null;

      const ax = ox + nA.col * spacing;
      const ay = oy + nA.row * spacing;
      const bx = ox + nB.col * spacing;
      const by = oy + nB.row * spacing;

      const pts = bezierCurve(ax, ay, bx, by).getPoints(20);
      const geo = new THREE.BufferGeometry().setFromPoints(pts);

      const key = `${Math.min(e.nodeA, e.nodeB)}_${Math.max(e.nodeA, e.nodeB)}`;
      const isRoute = routeSet.has(key);
      const isBlocked = e.blocked;

      let mat = roadMat;
      if (isBlocked) mat = blockedMat;
      else if (isRoute) mat = routeMat;

      let midX = 0, midZ = 0;
      if (isBlocked) {
        const dx = bx - ax, dy = by - ay;
        const side = ((Math.floor(ax) ^ Math.floor(ay) ^ Math.floor(bx) ^ Math.floor(by)) % 2) === 0 ? 1 : -1;
        const cX = (ax + bx) / 2 - dy * 0.18 * side;
        const cZ = (ay + by) / 2 + dx * 0.18 * side;
        midX = 0.25 * ax + 0.5 * cX + 0.25 * bx;
        midZ = 0.25 * ay + 0.5 * cZ + 0.25 * by;
      }

      return { geo, mat, isBlocked, midX, midZ };
    }).filter(Boolean);
  }, [edges, nodes, spacing, ox, oy, routeSet]);

  return (
    <group>
      {roadData.map((r, i) => (
        <React.Fragment key={i}>
          <line geometry={r.geo} material={r.mat} />
          {r.isBlocked && (
            <Text
              position={[r.midX, 0.5, r.midZ]}
              rotation={[-Math.PI / 2, 0, 0]}
              fontSize={4}
              anchorX="center"
              anchorY="middle"
            >
              🌊
            </Text>
          )}
        </React.Fragment>
      ))}
      <TrafficCars />
    </group>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Traffic cars (InstancedMesh)
// ═══════════════════════════════════════════════════════════════════
try { useGLTF.preload('/models/car.glb'); } catch(e) {}

// Procedural fallback car geometry (shared, never recreated)
const fallbackGeo = (() => {
  const body  = new THREE.BoxGeometry(1.0, 0.25, 0.45); body.translate(0, 0.2, 0);
  const cabin = new THREE.BoxGeometry(0.5, 0.22, 0.38); cabin.translate(-0.08, 0.45, 0);
  const wGeo  = new THREE.CylinderGeometry(0.1, 0.1, 0.08, 8); wGeo.rotateX(Math.PI / 2);
  const w1 = wGeo.clone(); w1.translate(-0.32, 0.1, 0.2);
  const w2 = wGeo.clone(); w2.translate( 0.32, 0.1, 0.2);
  const w3 = wGeo.clone(); w3.translate(-0.32, 0.1,-0.2);
  const w4 = wGeo.clone(); w4.translate( 0.32, 0.1,-0.2);
  return mergeGeometries([body, cabin, w1, w2, w3, w4], false);
})();

function TrafficCars() {
  const meshRef = useRef();
  // Pre-allocate a SINGLE Object3D — never create new ones in the loop
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const colors = useMemo(() => new Float32Array(PP.MAX_PARTICLES * 3), []);

  let gltf = null;
  try { gltf = useGLTF('/models/car.glb', true); } catch(e) {}

  // Normalise car geometry once
  const carGeo = useMemo(() => {
    if (gltf?.scene) {
      let geo = null;
      gltf.scene.traverse(c => { if (c.isMesh && !geo) geo = c.geometry; });
      if (geo) {
        geo = geo.clone();
        geo.computeBoundingBox();
        const s = new THREE.Vector3();
        geo.boundingBox.getSize(s);
        const f = 1 / Math.max(s.x, s.y, s.z, 0.001);
        geo.scale(f, f, f);
        geo.center();
        return geo;
      }
    }
    return fallbackGeo;
  }, [gltf]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const count = PP.getActiveCount();
    mesh.count = count;

    for (let i = 0; i < count; i++) {
      if (!PP.pActive[i]) {
        dummy.scale.set(0, 0, 0);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        continue;
      }

      const sx = PP.pStartX[i], sy = PP.pStartY[i];
      const ex = PP.pEndX[i],   ey = PP.pEndY[i];
      const t  = PP.pT[i];

      const dx = ex - sx, dy = ey - sy;
      const side = ((Math.floor(sx) ^ Math.floor(sy) ^ Math.floor(ex) ^ Math.floor(ey)) % 2) === 0 ? 1 : -1;
      const cx = (sx + ex) / 2 - dy * 0.18 * side;
      const cy = (sy + ey) / 2 + dx * 0.18 * side;

      const t2 = t * t, mt = 1 - t, mt2 = mt * mt;
      const px = mt2 * sx + 2 * mt * t * cx + t2 * ex;
      const py = mt2 * sy + 2 * mt * t * cy + t2 * ey;
      const dpx = 2 * mt * (cx - sx) + 2 * t * (ex - cx);
      const dpy = 2 * mt * (cy - sy) + 2 * t * (ey - cy);

      dummy.position.set(px, 0.15, py);
      dummy.rotation.set(0, -Math.atan2(dpy, dpx), 0);
      dummy.scale.set(0.45, 0.45, 0.45);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);

      colors[i * 3]     = PP.pColorR[i] / 255;
      colors[i * 3 + 1] = PP.pColorG[i] / 255;
      colors[i * 3 + 2] = PP.pColorB[i] / 255;
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.geometry.attributes.color) {
      mesh.geometry.attributes.color.needsUpdate = true;
    } else {
      mesh.geometry.setAttribute('color', new THREE.InstancedBufferAttribute(colors, 3));
    }
  });

  return (
    <instancedMesh ref={meshRef} args={[carGeo, null, PP.MAX_PARTICLES]} frustumCulled={false}>
      <meshStandardMaterial vertexColors roughness={0.35} metalness={0.55} />
    </instancedMesh>
  );
}
