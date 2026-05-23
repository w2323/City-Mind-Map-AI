import React, { useEffect, useRef } from 'react';

export default function EventFeedHUD({ events }) {
  const logRef = useRef(null);

  // Auto-scroll event log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  if (!events || events.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      width: 380,
      maxHeight: 250,
      background: 'rgba(10, 15, 25, 0.85)',
      backdropFilter: 'blur(10px)',
      border: '1px solid rgba(0, 255, 255, 0.2)',
      borderRadius: 12,
      display: 'flex',
      flexDirection: 'column',
      zIndex: 50,
      boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
      overflow: 'hidden'
    }}>
      <div style={{ padding: '8px 12px', background: 'rgba(0,0,0,0.3)', borderBottom: '1px solid rgba(0, 255, 255, 0.1)', fontSize: 10, fontWeight: 700, color: 'var(--accent-cyan)', letterSpacing: 1 }}>
        LIVE SIMULATION EVENTS
      </div>
      <div ref={logRef} className="event-log" style={{ flex: 1, padding: '12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {events.map((evt, i) => {
          const msg = typeof evt === 'string' ? evt : evt.message || '';
          const evtType = evt.type || '';
          let icon = '📡';
          let modifier = '';
          if (evtType === 'FLOOD') { icon = '🌊'; modifier = 'event-item--danger'; }
          else if (evtType === 'ROUTING') { icon = '🚑'; modifier = 'event-item--info'; }
          else if (evtType === 'ML') { icon = '⚠️'; modifier = 'event-item--warning'; }
          else if (evtType === 'AMBULANCE' || evtType === 'PLACEMENT') { icon = '📍'; modifier = 'event-item--success'; }
          else if (evtType === 'SIMULATION') { icon = '⚙️'; modifier = 'event-item--success'; }

          // Use index for key to ensure uniqueness as events stream in
          return (
            <div key={`evt-${i}`} className={`event-item ${modifier}`} style={{ animation: 'fade-in 0.3s ease-out' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span className="event-item__time">
                  [STEP {evt.step || 0}] {icon} {evtType}
                </span>
                <span className="event-item__msg" style={{ color: 'var(--text-primary)' }}>{msg}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
