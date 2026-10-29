// ═══════════════════════════════════════════════════════════
// CITYMIND — Boot Sequence (Pure CSS animations, no Framer)
// 3-Phase: Dark Boot → System Generation → Activation
// ═══════════════════════════════════════════════════════════

import { useState, useEffect } from 'react';

export default function BootSequence({ onComplete, events = [] }) {
  const [BOOT_LINES] = useState(() => events.slice(-5).map(e => ({ text: e.message, type: e.type === 'SIMULATION' ? 'ready' : 'normal' })));
  const [phase, setPhase] = useState(0);
  const [visibleLines, setVisibleLines] = useState(0);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    // Phase 1 starts immediately
    
    // Phase 2: Terminal lines
    const t1 = setTimeout(() => setPhase(1), 1200);

    const lineTimers = BOOT_LINES.map((_, i) =>
      setTimeout(() => setVisibleLines(i + 1), 1400 + i * 200)
    );

    // End boot
    const activateTime = 1600 + BOOT_LINES.length * 200 + 400;
    const t2 = setTimeout(() => setExiting(true), activateTime);
    const t3 = setTimeout(() => onComplete(), activateTime + 800);

    return () => {
      clearTimeout(t1); clearTimeout(t2); clearTimeout(t3);
      lineTimers.forEach(clearTimeout);
    };
  }, [onComplete]);

  return (
    <div className="boot-screen" style={{ opacity: exiting ? 0 : 1, pointerEvents: 'none', perspective: '1000px' }}>
      <div className="boot-logo" style={{ transformStyle: 'preserve-3d' }}>
        {['C','I','T','Y','M','I','N','D'].map((char, i) => (
          <span 
            key={i} 
            className="boot-letter" 
            style={{ 
              animation: `dropBounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) ${i * 80}ms forwards` 
            }}
          >
            {char}
          </span>
        ))}
      </div>

      <style>{`
        @keyframes dropBounce {
          0% { transform: translate3d(0, -100px, -500px) rotateX(-45deg); opacity: 0; }
          60% { transform: translate3d(0, 10px, 100px) rotateX(10deg); opacity: 1; }
          100% { transform: translate3d(0, 0, 0) rotateX(0deg); opacity: 1; }
        }
      `}</style>

      {phase >= 1 && (
        <div className="boot-terminal">
          <div style={{ marginBottom: 12, fontWeight: 600, color: 'var(--blue-vibrant)' }}>
            CITYMIND — Backend event snapshot
          </div>
          {BOOT_LINES.slice(0, visibleLines).map((line, i) => (
            <div key={i} className="boot-line" style={{ color: line.type === 'ready' ? 'var(--green-alive)' : 'var(--text-secondary)' }}>
              {line.text}
            </div>
          ))}
          <span style={{ display: 'inline-block', width: 8, height: 14, background: 'var(--blue-vibrant)', animation: 'blink 1s step-end infinite', marginTop: 8 }} />
        </div>
      )}
    </div>
  );
}
