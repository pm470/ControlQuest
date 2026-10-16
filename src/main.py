import sys

import pygame

from config import BACKGROUND_COLOR, FPS, HEIGHT, WIDTH
from entities import Ball, Target


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("MPC Game")
    clock = pygame.time.Clock()

    ball = Ball(x=WIDTH * 0.2, y=HEIGHT * 0.5)
    target = Target(x=WIDTH * 0.8, y=HEIGHT * 0.5)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                target.x, target.y = event.pos

        screen.fill(BACKGROUND_COLOR)
        ball.draw(screen)
        target.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
