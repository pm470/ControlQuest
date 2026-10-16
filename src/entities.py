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
