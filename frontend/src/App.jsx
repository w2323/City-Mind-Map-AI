// ═══════════════════════════════════════════════════════════
// CITYMIND — App Shell
// Layout: TopBar + (LeftPanel | Canvas | RightPanel) + BottomBar
// No Framer Motion. No TailwindCSS. Pure React + CSS.
// ═══════════════════════════════════════════════════════════

import { useState, useCallback, useRef, useEffect } from 'react';
import { useSimulation } from './hooks/useSimulation';
import BootSequence from './components/BootSequence';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import GraphCanvas3D from './components/GraphCanvas3D';
import RightPanel from './components/RightPanel';
import HealthDashboard from './components/HealthDashboard';
import EventFeedHUD from './components/EventFeedHUD';
import { getLabelFromNode, getNodeIdFromLabel, runDijkstra, getPath } from './utils/pathfinding';

export default function App() {
  const [booted, setBooted] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dashOpen, setDashOpen] = useState(false);
  const [uiIdle, setUiIdle] = useState(false);
  const [simSpeed, setSimSpeed] = useState(1);
  const [streetView, setStreetView] = useState(false);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(50);
  const [coverageRadius, setCoverageRadius] = useState(5);
  const [placementMode, setPlacementMode] = useState('Current');
  const [roadMode, setRoadMode] = useState('Optimized (2-connected)');
  const [algoMode, setAlgoMode] = useState('Single Algorithm');
  const [gatesNodeLabel, setGatesNodeLabel] = useState('');
  const [gatesNodeId, setGatesNodeId] = useState(null);
  const [gatesPaths, setGatesPaths] = useState([]);
  const [toastMessage, setToastMessage] = useState(null);
  const [godMode, setGodMode] = useState(false);
  
  const [viewToggles, setViewToggles] = useState({
    roads: true,
    coverage: true,
    heatmap: false,
    trails: false,
  });

  const idleTimer = useRef(null);
  const sim = useSimulation();
  const fpsRef = useRef({ frames: 0, lastTime: performance.now(), fps: 60 });

  const resetIdleTimer = useCallback(() => {
    if (!booted) return;
    setUiIdle(false);
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      setUiIdle(true);
    }, 3000);
  }, [booted]);

  useEffect(() => {
    resetIdleTimer();
    window.addEventListener('mousemove', resetIdleTimer);
    window.addEventListener('mousedown', resetIdleTimer);
    window.addEventListener('keydown', resetIdleTimer);
    window.addEventListener('wheel', resetIdleTimer);
    return () => {
      window.removeEventListener('mousemove', resetIdleTimer);
      window.removeEventListener('mousedown', resetIdleTimer);
      window.removeEventListener('keydown', resetIdleTimer);
      window.removeEventListener('wheel', resetIdleTimer);
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [resetIdleTimer]);

  const handleBootComplete = useCallback(() => {
    setBooted(true);
  }, []);

  const handleToggleView = useCallback((key) => {
    setViewToggles(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleSelectNode = useCallback((nodeId) => {
    if (godMode) {
      sim.handleFloodNode(nodeId);
      return;
    }
    setSelectedNode(nodeId);
    setDrawerOpen(false); // Auto-close left drawer when selecting a node
  }, [godMode, sim]);

  // ── Gates of Death Logic ──
  useEffect(() => {
    if (!booted || !sim.graph?.nodes || !sim.stats?.edgeList) return;
    
    // Clear paths/toasts by default
    setGatesPaths([]);
    setToastMessage(null);

    const targetId = getNodeIdFromLabel(gatesNodeLabel, sim.graph.nodes);
    setGatesNodeId(targetId);

    if (targetId === null) return;
    
    const ambulances = sim.state?.ambulances || [];
    if (ambulances.length === 0) return;

    if (placementMode === 'Optimizing...') {
      // Find closest ambulance
      let bestAmb = null;
      let minDistance = Infinity;
      
      for (const amb of ambulances) {
        const { dist } = runDijkstra(sim.graph.nodes, sim.stats.edgeList, amb);
        if (dist[targetId] < minDistance) {
          minDistance = dist[targetId];
          bestAmb = amb;
        }
      }
      
      if (bestAmb !== null) {
        const ambLabel = getLabelFromNode(sim.graph.nodes[bestAmb]);
        const targetLabel = getLabelFromNode(sim.graph.nodes[targetId]);
        setToastMessage(`🚨 ${ambLabel} is the most optimized ambulance when gates of death are unleashed to ${targetLabel}!`);
      }
    } else if (placementMode === 'Best found') {
      let bestAmb = null;
      let minDistance = Infinity;
      let bestPrev = null;
      
      for (const amb of ambulances) {
        const { dist, prev } = runDijkstra(sim.graph.nodes, sim.stats.edgeList, amb);
        if (dist[targetId] < minDistance) {
          minDistance = dist[targetId];
          bestAmb = amb;
          bestPrev = prev;
        }
      }
      
      if (bestAmb !== null && bestPrev !== null) {
        const path = getPath(bestPrev, targetId);
        setGatesPaths([{ color: '#00ffff', path }]);
      }
    } else if (placementMode === 'All candidates') {
      const allPaths = [];
      const colors = ['#ff00ff', '#00ffff', '#ffff00', '#ff8800', '#00ff88'];
      
      ambulances.forEach((amb, i) => {
        const { prev } = runDijkstra(sim.graph.nodes, sim.stats.edgeList, amb);
        const path = getPath(prev, targetId);
        if (path.length > 0) {
          allPaths.push({ color: colors[i % colors.length], path });
        }
      });
      setGatesPaths(allPaths);
    }
  }, [placementMode, gatesNodeLabel, sim.graph, sim.stats, sim.state, booted]);

  // ── Error State ──
  if (sim.error && !sim.state) {
    return (
      <div className="app-shell" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="glass-panel" style={{ padding: 32, borderRadius: 12, textAlign: 'center', maxWidth: 400 }}>
          <div className="mono" style={{ fontSize: 14, color: 'var(--accent-red)', marginBottom: 12, fontWeight: 600 }}>
            CONNECTION ERROR
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>
            {sim.error}
          </p>
          <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 16 }}>
            Make sure the backend is running: <code className="mono" style={{ color: 'var(--accent-cyan)' }}>uvicorn backend.api.main:app</code>
          </p>
          <button className="sim-btn sim-btn--primary" onClick={sim.loadData} style={{ maxWidth: 200, margin: '0 auto' }}>
            RETRY CONNECTION
          </button>
        </div>
      </div>
    );
  }

  // ── Boot Screen ──
  if (!booted || sim.loading) {
    return (
      <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
        {sim.loading && !booted && (
          <div style={{ position: 'fixed', inset: 0, zIndex: 99, background: '#020204' }} />
        )}
        {!sim.loading && !booted && (
          <BootSequence onComplete={handleBootComplete} />
        )}
        {sim.loading && (
          <div className="mono" style={{
            position: 'fixed', bottom: 24, left: 24, fontSize: 10,
            color: 'var(--text-tertiary)', zIndex: 101
          }}>
            CITYMIND OS — CONNECTING TO BACKEND...
          </div>
        )}
      </div>
    );
  }

  // ── Main Dashboard ──
  const renderCanvas = (overrideProps = {}) => (
    <GraphCanvas3D
      graph={sim.graph}
      state={sim.state}
      stats={sim.stats}
      booted={booted}
      selectedNode={selectedNode}
      onSelectNode={handleSelectNode}
      viewToggles={viewToggles}
      simSpeed={simSpeed}
      fpsRef={fpsRef}
      streetView={streetView}
      resetTrigger={resetTrigger}
      onZoomChange={setZoomLevel}
      coverageRadius={coverageRadius}
      placementMode={placementMode}
      roadMode={roadMode}
      gatesNodeId={gatesNodeId}
      gatesPaths={gatesPaths}
      godMode={godMode}
      {...overrideProps}
    />
  );

  return (
    <div className="app-shell">
      {/* Central Canvas (Hero Element) */}
      <div className="canvas-area">
        {algoMode === 'Single Algorithm' && renderCanvas()}
        {algoMode === 'Side-by-side Comparison' && (
          <div style={{ display: 'flex', width: '100%', height: '100%' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <div style={{ position: 'absolute', top: 80, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>MODE: All Roads</div>
              {renderCanvas({ roadMode: 'All roads' })}
            </div>
            <div style={{ width: 2, background: 'var(--accent-cyan)', zIndex: 10 }} />
            <div style={{ flex: 1, position: 'relative' }}>
              <div style={{ position: 'absolute', top: 80, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>MODE: {roadMode}</div>
              {renderCanvas()}
            </div>
          </div>
        )}
        {algoMode === 'Multi-view' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr', width: '100%', height: '100%' }}>
            <div style={{ position: 'relative', borderRight: '1px solid var(--accent-cyan)', borderBottom: '1px solid var(--accent-cyan)' }}>
              <div style={{ position: 'absolute', top: 80, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>All Roads</div>
              {renderCanvas({ roadMode: 'All roads' })}
            </div>
            <div style={{ position: 'relative', borderBottom: '1px solid var(--accent-cyan)' }}>
              <div style={{ position: 'absolute', top: 80, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>MST Optimized</div>
              {renderCanvas({ roadMode: 'Optimized (MST)' })}
            </div>
            <div style={{ position: 'relative', borderRight: '1px solid var(--accent-cyan)' }}>
              <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>2-Connected</div>
              {renderCanvas({ roadMode: 'Optimized (2-connected)' })}
            </div>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 10, padding: '4px 8px', background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12, borderRadius: 4, fontFamily: 'monospace' }}>Ambulance Optimized</div>
              {renderCanvas({ placementMode: 'Best found', roadMode: 'Optimized (2-connected)' })}
            </div>
          </div>
        )}
        {booted && <Shockwave />}
      </div>

      {/* Live Event Feed HUD */}
      {booted && <EventFeedHUD events={sim.stats?.events} />}

      {/* God Mode Toggle Button */}
      {booted && (
        <button
          onClick={() => setGodMode(p => !p)}
          style={{
            position: 'fixed', bottom: 24, left: 320, // next to left panel
            background: godMode ? 'rgba(255, 0, 85, 0.2)' : 'rgba(0, 255, 255, 0.1)',
            border: `1px solid ${godMode ? 'var(--red-alert)' : 'var(--accent-cyan)'}`,
            padding: '8px 16px', borderRadius: 8, color: '#fff',
            fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600,
            cursor: 'pointer', zIndex: 100, transition: 'all 0.2s',
            boxShadow: godMode ? '0 0 15px rgba(255, 0, 85, 0.4)' : 'none',
          }}
        >
          {godMode ? '🌊 GOD MODE: ACTIVE (Click nodes to flood)' : '⚡ ACTIVATE GOD MODE'}
        </button>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div style={{
          position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(20, 10, 30, 0.85)', border: '1px solid var(--accent-cyan)',
          padding: '12px 24px', borderRadius: '8px', zIndex: 100,
          color: '#fff', fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
          boxShadow: '0 0 20px rgba(0, 255, 255, 0.3)',
          animation: 'fade-in 0.3s ease-out'
        }}>
          {toastMessage}
        </div>
      )}

      {/* Floating Top Nav Bar */}
      <TopBar stats={sim.stats} connected={sim.connected} fpsRef={fpsRef} className={uiIdle ? 'ui-hidden' : ''} onToggleDash={() => setDashOpen(!dashOpen)} />

      {/* Health Dashboard */}
      {dashOpen && <HealthDashboard stats={sim.stats} onClose={() => setDashOpen(false)} />}

      {/* Floating Left Widget (Slide Drawer) */}
      <LeftPanel
        drawerOpen={drawerOpen}
        onToggle={() => setDrawerOpen(p => !p)}
        stats={sim.stats}
        viewToggles={viewToggles}
        onToggleView={handleToggleView}
        onStart={sim.handleStart}
        onStep={sim.handleStep}
        starting={sim.starting}
        stepping={sim.stepping}
        simSpeed={simSpeed}
        onSpeedChange={setSimSpeed}
        placementMode={placementMode}
        onPlacementModeChange={setPlacementMode}
        roadMode={roadMode}
        onRoadModeChange={setRoadMode}
        gatesNodeLabel={gatesNodeLabel}
        onGatesNodeChange={setGatesNodeLabel}
        algoMode={algoMode}
        onAlgoModeChange={setAlgoMode}
        coverageRadius={coverageRadius}
        onCoverageRadiusChange={setCoverageRadius}
        streetView={streetView}
        onToggleStreetView={() => setStreetView(s => !s)}
        onResetView={() => setResetTrigger(t => t + 1)}
      />

      {/* Floating Right Inspector */}
      <RightPanel
        selectedNode={selectedNode}
        graph={sim.graph}
        state={sim.state}
        stats={sim.stats}
        onClose={() => setSelectedNode(null)}
      />

      {/* Zoom Indicator */}
      <div className={`zoom-controls ${uiIdle ? 'ui-hidden' : ''}`}>
        <div className="zoom-controls__text">{zoomLevel.toFixed(1)}x</div>
        <button className="zoom-controls__btn" onClick={() => setResetTrigger(t => t + 1)} title="Center View">🎯</button>
      </div>

    </div>
  );
}

// ── Boot shockwave (one-shot animation) ──
function Shockwave() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute', top: '50%', left: '50%',
        width: 200, height: 200,
        transform: 'translate(-50%, -50%)',
        borderRadius: '50%',
        border: '1px solid var(--accent-cyan)',
        pointerEvents: 'none',
        zIndex: 5,
        animation: 'shockwave 1.5s ease-out forwards',
      }}
      onAnimationEnd={() => setVisible(false)}
    />
  );
}
