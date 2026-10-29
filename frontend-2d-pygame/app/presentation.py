"""Aspect-preserving presentation and pointer mapping for every desktop size."""
import pygame


class Presentation:
    def __init__(self, logical_size):
        self.logical_size = logical_size
        self.rect = pygame.Rect(0, 0, *logical_size)
        self.scale = 1.0
        self._scaled = None

    def resize(self, size):
        width, height = max(1, size[0]), max(1, size[1])
        self.scale = min(width / self.logical_size[0], height / self.logical_size[1])
        target = (max(1, round(self.logical_size[0] * self.scale)),
                  max(1, round(self.logical_size[1] * self.scale)))
        self.rect = pygame.Rect((width-target[0])//2, (height-target[1])//2, *target)
        self._scaled = None

    def to_logical(self, pos):
        return (round((pos[0]-self.rect.x) * self.logical_size[0] / self.rect.width),
                round((pos[1]-self.rect.y) * self.logical_size[1] / self.rect.height))

    def event(self, event):
        if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
            return event
        values = event.dict.copy()
        physical = values.get('pos', pygame.mouse.get_pos())
        values['pos'] = self.to_logical(physical)
        if event.type == pygame.MOUSEMOTION:
            values['rel'] = tuple(round(v / self.scale) for v in values.get('rel', (0, 0)))
        return pygame.event.Event(event.type, values)

    def draw(self, canvas, display):
        display.fill((6, 8, 16))
        if self.rect.size == canvas.get_size():
            display.blit(canvas, self.rect)
        else:
            if self._scaled is None or self._scaled.get_size() != self.rect.size:
                self._scaled = pygame.Surface(self.rect.size)
            pygame.transform.smoothscale(canvas, self.rect.size, self._scaled)
            display.blit(self._scaled, self.rect)
