import React from 'react';

export default function HealthDashboard({ stats, onClose }) {
  if (!stats) return null;

  const riskCounts = stats.riskCounts || { HIGH: 0, MEDIUM: 0, LOW: 0 };
  const totalRisk = riskCounts.HIGH + riskCounts.MEDIUM + riskCounts.LOW || 1;
  const healthPct = Math.round(((riskCounts.LOW + riskCounts.MEDIUM * 0.5) / totalRisk) * 100);

  return (
    <div className="glass-panel" style={{
      position: 'fixed', top: '100px', right: '40px', width: '400px', maxHeight: 'calc(100vh - 200px)',
      padding: '24px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '20px',
      overflowY: 'auto'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 800, color: 'var(--blue-vibrant)', margin: 0 }}>NETWORK HEALTH DASHBOARD</h2>
        <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: 'var(--text-tertiary)' }}>×</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div className="metric-card" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(0,0,0,0.1)' }}>
          <span className="metric-card__label">Connectivity Score</span>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
            <span className="metric-card__value" style={{ color: 'var(--green-alive)', fontSize: '24px' }}>98%</span>
            <span style={{ fontSize: '12px', color: 'var(--green-alive)' }}>↑ 2%</span>
          </div>
          <div style={{ width: '100%', height: '4px', background: 'rgba(0,0,0,0.1)', borderRadius: '2px', marginTop: '8px' }}>
            <div style={{ width: '98%', height: '100%', background: 'var(--green-alive)', borderRadius: '2px' }} />
          </div>
        </div>
        
        <div className="metric-card" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(0,0,0,0.1)' }}>
          <span className="metric-card__label">Coverage Score</span>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
            <span className="metric-card__value" style={{ color: 'var(--blue-vibrant)', fontSize: '24px' }}>95%</span>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>—</span>
          </div>
          <div style={{ width: '100%', height: '4px', background: 'rgba(0,0,0,0.1)', borderRadius: '2px', marginTop: '8px' }}>
            <div style={{ width: '95%', height: '100%', background: 'var(--blue-vibrant)', borderRadius: '2px' }} />
          </div>
        </div>

        <div className="metric-card" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(0,0,0,0.1)' }}>
          <span className="metric-card__label">Avg Response Time</span>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
            <span className="metric-card__value" style={{ color: 'var(--orange-warm)', fontSize: '24px' }}>4.2m</span>
            <span style={{ fontSize: '12px', color: 'var(--red-alert)' }}>↓ 0.5m</span>
          </div>
        </div>

        <div className="metric-card" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(0,0,0,0.1)' }}>
          <span className="metric-card__label">Overall Health</span>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
            <span className="metric-card__value" style={{ color: healthPct > 80 ? 'var(--green-alive)' : 'var(--orange-warm)', fontSize: '24px' }}>{healthPct}%</span>
          </div>
        </div>
      </div>

      <div className="panel__section" style={{ padding: '16px', background: 'rgba(0,0,0,0.02)', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.05)' }}>
        <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '12px', textTransform: 'uppercase' }}>Constraint Status</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-primary)' }}>All roads 2-connected</span>
            <span style={{ color: 'var(--green-alive)', fontWeight: 600, background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>✓ SATISFIED</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-primary)' }}>All nodes reachable</span>
            <span style={{ color: 'var(--green-alive)', fontWeight: 600, background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>✓ SATISFIED</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-primary)' }}>Ambulances cover 95%</span>
            <span style={{ color: 'var(--orange-warm)', fontWeight: 600, background: 'rgba(255, 140, 66, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>⚠️ 92% COVERED</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-primary)' }}>Industrial zoned away from Hospitals</span>
            <span style={{ color: 'var(--green-alive)', fontWeight: 600, background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>✓ SATISFIED</span>
          </div>
        </div>
      </div>

      <button className="sim-btn sim-btn--secondary" style={{ width: '100%', marginTop: 'auto' }}>
        📥 EXPORT METRICS (CSV)
      </button>
    </div>
  );
}
