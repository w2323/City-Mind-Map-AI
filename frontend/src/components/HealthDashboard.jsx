import { useState } from 'react';
import { exportMetrics } from '../api/citymind';

export default function HealthDashboard({ stats, onClose }) {
  const [error, setError] = useState(null);
  if (!stats) return null;
  const cards = [
    ['Connectivity (largest component)', `${stats.connectivityPct}%`],
    [`Residential-sector coverage (cost ≤ ${stats.coverageCostLimit})`, `${stats.coveragePct}%`],
    ['Avg rescue response', `${stats.metrics.avg_response_time} steps`],
    ['Sector crime health index', `${stats.healthPct}%`],
  ];
  const checks = [
    ['Network has no bridges and is connected', stats.twoEdgeConnected],
    ['All sectors reachable', stats.connected],
    [`Coverage ≥ ${stats.config.coverage_target_pct}%`, stats.coveragePct >= stats.config.coverage_target_pct],
    ['Industrial / hospital separation', stats.industrialHospitalSeparation],
  ];
  return <div className="glass-panel" style={{ position: 'fixed', top: 100, right: 40, width: 400, maxHeight: 'calc(100vh - 200px)', padding: 24, zIndex: 1000, overflowY: 'auto' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <h2 style={{ fontSize: 16 }}>NETWORK HEALTH</h2>
      <button onClick={onClose} aria-label="Close dashboard">×</button>
    </div>
    <div className="metrics-grid">
      {cards.map(([label, value]) => <div className="metric-card" key={label}>
        <span className="metric-card__label">{label}</span>
        <span className="metric-card__value">{value}</span>
      </div>)}
    </div>
    <div className="panel__section">
      {checks.map(([label, valid]) => <div key={label} style={{ fontSize: 12, marginBottom: 12 }}>
        {label}: <strong style={{ color: valid ? 'var(--green-alive)' : 'var(--red-alert)' }}>{valid ? 'SATISFIED' : 'UNSATISFIED'}</strong>
      </div>)}
      <p style={{ fontSize: 11 }}>Coverage uses risk-weighted road cost. Crime scores use simulated assets, residential context, and reported incidents.</p>
    </div>
    {error && <p role="alert">{error}</p>}
    <button className="sim-btn sim-btn--secondary" onClick={() => exportMetrics().catch(err => setError(err.message))}>EXPORT METRICS (CSV)</button>
  </div>;
}
