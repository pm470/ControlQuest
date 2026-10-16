import sys

import pygame

from config import (
    BACKGROUND_COLOR,
    FPS,
    GRID_COLOR,
    GRID_COLUMNS,
    GRID_ROWS,
    HEIGHT,
    WIDTH,
)
from entities import Ball, Target
from mpc_interface import update_state


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("MPC Game")
    clock = pygame.time.Clock()

    cell_width = WIDTH / GRID_COLUMNS
    cell_height = HEIGHT / GRID_ROWS
    ball = Ball(x=1, y=5)
    target: Target | None = None
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                if 0 <= mouse_x < WIDTH and 0 <= mouse_y < HEIGHT:
                    target = Target(
                        x=int(mouse_x // cell_width) + 1,
                        y=int(mouse_y // cell_height) + 1,
                    )
                    update_state(
                        ball_position=(ball.x, ball.y),
                        target_position=(target.x, target.y),
                    )

        screen.fill(BACKGROUND_COLOR)
        for column in range(GRID_COLUMNS + 1):
            x = round(column * cell_width)
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, HEIGHT))
        for row in range(GRID_ROWS + 1):
            y = round(row * cell_height)
            pygame.draw.line(screen, GRID_COLOR, (0, y), (WIDTH, y))

        ball.draw(screen, cell_width, cell_height)
        if target is not None:
            target.draw(screen, cell_width, cell_height)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
