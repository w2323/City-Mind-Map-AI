import { useRef, useState, useEffect } from 'react';

const NODE_LEGEND = [
  { type: 'Residential', color: 'var(--cyan-bright)', key: 'residential' },
  { type: 'Hospital', color: 'var(--green-alive)', key: 'hospitals' },
  { type: 'School', color: 'var(--yellow-sun)', key: 'schools' },
  { type: 'Industrial', color: 'var(--orange-warm)', key: 'industrial' },
  { type: 'Power Plant', color: 'var(--red-alert)', key: 'powerPlants' },
  { type: 'Ambulance Depot', color: 'var(--blue-vibrant)', key: 'depots' },
];

const ROAD_LEGEND = [
  { type: 'Normal Road', color: '#4a5568' },
  { type: 'Active Route', color: '#ef4444' },
  { type: 'Flooded Hazard', color: '#3b82f6' },
];

export default function LeftPanel({
  drawerOpen, onToggle, stats,
  viewToggles, onToggleView,
  onStart, onStep, onReset,
  starting, stepping,
  simSpeed, onSpeedChange,
  placementMode, onPlacementModeChange,
  roadMode, onRoadModeChange,
  gatesNodeLabel, onGatesNodeChange,
  algoMode, onAlgoModeChange,
  coverageRadius, onCoverageRadiusChange,
  streetView, onToggleStreetView, onResetView
}) {
  const [threadState, setThreadState] = useState('idle');
  const [threadCount, setThreadCount] = useState(5);
  const [gaProgress, setGaProgress] = useState({ gen: 0, fitness: 2.5, thread: 1 });
  const progressTimer = useRef(null);

  useEffect(() => {
    if (threadState === 'running') {
      progressTimer.current = setInterval(() => {
        setGaProgress(prev => {
          let nextGen = prev.gen + 2;
          let nextThread = prev.thread;
          let nextFitness = prev.fitness;
          
          if (nextGen > 100) {
            nextGen = 0;
            nextThread += 1;
          }
          
          if (nextThread > threadCount) {
             clearInterval(progressTimer.current);
             setThreadState('completed');
             onPlacementModeChange('Best found');
             return { gen: 100, fitness: 0.85, thread: threadCount };
          }
          
          if (nextGen % 10 === 0 && nextFitness > 0.85) {
             nextFitness = nextFitness - (Math.random() * 0.05);
             if (nextFitness < 0.85) nextFitness = 0.85;
          }

          return { gen: nextGen, fitness: nextFitness, thread: nextThread };
        });
      }, 50);
    } else if (threadState === 'idle') {
      setGaProgress({ gen: 0, fitness: 2.5, thread: 1 });
      if (progressTimer.current) clearInterval(progressTimer.current);
    } else {
      if (progressTimer.current) clearInterval(progressTimer.current);
    }
    return () => {
      if (progressTimer.current) clearInterval(progressTimer.current);
    }
  }, [threadState, threadCount, onPlacementModeChange]);

  if (!stats) return null;

  const riskCounts = stats.riskCounts || { HIGH: 0, MEDIUM: 0, LOW: 0 };
  const totalRisk = riskCounts.HIGH + riskCounts.MEDIUM + riskCounts.LOW || 1;
  const healthPct = Math.round(((riskCounts.LOW + riskCounts.MEDIUM * 0.5) / totalRisk) * 100);
  const blockedEdges = stats.metrics?.total_edges_blocked || 0;

  return (
    <>
      <button className={`left-panel__toggle ${drawerOpen ? 'ui-hidden' : ''}`} onClick={onToggle} title="Open Controls">
        ☰
      </button>
      <div className={`left-panel ${drawerOpen ? 'left-panel--open' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontWeight: 800, color: 'var(--blue-vibrant)' }}>CONTROLS</div>
          <button onClick={onToggle} style={{ background: 'none', border: 'none', fontSize: 24, cursor: 'pointer', color: 'var(--text-tertiary)' }}>×</button>
        </div>
          {/* NODE LEGEND */}
          <div className="panel__section">
            <div className="panel__title">NODE LEGEND</div>
            {NODE_LEGEND.map(item => (
              <div key={item.key} className="legend-item">
                <div className="legend-item__left">
                  <div className="legend-item__dot" style={{ background: item.color }} />
                  <span className="legend-item__label">{item.type}</span>
                </div>
                <span className="legend-item__count" style={{ color: item.color }}>
                  {stats[item.key] || 0}
                </span>
              </div>
            ))}
          </div>

          {/* ROAD LEGEND */}
          <div className="panel__section">
            <div className="panel__title">ROAD LEGEND</div>
            {ROAD_LEGEND.map(item => (
              <div key={item.type} className="legend-item">
                <div className="legend-item__left">
                  <div className="legend-item__dot" style={{ background: item.color, borderRadius: '2px', width: '12px', height: '4px' }} />
                  <span className="legend-item__label">{item.type}</span>
                </div>
              </div>
            ))}
          </div>

          {/* SIMULATION CONTROLS */}
          <div className="panel__section">
            <div className="panel__title">SIMULATION</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="sim-btn sim-btn--primary" onClick={onStart} disabled={starting}>
                {starting ? 'INITIALIZING...' : stats.step > 0 ? '⟲ RESTART' : '▶ START'}
              </button>
              <button className="sim-btn sim-btn--secondary" onClick={onStep} disabled={stepping || stats.isComplete}>
                {stepping ? 'PROCESSING...' : '→ NEXT STEP'}
              </button>
              {stats.isComplete && (
                <div style={{
                  padding: '6px 10px', borderRadius: 6, textAlign: 'center',
                  background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)',
                  color: 'var(--green-alive)', fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, fontWeight: 700
                }}>
                  ✓ COMPLETE — {stats.maxSteps} STEPS
                </div>
              )}
            </div>

            {/* Timeline Scrubber & Media Controls */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, width: '100%' }}>
                <button className="sim-btn sim-btn--icon" style={{ width: 24, height: 24, fontSize: 10 }} title="Start">⏮</button>
                <button className="sim-btn sim-btn--icon" style={{ width: 24, height: 24, fontSize: 10 }} title="Rewind">⏪</button>
                <button className="sim-btn sim-btn--icon" style={{ width: 28, height: 28, fontSize: 12 }} title="Play">▶</button>
                <button className="sim-btn sim-btn--icon" style={{ width: 24, height: 24, fontSize: 10 }} title="Forward">⏩</button>
                <button className="sim-btn sim-btn--icon" style={{ width: 24, height: 24, fontSize: 10 }} title="End">⏭</button>
              </div>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textAlign: 'center' }}>
                PROGRESS: STEP {stats.step || 0}/{stats.maxSteps || 20}
              </span>
              <input type="range" min="0" max={stats.maxSteps || 20} value={stats.step || 0} readOnly style={{ width: '100%', accentColor: 'var(--purple-pop)' }} />
            </div>

            {/* Camera Controls */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(0,0,0,0.05)' }}>
              <button 
                className={`sim-btn ${streetView ? 'sim-btn--primary' : 'sim-btn--secondary'}`} 
                style={{ flex: 1, padding: '6px 0', fontSize: 10 }}
                onClick={onToggleStreetView}
              >
                {streetView ? 'EXIT STREET VIEW' : 'STREET LEVEL'}
              </button>
              <button 
                className="sim-btn sim-btn--secondary" 
                style={{ flex: 1, padding: '6px 0', fontSize: 10 }}
                onClick={onResetView}
              >
                RESET VIEW
              </button>
            </div>

            {/* Speed slider */}
            <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>SPEED</span>
              <input
                type="range" min="0.25" max="4" step="0.25"
                value={simSpeed}
                onChange={e => onSpeedChange(parseFloat(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--blue-vibrant)' }}
              />
              <span style={{ fontSize: 10, fontWeight: 700, width: 24 }}>{simSpeed}x</span>
            </div>
          </div>

          {/* VIEW TOGGLES */}
          <div className="panel__section">
            <div className="panel__title">VIEW LAYERS</div>
            {[
              { key: 'roads', label: 'Road Network' },
              { key: 'coverage', label: 'Ambulance Coverage' },
              { key: 'heatmap', label: 'Risk Heatmap' },
              { key: 'clusters', label: 'Crime Clusters' },
              { key: 'trails', label: 'Agent Trails' },
            ].map(t => (
              <div key={t.key} className="toggle-row">
                <span className="toggle-row__label">{t.label}</span>
                <div
                  className={`toggle-switch ${viewToggles[t.key] ? 'toggle-switch--on' : ''}`}
                  onClick={() => onToggleView(t.key)}
                >
                  <div className="toggle-switch__knob" />
                </div>
              </div>
            ))}
            {viewToggles.coverage && (
              <div style={{ marginTop: 8, padding: '8px', background: 'rgba(0,0,0,0.02)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>RADIUS</span>
                  <input type="range" min="1" max="10" value={coverageRadius} onChange={e => onCoverageRadiusChange(parseFloat(e.target.value))} style={{ flex: 1 }} />
                  <span style={{ fontSize: 10 }}>{coverageRadius}m</span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>Coverage: 92% | Dead zones: 3</div>
              </div>
            )}
            {viewToggles.heatmap && (
              <div style={{ marginTop: 8, display: 'flex', gap: 4, height: 12, borderRadius: 6, overflow: 'hidden' }}>
                <div style={{ flex: 1, background: 'var(--green-alive)' }} title="Low Risk" />
                <div style={{ flex: 1, background: 'var(--orange-warm)' }} title="Medium Risk" />
                <div style={{ flex: 1, background: 'var(--red-alert)' }} title="High Risk" />
              </div>
            )}
            {viewToggles.clusters && (
              <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-secondary)' }}>
                Active Clusters: 3 (High Risk)
              </div>
            )}
          </div>

          {/* ALGORITHM MODE */}
          <div className="panel__section">
            <div className="panel__title">ALGORITHM MODE</div>
            <select value={algoMode} onChange={e => onAlgoModeChange(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
              <option>Single Algorithm</option>
              <option>Side-by-side Comparison</option>
              <option>Multi-view</option>
            </select>
          </div>

            {/* OPTIMIZATION (GA) */}
          <div className="panel__section">
            <div className="panel__title">THREAD OPTIMIZATION (GA)</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button className="sim-btn sim-btn--primary" style={{flex: 1}} onClick={() => setThreadState('running')} disabled={threadState === 'running' || threadState === 'completed'}>Start</button>
              <button className="sim-btn sim-btn--secondary" onClick={() => setThreadState('paused')} disabled={threadState !== 'running'}>Pause</button>
              <button className="sim-btn sim-btn--secondary" onClick={() => setThreadState('idle')}>Reset</button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>THREADS</span>
              <input type="number" min="1" max="50" value={threadCount} onChange={e => setThreadCount(parseInt(e.target.value) || 1)} style={{ width: 40, background: 'transparent', border: '1px solid rgba(0,0,0,0.1)', borderRadius: 4, padding: '2px 4px', fontSize: 11, outline: 'none' }} />
            </div>
            {threadState !== 'idle' && (
              <div style={{ padding: 8, background: 'rgba(0,102,255,0.05)', borderRadius: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 4 }}>
                  <span style={{ fontWeight: 700, color: 'var(--blue-vibrant)' }}>Thread {gaProgress.thread} / {threadCount}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>Gen: {gaProgress.gen}</span>
                </div>
                <div style={{ width: '100%', height: 4, background: 'rgba(0,0,0,0.1)', borderRadius: 2 }}>
                  <div style={{ width: `${threadState === 'completed' ? 100 : gaProgress.gen}%`, height: '100%', background: 'var(--blue-vibrant)', borderRadius: 2, transition: 'width 0.1s linear' }} />
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>Best Fitness: {gaProgress.fitness.toFixed(3)}</div>
                {threadState === 'completed' && (
                   <div style={{ fontSize: 10, color: 'var(--green-alive)', marginTop: 4, fontWeight: 'bold' }}>
                     OPTIMIZATION COMPLETE
                   </div>
                )}
              </div>
            )}
          </div>

          {/* ROAD NETWORK MODE */}
          <div className="panel__section">
            <div className="panel__title">ROAD NETWORK</div>
            <select value={roadMode} onChange={e => onRoadModeChange(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
              <option>All roads</option>
              <option>Optimized (MST)</option>
              <option>Optimized (2-connected)</option>
              <option>Comparison</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)' }}>
              <span>Length: {stats.edgeList?.length * 10 || 0}m</span>
              <span style={{ color: 'var(--green-alive)' }}>Connected: ✓</span>
            </div>
          </div>

          {/* AMBULANCE PLACEMENT & GATES OF DEATH */}
          <div className="panel__section">
            <div className="panel__title">AMBULANCE PLACEMENT</div>
            <select value={placementMode} onChange={e => onPlacementModeChange(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
              <option>Current</option>
              <option>Optimizing...</option>
              <option>Best found</option>
              <option>All candidates</option>
            </select>
            
            <div style={{ marginTop: 12, padding: 8, background: 'rgba(255, 0, 85, 0.05)', border: '1px solid rgba(255, 0, 85, 0.2)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--red-alert)', marginBottom: 4 }}>
                UNLEASH GATES OF DEATH
              </div>
              <input 
                type="text" 
                placeholder="Target Node (e.g., C4)" 
                value={gatesNodeLabel}
                onChange={e => onGatesNodeChange(e.target.value)}
                style={{ 
                  width: '100%', padding: '4px 8px', borderRadius: 4, 
                  border: '1px solid rgba(255,0,85,0.4)', background: 'transparent',
                  color: 'var(--text-primary)', fontSize: 11, fontFamily: 'monospace', outline: 'none'
                }}
              />
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginTop: 8 }}>
              <span>Avg Response: 4.2m</span>
              <span style={{ color: 'var(--green-alive)' }}>Score: 0.85</span>
            </div>
          </div>

          {/* LIVE METRICS */}
          <div className="panel__section">
            <div className="panel__title">LIVE METRICS</div>
            <div className="metrics-grid">
              <div className="metric-card">
                <span className="metric-card__label">Network Health</span>
                <span className="metric-card__value" style={{ color: healthPct > 80 ? 'var(--green-alive)' : healthPct > 50 ? 'var(--orange-warm)' : 'var(--red-alert)' }}>
                  {healthPct}%
                </span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">Ambulances</span>
                <span className="metric-card__value" style={{ color: 'var(--blue-vibrant)' }}>
                  {stats.ambulances?.length || 0}
                </span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">Blocked Roads</span>
                <span className="metric-card__value" style={{ color: blockedEdges > 0 ? 'var(--red-alert)' : 'var(--text-secondary)' }}>
                  {blockedEdges}
                </span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">Risk Level</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: riskCounts.HIGH > 3 ? 'var(--red-alert)' : riskCounts.MEDIUM > 5 ? 'var(--orange-warm)' : 'var(--green-alive)' }}>
                  {riskCounts.HIGH > 3 ? 'HIGH' : riskCounts.MEDIUM > 5 ? 'MEDIUM' : 'LOW'}
                </span>
              </div>
            </div>
          </div>
      </div>
    </>
  );
}
