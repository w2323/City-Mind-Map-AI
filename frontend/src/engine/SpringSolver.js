// ═══════════════════════════════════════════════════════════
// CITYMIND — Spring Physics Solver
// Replaces Framer Motion. Zero dependencies. ~80 LOC.
// ═══════════════════════════════════════════════════════════

export class Spring {
  constructor(value = 0, stiffness = 180, damping = 18, mass = 1) {
    this.current = value;
    this.previous = value;
    this.target = value;
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
    this.velocity = 0;
  }

  update(dt = 0.016) {
    const force = (this.target - this.current) * this.stiffness;
    const friction = this.velocity * this.damping;
    const accel = (force - friction) / this.mass;
    this.velocity += accel * dt;
    this.previous = this.current;
    this.current += this.velocity * dt;
    return this.current;
  }

  setTarget(t) { this.target = t; }
  set(v) { this.current = v; this.previous = v; this.target = v; this.velocity = 0; }
  get settled() { return Math.abs(this.current - this.target) < 0.001 && Math.abs(this.velocity) < 0.01; }
}

// Presets
export const SPRING_INTERACTIVE = { stiffness: 180, damping: 18 };
export const SPRING_PANEL       = { stiffness: 120, damping: 22 };
export const SPRING_RIGHT_PANEL = { stiffness: 140, damping: 20 };

// Simple lerp for secondary animations
export function lerp(a, b, t) { return a + (b - a) * t; }

// Clamp
export function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
