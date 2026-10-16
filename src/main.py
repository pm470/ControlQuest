import sys

import pygame

from config import (
    BACKGROUND_COLOR,
    FPS,
    GRID_COLOR,
    GRID_COLUMNS,
    GRID_ROWS,
    HEIGHT,
    SIDEBAR_COLOR,
    SIDEBAR_WIDTH,
    TEXT_COLOR,
    WIDTH,
)
from entities import Ball, Slider, Target
from mpc_interface import update_state


def send_to_mpc(ball: Ball, target: Target, sliders: list[Slider]) -> None:
    update_state(
        ball_position=(ball.x, ball.y),
        target_position=(target.x, target.y),
        settings=(sliders[0].value, sliders[1].value, sliders[2].value),
    )


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("MPC Game")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)

    grid_width = WIDTH - SIDEBAR_WIDTH
    cell_width = grid_width / GRID_COLUMNS
    cell_height = HEIGHT / GRID_ROWS
    ball = Ball(x=1, y=5)
    target: Target | None = None
    sliders = [
        Slider(
            label=f"Setting {index}",
            x=grid_width + 24,
            y=130 + (index - 1) * 100,
            width=SIDEBAR_WIDTH - 48,
        )
        for index in range(1, 4)
    ]
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False
            slider_changed = False
            for slider in sliders:
                if slider.handle_event(event):
                    slider_changed = True

            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and 0 <= event.pos[0] < grid_width
                and 0 <= event.pos[1] < HEIGHT
            ):
                mouse_x, mouse_y = event.pos
                if 0 <= mouse_x < grid_width:
                    target = Target(
                        x=int(mouse_x // cell_width) + 1,
                        y=int(mouse_y // cell_height) + 1,
                    )
                    send_to_mpc(ball, target, sliders)
            elif slider_changed and target is not None:
                send_to_mpc(ball, target, sliders)

        screen.fill(BACKGROUND_COLOR)
        for column in range(GRID_COLUMNS + 1):
            x = round(column * cell_width)
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, HEIGHT))
        for row in range(GRID_ROWS + 1):
            y = round(row * cell_height)
            pygame.draw.line(screen, GRID_COLOR, (0, y), (grid_width, y))

        ball.draw(screen, cell_width, cell_height)
        if target is not None:
            target.draw(screen, cell_width, cell_height)

        sidebar = pygame.Rect(grid_width, 0, SIDEBAR_WIDTH, HEIGHT)
        pygame.draw.rect(screen, SIDEBAR_COLOR, sidebar)
        pygame.draw.line(screen, GRID_COLOR, (grid_width, 0), (grid_width, HEIGHT), 2)
        title = font.render("MPC Settings", True, TEXT_COLOR)
        screen.blit(title, (grid_width + 24, 42))
        for slider in sliders:
            slider.draw(screen, font)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
