// ═══════════════════════════════════════════════════════════
// CITYMIND — Typed Array Particle Pool
// Zero allocation per frame. Pre-allocated Float32Arrays.
// Max 800 particles. LOD culling built-in.
// ═══════════════════════════════════════════════════════════

export const MAX_PARTICLES = 800;

// Particle state arrays — allocated ONCE at module load
export const px       = new Float32Array(MAX_PARTICLES);
export const py       = new Float32Array(MAX_PARTICLES);
export const pStartX  = new Float32Array(MAX_PARTICLES);
export const pStartY  = new Float32Array(MAX_PARTICLES);
export const pEndX    = new Float32Array(MAX_PARTICLES);
export const pEndY    = new Float32Array(MAX_PARTICLES);
export const pT       = new Float32Array(MAX_PARTICLES); // 0-1 along edge
export const pSpeed   = new Float32Array(MAX_PARTICLES);
export const pSize    = new Float32Array(MAX_PARTICLES);
export const pLife    = new Float32Array(MAX_PARTICLES);
export const pEdge    = new Int32Array(MAX_PARTICLES);   // edge index
export const pColorR  = new Uint8Array(MAX_PARTICLES);
export const pColorG  = new Uint8Array(MAX_PARTICLES);
export const pColorB  = new Uint8Array(MAX_PARTICLES);
export const pActive  = new Uint8Array(MAX_PARTICLES);   // 0 or 1
export const pTrailT  = new Float32Array(MAX_PARTICLES); // trail length as t delta

export let activeCount = 0;

export function resetPool() {
  activeCount = 0;
  pActive.fill(0);
}

export function spawnParticle(sx, sy, ex, ey, speed, size, r, g, b, edgeIdx, trailLen) {
  if (activeCount >= MAX_PARTICLES) return -1;
  const i = activeCount++;
  pStartX[i] = sx; pStartY[i] = sy;
  pEndX[i] = ex; pEndY[i] = ey;
  pT[i] = Math.random(); // random start position along edge
  pSpeed[i] = speed;
  pSize[i] = size;
  pLife[i] = 1.0;
  pEdge[i] = edgeIdx;
  pColorR[i] = r; pColorG[i] = g; pColorB[i] = b;
  pActive[i] = 1;
  pTrailT[i] = trailLen;
  // Calculate initial position
  px[i] = sx + (ex - sx) * pT[i];
  py[i] = sy + (ey - sy) * pT[i];
  return i;
}

export function updateParticles(dt, speedMultiplier) {
  for (let i = 0; i < activeCount; i++) {
    if (!pActive[i]) continue;
    pT[i] += pSpeed[i] * dt * speedMultiplier;
    if (pT[i] > 1.0) pT[i] -= 1.0;
    if (pT[i] < 0.0) pT[i] += 1.0;

    const t = pT[i];
    px[i] = pStartX[i] + (pEndX[i] - pStartX[i]) * t;
    py[i] = pStartY[i] + (pEndY[i] - pStartY[i]) * t;
  }
}

export function updateEdgeEndpoints(i, sx, sy, ex, ey) {
  pStartX[i] = sx; pStartY[i] = sy;
  pEndX[i] = ex; pEndY[i] = ey;
}

export function getActiveCount() { return activeCount; }
export function setActiveCount(n) { activeCount = n; }
