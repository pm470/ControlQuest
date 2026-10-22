"""How to play: the idea of the game in four steps, and how a run can end (PRD 1, 4.4, 6)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..core.navigation import ScreenId
from ..ui import theme
from ..ui.widgets import Button, Card, ColorDot, ScreenHeader, StepIcon, label, scrollable
from .base_screen import BaseScreen

STEPS = [
    ("ball", "You are the engineer",
     "You don't steer the ball. You design the MPC controller that does."),
    ("knobs", "Tune the controller",
     "Each level unlocks a few knobs: weights, horizon, margins, model, waypoints."),
    ("plan", "Run and watch the plan",
     "The dashed line is the plan the MPC computes right now. It is re-planned every step."),
    ("stars", "Fix it, earn stars",
     "★ pass the level  ·  ★★ beat the time  ·  ★★★ beat the level's second goal."),
]

OUTCOMES = [
    (theme.SUCCESS, "Success", "the ball rests on the target"),
    (theme.DANGER, "Crash", "the real ball hits a block or a wall"),
    (theme.WARNING, "Controller failure", "the solver finds no valid plan"),
    (theme.NEUTRAL, "Time out", "the ball does not arrive in time"),
]


class HowToPlayScreen(BaseScreen):
    back_target = ScreenId.TITLE

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 22, 40, 16)
        root.setSpacing(14)
        header = ScreenHeader("How to play")
        header.back_clicked.connect(self.go_back)
        root.addWidget(header)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(4, 4, 4, 8)
        col.setSpacing(18)
        root.addWidget(scrollable(content), 1)

        steps = QHBoxLayout()
        steps.setSpacing(18)
        for i, (icon, title, text) in enumerate(STEPS, start=1):
            card = Card(padding=18, spacing=8)
            card.body.addWidget(StepIcon(icon, 76), alignment=Qt.AlignmentFlag.AlignHCenter)
            card.body.addWidget(label(f"{i}. {title}", "subheading", wrap=True,
                                      align=Qt.AlignmentFlag.AlignHCenter))
            card.body.addWidget(label(text, "body", wrap=True, align=Qt.AlignmentFlag.AlignHCenter))
            card.body.addStretch(1)
            steps.addWidget(card, 1)
        col.addLayout(steps)

        ends = Card(padding=20, spacing=10)
        ends.body.addWidget(label("How a run can end", "subheading"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for row, (color, name, text) in enumerate(OUTCOMES):
            grid.addWidget(ColorDot(color, 14), row // 2, (row % 2) * 3)
            grid.addWidget(label(name, "subheading"), row // 2, (row % 2) * 3 + 1)
            grid.addWidget(label(text, "body"), row // 2, (row % 2) * 3 + 2)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(5, 1)
        ends.body.addLayout(grid)
        col.addWidget(ends)
        col.addSpacing(6)

        play = Button("Let's play", variant="primary", scale="large")
        play.clicked.connect(lambda: self.go(ScreenId.LEVEL_SELECT))
        col.addWidget(play, alignment=Qt.AlignmentFlag.AlignHCenter)
        col.addStretch(1)
