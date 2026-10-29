# components/buttons.py — Reusable Pygame button and UI components

import pygame
from app.theme import Colors, Fonts, Layout


def draw_rect_rounded(surface, color, rect, radius=6, border_color=None, border_width=1):
    """Draw a rounded rectangle with optional border."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_color:
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=radius)


class Button:
    """
    A reusable Pygame button with hover, pressed, and disabled states.

    Usage:
        btn = Button("STEP", rect=(x,y,w,h), style="primary")
        # In event loop:
        if btn.handle_event(event):
            do_action()
        # In draw loop:
        btn.draw(surface)
    """

    STYLES = {
        "primary":  (Colors.BTN_PRIMARY,   Colors.BTN_PRIMARY_H,  Colors.BTN_TEXT),
        "danger":   (Colors.BTN_DANGER,    Colors.BTN_DANGER_H,   Colors.BTN_TEXT),
        "neutral":  (Colors.BTN_NEUTRAL,   Colors.BTN_NEUTRAL_H,  Colors.TEXT_PRIMARY),
        "success":  (Colors.GREEN_D,       Colors.GREEN,          Colors.BTN_TEXT),
        "warning":  (Colors.ACCENT_AMBER_D,Colors.ACCENT_AMBER,   Colors.BG_DEEP),
    }

    def __init__(self, label: str, rect, style: str = "neutral",
                 font_size: int = 11, enabled: bool = True, tooltip: str = ""):
        self.label   = label
        self.rect    = pygame.Rect(rect)
        self.style   = style
        self.font_sz = font_size
        self.enabled = enabled
        self.tooltip = tooltip
        self._hovered  = False
        self._pressed  = False
        self._clicked  = False

    def handle_event(self, event) -> bool:
        """Returns True on a valid click."""
        self._clicked = False
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._clicked = True
                self._pressed = False
                return True
            self._pressed = False
        return False

    def draw(self, surface):
        if not self.enabled:
            draw_rect_rounded(surface, Colors.BTN_DISABLED, self.rect,
                              radius=Layout.RADIUS,
                              border_color=Colors.BORDER)
            font = Fonts.mono(self.font_sz)
            txt = font.render(self.label, True, Colors.BTN_TEXT_DIS)
            surface.blit(txt, txt.get_rect(center=self.rect.center))
            return

        colors = self.STYLES.get(self.style, self.STYLES["neutral"])
        bg_color = colors[1] if self._hovered else colors[0]
        if self._pressed:
            bg_color = tuple(max(0, c - 30) for c in colors[0])
        draw_rect_rounded(surface, bg_color, self.rect,
                          radius=Layout.RADIUS,
                          border_color=Colors.BORDER_BRIGHT if self._hovered else Colors.BORDER)
        font = Fonts.bold(self.font_sz)
        txt = font.render(self.label, True, colors[2])
        surface.blit(txt, txt.get_rect(center=self.rect.center))


class IconButton:
    """Small square button with a single character icon."""

    def __init__(self, icon: str, rect, color=Colors.ACCENT_CYAN, tooltip: str = ""):
        self.icon    = icon
        self.rect    = pygame.Rect(rect)
        self.color   = color
        self.tooltip = tooltip
        self._hovered = False
        self._pressed = False

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                return True
            self._pressed = False
        return False

    def draw(self, surface):
        bg = Colors.BG_HOVER if self._hovered else Colors.BG_CARD
        draw_rect_rounded(surface, bg, self.rect, radius=4,
                          border_color=self.color if self._hovered else Colors.BORDER)
        f = Fonts.bold(12)
        t = f.render(self.icon, True, self.color)
        surface.blit(t, t.get_rect(center=self.rect.center))


class ToggleButton(Button):
    """Button that maintains an on/off state."""

    def __init__(self, label_on, label_off, rect, state: bool = False, **kwargs):
        self.label_on  = label_on
        self.label_off = label_off
        self.state     = state
        kwargs["label"] = label_on if state else label_off
        super().__init__(**kwargs)

    def handle_event(self, event) -> bool:
        clicked = super().handle_event(event)
        if clicked:
            self.state = not self.state
            self.label = self.label_on if self.state else self.label_off
            self.style = "primary" if self.state else "neutral"
        return clicked


class TextInput:
    """Single-line text input field."""

    def __init__(self, rect, placeholder: str = "", max_len: int = 40, font_size: int = 12):
        self.rect        = pygame.Rect(rect)
        self.placeholder = placeholder
        self.max_len     = max_len
        self.font_sz     = font_size
        self.text        = ""
        self.focused     = False
        self._cursor_vis = True
        self._cursor_t   = 0

    def handle_event(self, event) -> bool:
        """Returns True if text changed."""
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.focused = self.rect.collidepoint(event.pos)
        if not self.focused:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                changed = True
            elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.focused = False
            elif len(self.text) < self.max_len and getattr(event, "unicode", "").isprintable():
                self.text += event.unicode
                changed = True
        return changed

    def update(self, dt: float):
        self._cursor_t += dt
        if self._cursor_t > 0.5:
            self._cursor_vis = not self._cursor_vis
            self._cursor_t = 0

    def draw(self, surface):
        border_color = Colors.ACCENT_CYAN if self.focused else Colors.BORDER
        draw_rect_rounded(surface, Colors.BG_CARD, self.rect, radius=4,
                          border_color=border_color)
        font = Fonts.mono(self.font_sz)
        if self.text:
            display = self.text
            color = Colors.TEXT_PRIMARY
        else:
            display = self.placeholder
            color = Colors.TEXT_MUTED
        txt_surf = font.render(display, True, color)
        inner = self.rect.inflate(-8, -4)
        surface.blit(txt_surf, (inner.x, inner.centery - txt_surf.get_height() // 2))
        if self.focused and self._cursor_vis:
            cx = inner.x + min(font.size(self.text)[0], inner.width - 4)
            cy = inner.centery
            pygame.draw.line(surface, Colors.ACCENT_CYAN, (cx, cy - 6), (cx, cy + 6), 1)


class ScrollList:
    """Scrollable list of text items."""

    def __init__(self, rect, items=None, font_size=11, item_height=20):
        self.rect       = pygame.Rect(rect)
        self.items      = items or []
        self.font_sz    = font_size
        self.item_h     = item_height
        self._scroll    = 0
        self.selected   = -1

    def handle_event(self, event) -> int:
        """Returns index of selected item, or -1."""
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(getattr(event, "pos", pygame.mouse.get_pos())):
                self._scroll = max(0, self._scroll - event.y * self.item_h)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                rel_y = event.pos[1] - self.rect.y + self._scroll
                idx = rel_y // self.item_h
                if 0 <= idx < len(self.items):
                    self.selected = idx
                    return idx
        return -1

    def set_items(self, items):
        self.items = items

    def scroll_to_bottom(self):
        total_h = len(self.items) * self.item_h
        self._scroll = max(0, total_h - self.rect.height)

    def draw(self, surface):
        clip = surface.get_clip()
        surface.set_clip(self.rect)

        font = Fonts.mono(self.font_sz)
        max_scroll = max(0, len(self.items) * self.item_h - self.rect.height)
        self._scroll = min(self._scroll, max_scroll)

        for i, item in enumerate(self.items):
            y = self.rect.y + i * self.item_h - self._scroll
            if y + self.item_h < self.rect.y:
                continue
            if y > self.rect.y + self.rect.height:
                break
            item_rect = pygame.Rect(self.rect.x, y, self.rect.width, self.item_h)
            if i == self.selected:
                pygame.draw.rect(surface, Colors.BG_SELECTED, item_rect)

            # Colour coding by log level
            color = Colors.TEXT_SECONDARY
            if isinstance(item, dict):
                lvl = item.get("level", "info")
                msg = f"[{item.get('ts','')}] [{item.get('cat','')}] {item.get('msg','')}"
                if lvl == "error":
                    color = Colors.RED
                elif lvl == "warning":
                    color = Colors.YELLOW
                elif lvl == "info":
                    color = Colors.TEXT_SECONDARY
                else:
                    color = Colors.TEXT_MUTED
            else:
                msg = str(item)

            t = font.render(msg[:120], True, color)
            surface.blit(t, (self.rect.x + 4, y + (self.item_h - t.get_height()) // 2))

        surface.set_clip(clip)


def draw_label(surface, text: str, pos, font_size: int = 11,
               color=Colors.TEXT_SECONDARY, bold: bool = False):
    font = Fonts.bold(font_size) if bold else Fonts.mono(font_size)
    surf = font.render(text, True, color)
    surface.blit(surf, pos)
    return surf.get_width()


def draw_value_row(surface, label: str, value: str, y: int, x: int,
                   w: int = 240, font_size: int = 11,
                   val_color=Colors.ACCENT_CYAN):
    """Draw a label: value pair on one row."""
    draw_label(surface, label, (x, y), font_size, Colors.TEXT_MUTED)
    draw_label(surface, value, (x + w - Fonts.mono(font_size).size(value)[0] - 4, y),
               font_size, val_color)


def draw_section_header(surface, title: str, y: int, x: int, w: int,
                        font_size: int = 11):
    """Draw a section header with a horizontal rule."""
    font = Fonts.bold(font_size)
    t = font.render(title.upper(), True, Colors.TEXT_SECONDARY)
    surface.blit(t, (x + 2, y))
    pygame.draw.line(surface, Colors.BORDER,
                     (x, y + font_size + 4), (x + w, y + font_size + 4), 1)
    return y + font_size + 8


def draw_badge(surface, text: str, pos, color=Colors.ACCENT_CYAN, bg=None, font_size: int = 10):
    """Draw a small coloured badge."""
    font = Fonts.bold(font_size)
    t = font.render(text, True, color)
    w, h = t.get_size()
    pad = 4
    r = pygame.Rect(pos[0], pos[1], w + pad * 2, h + pad)
    bg_col = bg or tuple(max(0, c // 4) for c in color)
    draw_rect_rounded(surface, bg_col, r, radius=3, border_color=color)
    surface.blit(t, (r.x + pad, r.y + pad // 2))
    return r.width


def draw_tooltip(surface, text: str, pos):
    """Draw a floating tooltip near pos."""
    if not text:
        return
    font = Fonts.sans(10)
    lines = text.split("\n")
    max_w = max(font.size(l)[0] for l in lines) + 12
    h = len(lines) * 14 + 8
    r = pygame.Rect(pos[0] + 12, pos[1] - 4, max_w, h)
    # Keep on screen
    sw, sh = surface.get_size()
    if r.right > sw:
        r.x = pos[0] - max_w - 4
    if r.bottom > sh:
        r.y = pos[1] - h
    pygame.draw.rect(surface, Colors.BG_CARD, r, border_radius=4)
    pygame.draw.rect(surface, Colors.BORDER_BRIGHT, r, 1, border_radius=4)
    for i, line in enumerate(lines):
        t = font.render(line, True, Colors.TEXT_PRIMARY)
        surface.blit(t, (r.x + 6, r.y + 4 + i * 14))


class Slider:
    """Continuous pointer adjustment with one committed API update on release."""
    def __init__(self, rect, value=3.0, minimum=1.0, maximum=12.0):
        self.rect = pygame.Rect(rect)
        self.value, self.minimum, self.maximum = value, minimum, maximum
        self.dragging = False
        self.enabled = True

    def handle_event(self, event):
        if not self.enabled:
            self.dragging = False
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.inflate(18,18).collidepoint(event.pos):
            self.dragging = True
        if self.dragging and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            ratio = max(0, min(1, (event.pos[0]-self.rect.x)/max(1,self.rect.width)))
            self.value = round((self.minimum + ratio*(self.maximum-self.minimum))*2)/2
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            return True
        return False

    def draw(self, surface, color):
        y = self.rect.centery
        pygame.draw.line(surface, Colors.BORDER, (self.rect.x,y), (self.rect.right,y), 5)
        fraction = (self.value-self.minimum)/max(.1,self.maximum-self.minimum)
        x = round(self.rect.x + fraction*self.rect.width)
        pygame.draw.line(surface, color, (self.rect.x,y), (x,y), 5)
        pygame.draw.circle(surface, (255,255,255), (x,y), 8)
        pygame.draw.circle(surface, color, (x,y), 8, 2)
