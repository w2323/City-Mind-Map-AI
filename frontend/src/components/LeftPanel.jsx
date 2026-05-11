import { useRef, useState } from 'react';

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
  simSpeed, onSpeedChange
}) {
  const [threadState, setThreadState] = useState('idle');
  const [threadCount, setThreadCount] = useState(5);
  const [roadMode, setRoadMode] = useState('All roads');
  const [algoMode, setAlgoMode] = useState('Single Algorithm');
  const [placementMode, setPlacementMode] = useState('Current');
  const [coverageRadius, setCoverageRadius] = useState(5);

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
                  <input type="range" min="1" max="10" value={coverageRadius} onChange={e => setCoverageRadius(e.target.value)} style={{ flex: 1 }} />
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
            <select value={algoMode} onChange={e => setAlgoMode(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
              <option>Single Algorithm</option>
              <option>Side-by-side Comparison</option>
              <option>Multi-view</option>
            </select>
          </div>

          {/* OPTIMIZATION (GA) */}
          <div className="panel__section">
            <div className="panel__title">THREAD OPTIMIZATION (GA)</div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button className="sim-btn sim-btn--primary" style={{flex: 1}} onClick={() => setThreadState('running')}>Start</button>
              <button className="sim-btn sim-btn--secondary" onClick={() => setThreadState('paused')}>Pause</button>
              <button className="sim-btn sim-btn--secondary" onClick={() => setThreadState('idle')}>Reset</button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>THREADS</span>
              <input type="number" min="1" max="50" value={threadCount} onChange={e => setThreadCount(e.target.value)} style={{ width: 40, background: 'transparent', border: '1px solid rgba(0,0,0,0.1)', borderRadius: 4, padding: '2px 4px', fontSize: 11, outline: 'none' }} />
            </div>
            {threadState === 'running' && (
              <div style={{ padding: 8, background: 'rgba(0,102,255,0.05)', borderRadius: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 4 }}>
                  <span style={{ fontWeight: 700, color: 'var(--blue-vibrant)' }}>Thread 3 / {threadCount}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>Gen: 45</span>
                </div>
                <div style={{ width: '100%', height: 4, background: 'rgba(0,0,0,0.1)', borderRadius: 2 }}>
                  <div style={{ width: '60%', height: '100%', background: 'var(--blue-vibrant)', borderRadius: 2 }} />
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>Best Fitness: 0.892</div>
              </div>
            )}
          </div>

          {/* ROAD NETWORK MODE */}
          <div className="panel__section">
            <div className="panel__title">ROAD NETWORK</div>
            <select value={roadMode} onChange={e => setRoadMode(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
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

          {/* AMBULANCE PLACEMENT */}
          <div className="panel__section">
            <div className="panel__title">AMBULANCE PLACEMENT</div>
            <select value={placementMode} onChange={e => setPlacementMode(e.target.value)} style={{ width: '100%', padding: 6, borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)', fontSize: 11, marginBottom: 8, outline: 'none' }}>
              <option>Current</option>
              <option>Optimizing...</option>
              <option>Best found</option>
              <option>All candidates</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)' }}>
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
