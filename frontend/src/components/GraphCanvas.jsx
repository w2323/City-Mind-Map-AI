// ═══════════════════════════════════════════════════════════
// CITYMIND — Graph Canvas Engine
// 60fps Canvas 2D renderer. Zero React coupling in rAF.
// OffscreenCanvas sprite stamping, typed array particles.
// ═══════════════════════════════════════════════════════════

import { useRef, useEffect, useCallback } from 'react';
import { buildSpriteAtlas, getGlowSprite, hexToRgb } from '../engine/GlowSprites';
import * as PP from '../engine/ParticlePool';
import { Spring, lerp, clamp } from '../engine/SpringSolver';

// ── Spark color mapping ──────────────────────────────────
const EDGE_COLORS = {
  'RESIDENTIAL-RESIDENTIAL': '#00E5FF',
  'RESIDENTIAL-HOSPITAL':    '#00FFAA',
  'HOSPITAL-RESIDENTIAL':    '#00FFAA',
  'RESIDENTIAL-SCHOOL':      '#FFD600',
  'SCHOOL-RESIDENTIAL':      '#FFD600',
  'HOSPITAL-DEPOT':          '#00AA88',
  'DEPOT-HOSPITAL':          '#00AA88',
  'INDUSTRIAL-POWER_PLANT':  '#FF6D00',
  'POWER_PLANT-INDUSTRIAL':  '#FF6D00',
  'EMERGENCY':               '#FF1744',
  'FLOODED':                 '#666666',
  'DEFAULT':                 '#2979FF',
};

function getEdgeColorHex(typeA, typeB, isRoute, isFlooded) {
  if (isFlooded) return '#666666';
  if (isRoute) return '#FF1744';
  const key = `${typeA}-${typeB}`;
  return EDGE_COLORS[key] || '#2979FF';
}

// ── Node color config ─────────────────────────────────────
const NODE_COLORS = {
  RESIDENTIAL: { ring: '#00CCFF', core: '#FFFFFF' },
  HOSPITAL:    { ring: '#00FFAA', core: '#FFFFFF' },
  SCHOOL:      { ring: '#FFD600', core: '#FFD600' },
  INDUSTRIAL:  { ring: '#FF6600', core: '#FF6600' },
  POWER_PLANT: { ring: '#FF4444', core: '#FFFFFF' },
  DEPOT:       { ring: '#4488FF', core: '#4488FF' },
  EMPTY:       { ring: '#1a1b2e', core: '#1a1b2e' },
};

