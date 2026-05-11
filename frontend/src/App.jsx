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
    setSelectedNode(nodeId);
    setDrawerOpen(false); // Auto-close left drawer when selecting a node
  }, []);

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
  return (
    <div className="app-shell">
      {/* Central Canvas (Hero Element) */}
      <div className="canvas-area">
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
        />
        {booted && <Shockwave />}
      </div>

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

      {/* Floating Bottom Control Bar with Event Scrubber */}
      <div className={`bottom-bar ${uiIdle ? 'ui-hidden' : ''}`} style={{ width: '90%', display: 'flex', flexDirection: 'column', height: 'auto', padding: '12px 28px', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div className="bottom-bar__section">
            <span style={{ fontWeight: 700, background: 'linear-gradient(90deg, #0066FF, #8B5CF6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              CITYMIND v3.0
            </span>
            <span style={{ color: 'rgba(0,0,0,0.1)' }}>|</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>Immersive Dashboard</span>
          </div>
          <div className="bottom-bar__section">
            <button 
              className={`sim-btn ${streetView ? 'sim-btn--primary' : 'sim-btn--secondary'}`} 
              style={{ padding: '4px 12px', fontSize: 11, marginRight: '8px' }}
              onClick={() => setStreetView(s => !s)}
            >
              {streetView ? 'EXIT STREET VIEW' : 'STREET LEVEL'}
            </button>
            <button 
              className="sim-btn sim-btn--secondary" 
              style={{ padding: '4px 12px', fontSize: 11 }}
              onClick={() => setResetTrigger(t => t + 1)}
            >
              RESET VIEW
            </button>
            <span style={{ color: 'rgba(0,0,0,0.1)', marginLeft: '8px' }}>|</span>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{sim.stats?.totalNodes || 0} nodes / {sim.stats?.edgeList?.length || 0} edges</span>
            <span style={{ color: 'rgba(0,0,0,0.1)' }}>|</span>
            <span style={{ fontSize: 12, fontWeight: 600 }}>Speed: {simSpeed}x</span>
          </div>
        </div>
        
        {/* Timeline Scrubber */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', marginTop: 4, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.05)' }}>
          <button className="sim-btn sim-btn--icon" style={{ width: 28, height: 28, fontSize: 12 }} title="Start">⏮</button>
          <button className="sim-btn sim-btn--icon" style={{ width: 28, height: 28, fontSize: 12 }} title="Rewind 10s">⏪</button>
          <button className="sim-btn sim-btn--icon" style={{ width: 32, height: 32, fontSize: 14 }} title="Play">▶</button>
          <button className="sim-btn sim-btn--icon" style={{ width: 28, height: 28, fontSize: 12 }} title="Forward 10s">⏩</button>
          <button className="sim-btn sim-btn--icon" style={{ width: 28, height: 28, fontSize: 12 }} title="End">⏭</button>
          <input type="range" min="0" max="20" value={sim.stats?.step || 0} readOnly style={{ flex: 1, accentColor: 'var(--purple-pop)' }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', minWidth: 60 }}>STEP {sim.stats?.step || 0}/20</span>
        </div>
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
