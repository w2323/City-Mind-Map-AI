# theme.py — CityMind 2D Desktop Application: Design Tokens
# All colours, fonts, spacing, and semantic states in one place.

import pygame
from collections import OrderedDict


# ─── Colour Palette ──────────────────────────────────────────────────────────

class Colors:
    # Background layers
    BG_DEEP       = (239, 243, 248)
    BG_DARK       = (20, 32, 53)
    BG_PANEL      = (255, 255, 255)
    BG_CARD       = (247, 249, 252)
    BG_HOVER      = (231, 237, 245)
    BG_SELECTED   = (226, 236, 255)

    # Primary accent — cyan
    ACCENT_CYAN   = (38, 100, 220)
    ACCENT_CYAN_D = (30, 78, 167)
    ACCENT_CYAN_G = (0,   220, 255, 40)  # ghost (for fills with alpha)

    # Secondary accent — amber
    ACCENT_AMBER  = (202, 120, 28)
    ACCENT_AMBER_D= (160, 94, 20)

    # Status colours
    GREEN         = (27, 145, 105)
    GREEN_D       = (21, 114, 83)
    RED           = (210, 65, 73)
    RED_D         = (170, 44, 52)
    YELLOW        = (179, 116, 24)
    PURPLE        = (123, 88, 191)

    # Text
    TEXT_PRIMARY  = (31, 45, 68)
    TEXT_SECONDARY= (82, 100, 126)
    TEXT_MUTED    = (110, 126, 148)
    TEXT_BRIGHT   = (24, 39, 61)

    # Borders / dividers
    BORDER        = (220, 228, 238)
    BORDER_BRIGHT = (179, 195, 215)

    # Node type colours
    NODE_EMPTY        = (220, 227, 237)
    NODE_RESIDENTIAL  = (177, 208, 199)
    NODE_HOSPITAL     = (128, 195, 219)
    NODE_SCHOOL       = (162, 186, 231)
    NODE_INDUSTRIAL   = (227, 188, 151)
    NODE_POWER_PLANT  = (228, 209, 146)
    NODE_DEPOT        = (181, 165, 222)

    # Edge states
    EDGE_NORMAL   = (180, 192, 209)
    EDGE_ROUTE    = (38, 100, 220)
    EDGE_BLOCKED  = (210, 65, 73)
    EDGE_BRIDGE   = (255, 200,  30)

    # Risk colours
    RISK_HIGH     = (224, 132, 136)
    RISK_MEDIUM   = (232, 200, 134)
    RISK_LOW      = (161, 206, 185)
    RISK_NONE     = (220, 227, 237)

    # Heatmap gradient: cold → hot
    HEAT_COLD     = (20,  40, 120)
    HEAT_MID      = (200, 100,  30)
    HEAT_HOT      = (230,  30,  30)

    # Ambulance, police, civilian
    AMBULANCE     = (38, 100, 220)
    POLICE        = (123, 88, 191)
    CIVILIAN      = (210, 65, 73)

    # Status bar
    STATUS_OK     = (40,  200,  80)
    STATUS_WARN   = (255, 180,  30)
    STATUS_ERROR  = (230,  50,  50)

    # Button states
    BTN_PRIMARY   = (38, 100, 220)
    BTN_PRIMARY_H = (29, 82, 189)
    BTN_DANGER    = (210, 65, 73)
    BTN_DANGER_H  = (181, 48, 56)
    BTN_NEUTRAL   = (231, 237, 245)
    BTN_NEUTRAL_H = (216, 226, 240)
    BTN_DISABLED  = (237, 241, 247)
    BTN_TEXT      = (255, 255, 255)
    BTN_TEXT_DIS  = (163, 174, 192)

    # Transparency helpers
    TRANSPARENT   = (0, 0, 0, 0)