export default function GraphCanvas({ graph, state, stats, booted, selectedNode, onSelectNode, viewToggles, simSpeed }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const bgCanvasRef = useRef(null); // static background
  const animRef = useRef(null);
  const fpsRef = useRef({ frames: 0, lastTime: performance.now(), fps: 60 });
  const mouseRef = useRef({ x: -1000, y: -1000, hoveredNode: -1 });
  const layoutRef = useRef({ nodes: {}, edges: [], spacing: 0, ox: 0, oy: 0, w: 0, h: 0, routeSet: new Set(), risks: {}, nodeList: [] });
  const nodeSpringScales = useRef({});
  const particlesInitialized = useRef(false);

  // Build sprite atlas once on mount
  useEffect(() => { buildSpriteAtlas(); }, []);

  // ── Rebuild layout data when graph/state changes (no rAF) ──
  useEffect(() => {
    if (!graph?.nodes) return;
    const nodes = graph.nodes;
    const edgeList = stats?.edgeList || [];
    const currentPath = state?.router?.current_path || [];
    const risks = state?.risk_predictions || {};

    const routeSet = new Set();
    for (let i = 0; i < currentPath.length - 1; i++) {
      const a = Math.min(currentPath[i], currentPath[i + 1]);
      const b = Math.max(currentPath[i], currentPath[i + 1]);
      routeSet.add(`${a}_${b}`);
    }

    const nodeList = [];
    for (const id in nodes) {
      const n = nodes[id];
      nodeList.push({ id: Number(id), row: n.row, col: n.col, type: n.node_type || 'EMPTY', pop: n.population_density || 0 });
    }

    layoutRef.current.nodes = nodes;
    layoutRef.current.edges = edgeList;
    layoutRef.current.routeSet = routeSet;
    layoutRef.current.risks = risks;
    layoutRef.current.nodeList = nodeList;

    // Initialize particles for edges
    PP.resetPool();
    const { spacing, ox, oy } = layoutRef.current;
    if (spacing > 0) {
      initParticlesFromEdges(edgeList, nodes, routeSet, spacing, ox, oy);
    }
    particlesInitialized.current = spacing > 0;
  }, [graph, state, stats]);

  // ── Canvas ResizeObserver ──
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const bgCanvas = document.createElement('canvas');
    bgCanvasRef.current = bgCanvas;

    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        bgCanvas.width = canvas.width;
        bgCanvas.height = canvas.height;

        const s = Math.min(width, height) / 17;
        layoutRef.current.spacing = s;
        layoutRef.current.ox = (width - 14 * s) / 2;
        layoutRef.current.oy = (height - 14 * s) / 2;
        layoutRef.current.w = width;
        layoutRef.current.h = height;

        drawBackground(bgCanvas, width, height, dpr);

        // Re-init particles with new layout
        const { edges, nodes: ln, routeSet } = layoutRef.current;
        if (ln && Object.keys(ln).length > 0) {
          PP.resetPool();
          initParticlesFromEdges(edges, ln, routeSet, s, layoutRef.current.ox, layoutRef.current.oy);
          particlesInitialized.current = true;
        }
      }
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // ── Mouse tracking (for hover/click — no React re-renders) ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.x = e.clientX - rect.left;
      mouseRef.current.y = e.clientY - rect.top;
    };

    const handleClick = (e) => {
      const { hoveredNode } = mouseRef.current;
      if (hoveredNode >= 0 && onSelectNode) {
        onSelectNode(hoveredNode === selectedNode ? null : hoveredNode);
      }
    };

    const handleLeave = () => {
      mouseRef.current.x = -1000;
      mouseRef.current.y = -1000;
    };

    canvas.addEventListener('mousemove', handleMove);
    canvas.addEventListener('click', handleClick);
    canvas.addEventListener('mouseleave', handleLeave);
    return () => {
      canvas.removeEventListener('mousemove', handleMove);
      canvas.removeEventListener('click', handleClick);
      canvas.removeEventListener('mouseleave', handleLeave);
    };
  }, [onSelectNode, selectedNode]);

  // ── Main Animation Loop (ZERO React calls inside) ──
  useEffect(() => {
    if (!booted) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let frame = 0;
    let lastTime = performance.now();

    function render(now) {
      frame++;
      const dt = Math.min((now - lastTime) / 1000, 0.05); // cap dt
      lastTime = now;

      // FPS counter
      fpsRef.current.frames++;
      if (now - fpsRef.current.lastTime >= 1000) {
        fpsRef.current.fps = fpsRef.current.frames;
        fpsRef.current.frames = 0;
        fpsRef.current.lastTime = now;
      }

      const dpr = window.devicePixelRatio || 1;
      const L = layoutRef.current;
      const { spacing, ox, oy, w, h, routeSet, risks, nodeList, edges, nodes } = L;

      if (!spacing || !nodes || nodeList.length === 0) {
        animRef.current = requestAnimationFrame(render);
        return;
      }

      // Composite transparent static background (grid)
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const bg = bgCanvasRef.current;
      if (bg) {
        ctx.drawImage(bg, 0, 0);
      }

      ctx.save();
      ctx.scale(dpr, dpr);

      const time = frame * 0.02;
      const toggles = viewToggles || { roads: true, coverage: true, heatmap: false, trails: false };
      const speed = simSpeed || 1;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      // ── Find hovered node ──
      let hovId = -1;
      let hovDist = 80;
      for (let i = 0; i < nodeList.length; i++) {
        const n = nodeList[i];
        if (n.type === 'EMPTY') continue;
        const nx = ox + n.col * spacing;
        const ny = oy + n.row * spacing;
        const d = Math.sqrt((mx - nx) ** 2 + (my - ny) ** 2);
        if (d < hovDist) { hovDist = d; hovId = n.id; }
      }
      mouseRef.current.hoveredNode = hovId;
      canvas.style.cursor = hovId >= 0 ? 'pointer' : 'crosshair';

      // ── Draw Ambient Particles ──
      drawAmbientParticles(ctx, canvas.width / dpr, canvas.height / dpr, time);

      // ── Draw Edges ──
      if (toggles.roads) {
        drawEdges(ctx, edges, nodes, spacing, ox, oy, routeSet, time);
      }

      // ── Update & Draw Particles (sparks) ──
      PP.updateParticles(dt * 60, speed);
      drawParticles(ctx, frame, dpr);

      // ── Draw Risk Heatmap Overlay ──
      if (toggles.heatmap) {
        drawHeatmap(ctx, nodeList, risks, spacing, ox, oy);
      }

      // ── Draw Ambulance Coverage ──
      if (toggles.coverage) {
        drawCoverage(ctx, state, nodes, spacing, ox, oy);
      }

      // ── Draw Nodes ──
      drawNodes(ctx, nodeList, risks, spacing, ox, oy, time, hovId, selectedNode, nodeSpringScales);

      // ── Draw hover magnetic effect ──
      if (hovId >= 0) {
        const hn = nodes[String(hovId)];
        if (hn) {
          const hnx = ox + hn.col * spacing;
          const hny = oy + hn.row * spacing;
          drawHoverEffect(ctx, hnx, hny, mx, my, time);
        }
      }

      ctx.restore();
      animRef.current = requestAnimationFrame(render);
    }

    animRef.current = requestAnimationFrame(render);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [booted, selectedNode, viewToggles, simSpeed, state]);

  return (
    <div ref={containerRef} className="canvas-area" style={{ position: 'relative' }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      {booted && <FPSDisplay fpsRef={fpsRef} />}
    </div>
  );
}

// ── FPS overlay (updates via DOM directly, no React re-renders) ──
function FPSDisplay({ fpsRef }) {
  const spanRef = useRef(null);
  useEffect(() => {
    const iv = setInterval(() => {
      if (spanRef.current) spanRef.current.textContent = `${fpsRef.current.fps} FPS`;
    }, 500);
    return () => clearInterval(iv);
  }, [fpsRef]);

  return (
    <span ref={spanRef} className="mono" style={{
      position: 'absolute', top: 8, right: 12, fontSize: 9, color: '#00E5FF88',
      zIndex: 10, pointerEvents: 'none', fontVariantNumeric: 'tabular-nums'
    }}>60 FPS</span>
  );
}

// ═══════════════════════════════════════════════════════════
// DRAWING FUNCTIONS (pure canvas, zero React)
// ═══════════════════════════════════════════════════════════

function drawBackground(bgCanvas, w, h, dpr) {
  const bctx = bgCanvas.getContext('2d');
  bctx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
  bctx.save();
  bctx.scale(dpr, dpr);
  // Draw subtle breathing grid
  bctx.strokeStyle = `rgba(0, 102, 255, 0.05)`;
  bctx.lineWidth = 1;
  for (let x = 0; x <= w; x += 60) {
    bctx.beginPath(); bctx.moveTo(x, 0); bctx.lineTo(x, h); bctx.stroke();
  }
  for (let y = 0; y <= h; y += 60) {
    bctx.beginPath(); bctx.moveTo(0, y); bctx.lineTo(w, y); bctx.stroke();
  }
  bctx.restore();
}

function computeControlPoint(ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const side = ((Math.floor(ax) ^ Math.floor(ay) ^ Math.floor(bx) ^ Math.floor(by)) % 2) === 0 ? 1 : -1;
  const cx = (ax + bx) / 2 - (dy * 0.2 * side);
  const cy = (ay + by) / 2 + (dx * 0.2 * side);
  return { cx, cy };
}

function drawAmbientParticles(ctx, w, h, time) {
  for (let i = 0; i < 30; i++) {
    const seed = i * 123.456;
    const x = ((seed * 11) % w) + Math.sin(time + seed)*20;
    const y = (((seed * 7) + time * 10) % (h + 100)) - 50; 
    const size = (seed % 3) + 1;
    ctx.fillStyle = `rgba(0, 102, 255, ${0.1 + (seed % 20)/100})`;
    ctx.beginPath();
    ctx.arc(x, h - y, size, 0, Math.PI*2);
    ctx.fill();
  }
}

function drawEdges(ctx, edges, nodes, spacing, ox, oy, routeSet, time) {
  for (let i = 0; i < edges.length; i++) {
    const e = edges[i];
    const nA = nodes[String(e.nodeA)];
    const nB = nodes[String(e.nodeB)];
    if (!nA || !nB) continue;

    const ax = ox + nA.col * spacing;
    const ay = oy + nA.row * spacing;
    const bx = ox + nB.col * spacing;
    const by = oy + nB.row * spacing;

    const { cx, cy } = computeControlPoint(ax, ay, bx, by);
    const key = `${Math.min(e.nodeA, e.nodeB)}_${Math.max(e.nodeA, e.nodeB)}`;
    const isRoute = routeSet.has(key);
    const isFlooded = e.blocked;

    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.quadraticCurveTo(cx, cy, bx, by);
    
    if (isFlooded) {
      ctx.strokeStyle = 'rgba(200, 200, 200, 0.4)';
      ctx.setLineDash([8, 8]);
      ctx.lineWidth = 2;
    } else if (isRoute) {
      ctx.strokeStyle = 'rgba(0, 102, 255, 0.6)';
      ctx.setLineDash([]);
      ctx.lineWidth = 4;
      ctx.shadowBlur = 10;
      ctx.shadowColor = 'rgba(0, 102, 255, 0.5)';
    } else {
      ctx.strokeStyle = 'rgba(0, 102, 255, 0.15)';
      ctx.setLineDash([]);
      ctx.lineWidth = 2;
      ctx.shadowBlur = 0;
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
}

function drawParticles(ctx, frame, dpr) {
  const count = PP.getActiveCount();
  for (let i = 0; i < count; i++) {
    if (!PP.pActive[i]) continue;
    
    const sx = PP.pStartX[i];
    const sy = PP.pStartY[i];
    const ex = PP.pEndX[i];
    const ey = PP.pEndY[i];
    const t = PP.pT[i];
    
    const { cx, cy } = computeControlPoint(sx, sy, ex, ey);

    const r = PP.pColorR[i];
    const g = PP.pColorG[i];
    const b = PP.pColorB[i];

    ctx.shadowBlur = 8;
    ctx.shadowColor = `rgb(${r},${g},${b})`;

    for (let j = 0; j <= 5; j++) {
      let pastT = t - j * 0.02;
      if (pastT < 0) pastT += 1;
      const px = Math.pow(1-pastT, 2)*sx + 2*(1-pastT)*pastT*cx + Math.pow(pastT, 2)*ex;
      const py = Math.pow(1-pastT, 2)*sy + 2*(1-pastT)*pastT*cy + Math.pow(pastT, 2)*ey;
      
      ctx.fillStyle = `rgba(${r},${g},${b},${1 - j*0.18})`;
      ctx.beginPath();
      ctx.arc(px, py, 2.5 - j*0.3, 0, Math.PI*2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
  }
}

function drawNodes(ctx, nodeList, risks, spacing, ox, oy, time, hovId, selId, springScalesRef) {
  const buildingSize = spacing * 0.8;

  for (let i = 0; i < nodeList.length; i++) {
    const n = nodeList[i];
    const nx = ox + n.col * spacing;
    const ny = oy + n.row * spacing;
    const isHov = n.id === hovId;
    const isSel = n.id === selId;

    if (!springScalesRef.current[n.id]) {
      springScalesRef.current[n.id] = new Spring(1, 180, 18);
    }
    const spring = springScalesRef.current[n.id];
    spring.setTarget(isSel ? 1.3 : isHov ? 1.25 : 1.0);
    const scale = spring.update(0.016);
    const s = buildingSize * scale;

    ctx.save();
    ctx.translate(nx, ny);
    
    if (isSel || isHov) {
      const gSize = s * 1.5;
      const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, gSize);
      glow.addColorStop(0, 'rgba(0, 212, 255, 0.4)');
      glow.addColorStop(1, 'rgba(0, 212, 255, 0)');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, gSize, 0, Math.PI*2);
      ctx.fill();
    }

    let r1, r2;
    if (n.type === 'RESIDENTIAL') { r1 = '#00D4FF'; r2 = '#0099FF'; }
    else if (n.type === 'HOSPITAL') { r1 = '#10B981'; r2 = '#059669'; }
    else if (n.type === 'SCHOOL') { r1 = '#FFD600'; r2 = '#FFA500'; }
    else if (n.type === 'INDUSTRIAL') { r1 = '#FF8C42'; r2 = '#E67E22'; }
    else if (n.type === 'POWER_PLANT') { r1 = '#FF4757'; r2 = '#FF6B35'; }
    else if (n.type === 'DEPOT') { r1 = '#0066FF'; r2 = '#6366F1'; }
    else { r1 = '#E8F4FF'; r2 = '#B0C4DE'; }

    const risk = risks[String(n.id)] || 'LOW';
    if (risk === 'HIGH') { r1 = '#FF4757'; r2 = '#990000'; }

    ctx.shadowColor = 'rgba(0,102,255,0.2)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetY = 4;
    
    const rad = s/2;
    const grad = ctx.createRadialGradient(-rad*0.3, -rad*0.3, rad*0.1, 0, 0, rad);
    grad.addColorStop(0, '#FFFFFF');
    grad.addColorStop(0.3, r1);
    grad.addColorStop(1, r2);

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(0, 0, rad, 0, Math.PI*2);
    ctx.fill();
    
    ctx.restore();
  }
}

function drawHoverEffect(ctx, nx, ny, mx, my, time) {}

function drawHeatmap(ctx, nodeList, risks, spacing, ox, oy) {
  for (let i = 0; i < nodeList.length; i++) {
    const n = nodeList[i];
    if (n.type === 'EMPTY') continue;
    const risk = risks[String(n.id)];
    if (!risk) continue;
    const nx = ox + n.col * spacing;
    const ny = oy + n.row * spacing;

    let color, alpha;
    if (risk === 'HIGH') { color = '255,71,87'; alpha = 0.4; }
    else if (risk === 'MEDIUM') { color = '255,140,66'; alpha = 0.25; }
    else { color = '16,185,129'; alpha = 0.1; }

    const r = spacing * 1.5;
    const grad = ctx.createRadialGradient(nx, ny, 0, nx, ny, r);
    grad.addColorStop(0, `rgba(${color},${alpha})`);
    grad.addColorStop(1, 'transparent');
    ctx.fillStyle = grad;
    ctx.fillRect(nx - r, ny - r, r * 2, r * 2);
  }
}

function drawCoverage(ctx, state, nodes, spacing, ox, oy) {
  const ambulances = state?.ambulances || [];
  ambulances.forEach((ambId) => {
    const n = nodes[String(ambId)];
    if (!n) return;
    const nx = ox + n.col * spacing;
    const ny = oy + n.row * spacing;
    const coverR = spacing * 3.5;

    ctx.beginPath();
    ctx.arc(nx, ny, coverR, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(16, 185, 129, 0.15)`;
    ctx.fill();
    ctx.strokeStyle = `rgba(16, 185, 129, 0.8)`;
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

function initParticlesFromEdges(edges, nodes, routeSet, spacing, ox, oy) {
  let idx = 0;
  for (let ei = 0; ei < edges.length; ei++) {
    if (idx >= PP.MAX_PARTICLES) break;
    const e = edges[ei];
    const nA = nodes[String(e.nodeA)];
    const nB = nodes[String(e.nodeB)];
    if (!nA || !nB) continue;

    const ax = ox + nA.col * spacing;
    const ay = oy + nA.row * spacing;
    const bx = ox + nB.col * spacing;
    const by = oy + nB.row * spacing;

    const key = `${Math.min(e.nodeA, e.nodeB)}_${Math.max(e.nodeA, e.nodeB)}`;
    const isRoute = routeSet.has(key);
    
    const count = isRoute ? 4 : 1;

    for (let j = 0; j < count; j++) {
      if (idx >= PP.MAX_PARTICLES) break;
      
      let r = 0, g = 212, b = 255;
      if (isRoute) { r = 255; g = 71; b = 87; }
      else if (Math.random() > 0.5) { r = 16; g = 185; b = 129; }
      else if (Math.random() > 0.5) { r = 139; g = 92; b = 246; }

      PP.spawnParticle(
        ax, ay, bx, by,
        0.002 + Math.random() * 0.004,
        2 + Math.random(),
        r, g, b,
        ei,
        0
      );
      idx++;
    }
  }
}

