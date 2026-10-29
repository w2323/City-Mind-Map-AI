import { useEffect, useRef } from 'react';
import {sectorInfo,sectorText} from '../presentation/sectors';

export default function RightPanel({ selectedNode, graph, state, stats, onClose }) {
  const isOpen = selectedNode !== null;
  const node = isOpen ? graph?.nodes?.find(n=>n.id===selectedNode) : null;
  const risk = state?.risk_predictions?.[String(selectedNode)] || 'LOW';
  const ambulances = state?.ambulances || [];
  const police = (state?.police?.units || []).map(p => p.position);
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
  const info=sectorInfo(type);
  const typeName = info.name;
  const isAmb = ambulances.includes(selectedNode);
  const isPol = police.includes(selectedNode);

  return (
    <div className={`right-panel ${isOpen ? 'right-panel--open' : ''}`}>
      {/* Header */}
      <div style={{ padding: 20, borderBottom: '1px solid rgba(0,0,0,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="panel__title" style={{ marginBottom: 4, color: 'var(--blue-vibrant)' }}>Sector {node.label || selectedNode} — {typeName}</div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Grid Ref: {node.label} · Row {node.label.match(/^[A-Z]+/)?.[0]} · Column {node.label.match(/\d+$/)?.[0]}</div>
          <div style={{fontSize:11,marginTop:6}}>{info.description}</div>
        </div>
        <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: '50%', border: 'none', background: 'rgba(0,0,0,0.05)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 16, fontWeight: 'bold' }}>×</button>
      </div>

      {/* Metrics */}
      <div className="panel__section" style={{ padding: 20 }}>
        <div className="panel__title">REAL-TIME METRICS</div>
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-card__label">Sector population</span>
            <span className="metric-card__value" style={{ color: 'var(--text-primary)' }}>
              {(node.population ?? 0).toLocaleString()}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Sector crime level</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: risk === 'HIGH' ? 'var(--red-alert)' : risk === 'MEDIUM' ? 'var(--orange-warm)' : 'var(--green-alive)' }}>{risk}</span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Accessible</span>
            <span className="metric-card__value" style={{ color: node.accessible !== false ? 'var(--green-alive)' : 'var(--red-alert)' }}>
              {node.accessible !== false ? '✓ Yes' : '✗ No'}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-card__label">Land use</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>
              {typeName}
            </span>
          </div>
        </div>
      </div>

      <div className="panel__section" style={{ padding: 20 }}>
        <div className="panel__title">CRIME SCENARIO (SIMULATED)</div>
        <div style={{fontSize:12}}>Sector crime score: {node.crime_score ?? '—'}/100</div>
        {(node.crime_reasons || []).map(reason=><div key={reason} style={{fontSize:11}}>{sectorText(reason)}</div>)}
        {Object.entries(node.risk_features || {}).map(([name, value]) => (
          <div key={name} style={{ fontSize: 11 }}>{sectorText(name.replaceAll('_', ' '))}: {value}</div>
        ))}
        <div style={{ fontSize: 11 }}>Sector-wide opportunity, not an incident at every building.</div>
        <div style={{ fontSize: 11 }}>Scenario score; not a measured crime probability.</div>
      </div>

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
