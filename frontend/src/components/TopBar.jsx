// ═══════════════════════════════════════════════════════════
// CITYMIND — Top Bar (48px)
// Logo, live status, step counter, FPS
// ═══════════════════════════════════════════════════════════

export default function TopBar({ stats, connected, fpsRef, className, onToggleDash }) {
  const step = stats?.step ?? 0;
  const max = stats?.maxSteps ?? 0;
  const total = stats?.totalNodes ?? 0;
  const incidents = (stats?.disasters?.gates?.length || 0) + (stats?.disasters?.fully_blocked_roads || 0);
  const done = stats?.isComplete;

  return (
    <header className={`top-bar ${className || ''}`}>
      {/* Left: Logo */}
      <span className="top-bar__logo">CITYMIND</span>

      {/* Center: Live status */}
      <div className="top-bar__status">
        <div className="top-bar__status-item">
          <div className={`top-bar__live-dot ${!connected ? 'top-bar__live-dot--offline' : ''}`} />
          <span style={{ color: connected ? 'var(--green-alive)' : 'var(--red-alert)', fontWeight: 700 }}>
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        <span className="top-bar__status-item">{total} sectors</span>
        <span className="top-bar__status-item">
          <span style={{ color: incidents > 0 ? 'var(--orange-warm)' : 'var(--text-secondary)' }}>
            {incidents} incidents
          </span>
        </span>
        {done && (
          <span className="top-bar__status-item" style={{ color: 'var(--green-alive)' }}>✓ COMPLETE</span>
        )}
      </div>

      {/* Right: Step + Progress */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <button onClick={onToggleDash} className="sim-btn sim-btn--secondary" style={{ padding: '6px 12px', marginRight: 16 }}>
          📊 DASHBOARD
        </button>
        <div style={{ fontSize: 12, fontWeight: 600 }}>
          <span style={{ color: 'var(--text-tertiary)' }}>STEP </span>
          <span className="tabular-nums" style={{ color: 'var(--blue-vibrant)' }}>{step}</span>
          <span style={{ color: 'var(--text-tertiary)' }}> / {max}</span>
        </div>
        <div style={{ width: 100, height: 4, borderRadius: 2, background: 'rgba(0,0,0,0.1)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 2, background: 'var(--blue-vibrant)',
            width: `${max > 0 ? (step / max) * 100 : 0}%`,
            transition: 'width 0.4s cubic-bezier(0.34, 1.1, 0.64, 1)'
          }} />
        </div>
      </div>
    </header>
  );
}
