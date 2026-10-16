from dataclasses import dataclass

import pygame

from config import (
    BALL_COLOR,
    BALL_RADIUS,
    TARGET_COLOR,
    TARGET_CROSS_SIZE,
    TARGET_RADIUS,
)


@dataclass
class Ball:
    x: float
    y: float

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.circle(surface, BALL_COLOR, (round(self.x), round(self.y)), BALL_RADIUS)


@dataclass
class Target:
    x: float
    y: float

    def draw(self, surface: pygame.Surface) -> None:
        center = (round(self.x), round(self.y))
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