def lerp_color(c1, c2, t: float):
    """Linearly interpolate between two (r,g,b) colours. t in [0,1]."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def heat_color(value: float, lo: float = 0.0, hi: float = 1.0):
    """Map value in [lo,hi] to a cold→mid→hot colour."""
    if hi <= lo:
        return Colors.HEAT_COLD
    t = (value - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return lerp_color(Colors.HEAT_COLD, Colors.HEAT_MID, t * 2)
    else:
        return lerp_color(Colors.HEAT_MID, Colors.HEAT_HOT, (t - 0.5) * 2)


NODE_TYPE_COLORS = {
    "EMPTY":          Colors.NODE_EMPTY,
    "RESIDENTIAL":    Colors.NODE_RESIDENTIAL,
    "HOSPITAL":       Colors.NODE_HOSPITAL,
    "SCHOOL":         Colors.NODE_SCHOOL,
    "INDUSTRIAL":     Colors.NODE_INDUSTRIAL,
    "POWER_PLANT":    Colors.NODE_POWER_PLANT,
    "BANK":           (190, 139, 34),
    "AMBULANCE_DEPOT":Colors.NODE_DEPOT,
}

NODE_TYPE_LABELS = {
    "EMPTY":          "·",
    "RESIDENTIAL":    "R",
    "HOSPITAL":       "H",
    "SCHOOL":         "S",
    "INDUSTRIAL":     "I",
    "POWER_PLANT":    "P",
    "BANK":           "B",
    "AMBULANCE_DEPOT":"D",
}

RISK_COLORS = {
    "HIGH":   Colors.RISK_HIGH,
    "MEDIUM": Colors.RISK_MEDIUM,
    "LOW":    Colors.RISK_LOW,
    "NONE":   Colors.RISK_NONE,
}


# ─── Font Registry ────────────────────────────────────────────────────────────

class _CachedFont:
    """Fonts share a bounded text atlas. Returned surfaces are read-only to callers."""
    _surfaces = OrderedDict()
    _bytes = 0
    MAX_BYTES = 8 * 1024 * 1024
    MAX_ENTRIES = 2048

    def __init__(self, font):
        self._font = font

    def __getattr__(self, name):
        return getattr(self._font, name)

    def render(self, text, antialias, color, background=None):
        text = str(text)
        fg = tuple(pygame.Color(color))
        bg = tuple(pygame.Color(background)) if background is not None else None
        key = (self, text, antialias, fg, bg)
        cache = type(self)._surfaces
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        result = self._font.render(text, antialias, color, background)
        size = result.get_pitch() * result.get_height()
        if len(text) <= 512 and size <= self.MAX_BYTES:
            cache[key] = result
            type(self)._bytes += size
            while len(cache) > self.MAX_ENTRIES or type(self)._bytes > self.MAX_BYTES:
                _, old = cache.popitem(last=False)
                type(self)._bytes -= old.get_pitch() * old.get_height()
        return result


class Fonts:
    """Lazy font loader. Call Fonts.init() once after pygame.init()."""
    _cache: dict = {}

    MONO_SIZES   = [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 28, 32, 36, 48]
    SANS_SIZES   = [9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 28, 32]

    @classmethod
    def init(cls):
        if not pygame.font.get_init():
            pygame.font.init()
        cls._cache.clear()
        _CachedFont._surfaces.clear()
        _CachedFont._bytes = 0
        for sz in cls.MONO_SIZES:
            cls._cache[f"mono_{sz}"] = _CachedFont(pygame.font.SysFont("Consolas,Courier New,monospace", sz))
        for sz in cls.SANS_SIZES:
            cls._cache[f"sans_{sz}"]  = _CachedFont(pygame.font.SysFont("Segoe UI,Arial,sans-serif", sz))
            cls._cache[f"sansbold_{sz}"] = _CachedFont(pygame.font.SysFont("Segoe UI,Arial,sans-serif", sz, bold=True))

    @classmethod
    def mono(cls, size: int = 12):
        if not pygame.font.get_init() or not cls._cache:
            cls.init()
        key = f"mono_{size}"
        if key not in cls._cache:
            try:
                cls._cache[key] = _CachedFont(pygame.font.SysFont("Consolas,Courier New,monospace", size))
            except Exception:
                cls._cache[key] = pygame.font.Font(None, size)
        return cls._cache.get(key) or pygame.font.Font(None, size)

    @classmethod
    def sans(cls, size: int = 12):
        if not pygame.font.get_init() or not cls._cache:
            cls.init()
        key = f"sans_{size}"
        if key not in cls._cache:
            try:
                cls._cache[key] = _CachedFont(pygame.font.SysFont("Segoe UI,Arial,sans-serif", size))
            except Exception:
                cls._cache[key] = pygame.font.Font(None, size)
        return cls._cache.get(key) or pygame.font.Font(None, size)

    @classmethod
    def bold(cls, size: int = 12):
        if not pygame.font.get_init() or not cls._cache:
            cls.init()
        key = f"sansbold_{size}"
        if key not in cls._cache:
            try:
                cls._cache[key] = _CachedFont(pygame.font.SysFont("Segoe UI,Arial,sans-serif", size, bold=True))
            except Exception:
                cls._cache[key] = pygame.font.Font(None, size)
        return cls._cache.get(key) or pygame.font.Font(None, size)


# ─── Layout Constants ─────────────────────────────────────────────────────────

class Layout:
    WIN_W         = 1560
    WIN_H         = 960

    TOPBAR_H      = 86
    STATUSBAR_H   = 28
    LEFT_PANEL_W  = 208
    RIGHT_PANEL_W = 280

    CONTENT_X     = LEFT_PANEL_W
    CONTENT_Y     = TOPBAR_H
    CONTENT_W     = WIN_W - LEFT_PANEL_W - RIGHT_PANEL_W
    CONTENT_H     = WIN_H - TOPBAR_H - STATUSBAR_H

    PADDING       = 10
    GAP           = 6
    RADIUS        = 6
    ICON_SZ       = 20
