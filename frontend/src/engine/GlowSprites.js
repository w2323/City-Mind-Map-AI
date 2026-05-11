// ═══════════════════════════════════════════════════════════
// CITYMIND — Glow Sprite Atlas (OffscreenCanvas)
// Pre-renders all glow sprites once. Zero shadowBlur calls.
// ═══════════════════════════════════════════════════════════

const glowCache = {};

export function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

export function createGlowSprite(color, radius) {
  const key = `${color}-${radius}`;
  if (glowCache[key]) return glowCache[key];

  const size = radius * 4;
  const offscreen = new OffscreenCanvas(size, size);
  const octx = offscreen.getContext('2d');
  const rgb = hexToRgb(color);
  const gradient = octx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, radius);
  gradient.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},0.9)`);
  gradient.addColorStop(0.4, `rgba(${rgb.r},${rgb.g},${rgb.b},0.3)`);
  gradient.addColorStop(1, 'transparent');
  octx.fillStyle = gradient;
  octx.fillRect(0, 0, size, size);

  glowCache[key] = offscreen;
  return offscreen;
}

// Build all needed sprites at init
export function buildSpriteAtlas() {
  const colors = [
    '#00E5FF', '#00FFAA', '#FFD600', '#FF6D00', '#FF4444',
    '#4488FF', '#2979FF', '#FF1744', '#00CCFF', '#666666',
    '#00E676', '#FF6600', '#00AA88', '#FF0044'
  ];
  const radii = [6, 8, 10, 12, 16, 20];
  for (const c of colors) {
    for (const r of radii) {
      createGlowSprite(c, r);
    }
  }
  return glowCache;
}

export function getGlowSprite(color, radius) {
  return glowCache[`${color}-${radius}`] || createGlowSprite(color, radius);
}
