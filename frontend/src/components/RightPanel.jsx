import { useEffect, useRef } from 'react';

const NODE_NAMES = {
  RESIDENTIAL: 'Residential Zone',
  HOSPITAL: 'Medical Center',
  SCHOOL: 'Education Complex',
  INDUSTRIAL: 'Industrial District',
  POWER_PLANT: 'Power Station',
  DEPOT: 'Ambulance Depot',
};

export default function RightPanel({ selectedNode, graph, state, stats, onClose }) {
  const isOpen = selectedNode !== null;
  const node = isOpen ? graph?.nodes?.[String(selectedNode)] : null;
  const risk = state?.risk_predictions?.[String(selectedNode)] || 'LOW';
  const ambulances = state?.ambulances || [];
  const police = (state?.police_deployments || []).map(p => p.node_id);
  const events = stats?.events || [];
  const logRef = useRef(null);

  // Auto-scroll event log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = 0;
  }, [events.length]);

  if (!node) {
    return <div className={`right-panel ${isOpen ? 'right-panel--open' : ''}`} />;
  }

  const type = node.node_type || 'EMPTY';
  const typeName = NODE_NAMES[type] || type;
  const isAmb = ambulances.includes(selectedNode);
  const isPol = police.includes(selectedNode);

  return (
    <div className={`right-panel ${isOpen ? 'right-panel--open' : ''}`}>
      {/* Header */}
      <div style={{ padding: 20, borderBottom: '1px solid rgba(0,0,0,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="panel__title" style={{ marginBottom: 4, color: 'var(--blue-vibrant)' }}>Node {node.label || selectedNode} — {typeName}</div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Grid Ref: {node.label} ({node.row}, {node.col})</div>
        </div>
        <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: '50%', border: 'none', background: 'rgba(0,0,0,0.05)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 16, fontWeight: 'bold' }}>×</button>
      </div>

      {/* Metrics */}
      <div className="panel__section" style={{ padding: 20 }}>
        <div className="panel__title">REAL-TIME METRICS</div>
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-card__label">Population</span>
            <span className="metric-card__value" style={{ color: 'var(--text-primary)' }}>
              {Math.floor((node.population_density || 0) * 10000).toLocaleString()}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Risk Level</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: risk === 'HIGH' ? 'var(--red-alert)' : risk === 'MEDIUM' ? 'var(--orange-warm)' : 'var(--green-alive)' }}>{risk}</span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Accessible</span>
            <span className="metric-card__value" style={{ color: node.accessible !== false ? 'var(--green-alive)' : 'var(--red-alert)' }}>
              {node.accessible !== false ? '✓ Yes' : '✗ No'}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Type</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>
              {type}
            </span>
          </div>
        </div>
      </div>

      {/* ML Risk Factor Breakdown */}
      {(risk === 'HIGH' || risk === 'MEDIUM') && (
        <div className="panel__section" style={{ padding: '0 20px 20px' }}>
          <div className="panel__title">ML RISK FACTORS (CLUSTER PREDICTION)</div>
          <div style={{ background: 'rgba(0,0,0,0.02)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(0,0,0,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Population Density (Weight)</span>
              <span style={{ fontWeight: 600 }}>42%</span>
            </div>
            <div style={{ width: '100%', background: 'rgba(0,0,0,0.05)', height: '4px', borderRadius: '2px', marginBottom: '12px' }}>
              <div style={{ width: '42%', background: 'var(--red-alert)', height: '100%', borderRadius: '2px' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Industrial Proximity</span>
              <span style={{ fontWeight: 600 }}>35%</span>
            </div>
            <div style={{ width: '100%', background: 'rgba(0,0,0,0.05)', height: '4px', borderRadius: '2px', marginBottom: '12px' }}>
              <div style={{ width: '35%', background: 'var(--orange-warm)', height: '100%', borderRadius: '2px' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Historical Incident Rate</span>
              <span style={{ fontWeight: 600 }}>23%</span>
            </div>
            <div style={{ width: '100%', background: 'rgba(0,0,0,0.05)', height: '4px', borderRadius: '2px' }}>
              <div style={{ width: '23%', background: 'var(--blue-vibrant)', height: '100%', borderRadius: '2px' }} />
            </div>
          </div>
        </div>
      )}

      {/* Agent Status */}
      <div className="panel__section" style={{ padding: '0 20px 20px' }}>
        <div className="panel__title">AGENT STATUS</div>
        {isAmb && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, background: 'rgba(16, 185, 129, 0.1)', borderRadius: 12, border: '1px solid rgba(16, 185, 129, 0.2)', marginBottom: 8 }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--green-alive)', boxShadow: '0 0 8px var(--green-alive)' }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>🚑 Ambulance</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Stationed at this node</div>
            </div>
          </div>
        )}
        {isPol && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, background: 'rgba(0, 102, 255, 0.1)', borderRadius: 12, border: '1px solid rgba(0, 102, 255, 0.2)' }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--blue-vibrant)', boxShadow: '0 0 8px var(--blue-vibrant)' }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>🚓 Police Unit</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Patrolling — risk zone</div>
            </div>
          </div>
        )}
        {!isAmb && !isPol && (
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            No agents deployed at this node
          </div>
        )}
      </div>

    </div>
  );
}
