from dataclasses import dataclass

import pygame

from config import (
    BALL_COLOR,
    BALL_RADIUS,
    SLIDER_FILL_COLOR,
    SLIDER_TRACK_COLOR,
    TEXT_COLOR,
    TARGET_COLOR,
    TARGET_CROSS_SIZE,
    TARGET_RADIUS,
)


@dataclass
class Ball:
    x: int
    y: int

    def draw(
        self,
        surface: pygame.Surface,
        cell_width: float,
        cell_height: float,
    ) -> None:
        center = (
            round((self.x - 0.5) * cell_width),
            round((self.y - 0.5) * cell_height),
        )
        pygame.draw.circle(surface, BALL_COLOR, center, BALL_RADIUS)


@dataclass
class Target:
    x: int
    y: int

    def draw(
        self,
        surface: pygame.Surface,
        cell_width: float,
        cell_height: float,
    ) -> None:
        center = (
            round((self.x - 0.5) * cell_width),
            round((self.y - 0.5) * cell_height),
        )
        pygame.draw.circle(surface, TARGET_COLOR, center, TARGET_RADIUS)
        pygame.draw.line(
            surface,
            TARGET_COLOR,
            (center[0] - TARGET_CROSS_SIZE, center[1]),
            (center[0] + TARGET_CROSS_SIZE, center[1]),
            2,
        )
        pygame.draw.line(
            surface,
            TARGET_COLOR,
            (center[0], center[1] - TARGET_CROSS_SIZE),
            (center[0], center[1] + TARGET_CROSS_SIZE),
            2,
        )


@dataclass
class Slider:
    label: str
    x: int
    y: int
    width: int
    value: float = 0.5
    dragging: bool = False

    @property
    def handle_x(self) -> int:
        return round(self.x + self.value * self.width)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = event.pos
            on_track = self.x <= mouse_x <= self.x + self.width
            near_track = abs(mouse_y - self.y) <= 14
            if on_track and near_track:
                self.dragging = True
                return self._set_from_mouse(mouse_x)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            return self._set_from_mouse(event.pos[0])
        return False

    def _set_from_mouse(self, mouse_x: int) -> bool:
        value = min(1.0, max(0.0, (mouse_x - self.x) / self.width))
        if value == self.value:
            return False
        self.value = value
        return True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        label = font.render(f"{self.label}  {self.value:.2f}", True, TEXT_COLOR)
        surface.blit(label, (self.x, self.y - 32))
        pygame.draw.line(
            surface,
            SLIDER_TRACK_COLOR,
            (self.x, self.y),
            (self.x + self.width, self.y),
            6,
        )
        pygame.draw.line(
            surface,
            SLIDER_FILL_COLOR,
            (self.x, self.y),
            (self.handle_x, self.y),
            6,
        )
        pygame.draw.circle(surface, SLIDER_FILL_COLOR, (self.handle_x, self.y), 10)
