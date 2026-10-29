# screens/base_screen.py — Base class for all screens

import pygame
from app.theme import Colors, Fonts, Layout
from components.buttons import draw_label, draw_rect_rounded


class BaseScreen:
    """All screens inherit from this. Provides common helpers."""

    def __init__(self, app, rect: pygame.Rect):
        self.app  = app
        self.rect = rect

    @property
    def state(self):
        return self.app.state

    @property
    def graph(self):
        return self.app.state.backend_graph

    @property
    def sim(self):
        return self.app.state.backend_sim

    def handle_event(self, event):
        pass

    def update(self, dt: float):
        pass

    def draw(self, surface):
        pass

    def on_enter(self):
        pass

    def on_state_updated(self):
        pass

    def draw_panel(self, surface, rect, title: str = None):
        """Draw a card panel background."""
        pygame.draw.rect(surface, Colors.BG_PANEL, rect, border_radius=Layout.RADIUS)
        pygame.draw.rect(surface, Colors.BORDER, rect, 1, border_radius=Layout.RADIUS)
        if title:
            f = Fonts.bold(10)
            t = f.render(title.upper(), True, Colors.TEXT_MUTED)
            surface.blit(t, (rect.x + Layout.PADDING, rect.y + Layout.PADDING))
            return rect.y + Layout.PADDING + t.get_height() + 6
        return rect.y + Layout.PADDING

    def draw_kv(self, surface, label: str, value: str, x: int, y: int,
                lw: int = 130, val_color=Colors.ACCENT_CYAN, font_size: int = 11):
        """Draw a label: value pair."""
        fl = Fonts.mono(font_size)
        tl = fl.render(label, True, Colors.TEXT_MUTED)
        tv = fl.render(str(value), True, val_color)
        surface.blit(tl, (x, y))
        surface.blit(tv, (x + lw, y))
        return y + max(tl.get_height(), tv.get_height()) + 4

    def draw_not_connected(self, surface):
        """Show a 'not connected' message in centre of rect."""
        f = Fonts.bold(14)
        t = f.render("Backend not connected", True, Colors.RED)
        cx = self.rect.centerx
        cy = self.rect.centery
        surface.blit(t, (cx - t.get_width() // 2, cy - 30))
        f2 = Fonts.mono(10)
        t2 = f2.render("Start the backend:  uvicorn backend.api.main:app --reload",
                        True, Colors.TEXT_MUTED)
        surface.blit(t2, (cx - t2.get_width() // 2, cy))

    def draw_not_initialized(self, surface):
        f = Fonts.bold(12)
        t = f.render("Simulation not initialized — use Restart",
                     True, Colors.YELLOW)
        cx = self.rect.centerx
        cy = self.rect.centery
        surface.blit(t, (cx - t.get_width() // 2, cy))
