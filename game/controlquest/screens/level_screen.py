"""Level screen: hosts one level.

Today it shows the level briefing and a "coming soon" card. When a level file
provides `play_screen` (see levels/base.py), its gameplay widget is shown here
instead, below the same header. The gameplay itself lives in the level's file
(and in shared gameplay modules we add later), not in this screen.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..core.config import DEV_MODE, MAX_STARS
from ..core.navigation import ScreenId
from ..levels.base import LevelInfo
from ..ui.widgets import Button, Card, ScreenHeader, StarRow, StepIcon, divider, label, scrollable
from .base_screen import BaseScreen


class LevelScreen(BaseScreen):
    back_target = ScreenId.LEVEL_SELECT

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        self.level: LevelInfo | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 22, 40, 16)
        root.setSpacing(14)
        self.stars = StarRow(0, MAX_STARS, star_radius=13)
        self.header = ScreenHeader("", right=self.stars, back_text="←  Levels")
        self.header.back_clicked.connect(self.go_back)
        root.addWidget(self.header)
        self._body_host = QVBoxLayout()
        root.addLayout(self._body_host, 1)
        self._body: QWidget | None = None

    def on_enter(self, payload: Any = None) -> None:
        if isinstance(payload, LevelInfo):
            self.level = payload
        if self.level is None:  # opened without a level: nothing to show
            self.go(ScreenId.LEVEL_SELECT)
            return
        level = self.level
        self.header.set_title(f"Level {level.number}  ·  {level.title}")
        self.stars.set_stars(self.ctx.state.stars(level.id))
        self._set_body(level.play_screen(self.ctx, level) if level.is_playable
                       else self._coming_soon(level))

    def on_leave(self) -> None:
        self._set_body(None)

    def _set_body(self, widget: QWidget | None) -> None:
        if self._body is not None:
            self._body.setParent(None)
            self._body.deleteLater()
        self._body = widget
        if widget is not None:
            self._body_host.addWidget(widget)

    # --- placeholder until the level is playable ---------------------------------------
    def _coming_soon(self, level: LevelInfo) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        card = Card(padding=30, spacing=12)
        card.setMaximumWidth(760)
        card.body.addWidget(label(level.topic, "tag"), alignment=Qt.AlignmentFlag.AlignLeft)
        card.body.addWidget(label(f"“{level.briefing}”", "quote", wrap=True))
        card.body.addSpacing(6)
        card.body.addWidget(label("What this level is about", "subheading"))
        card.body.addWidget(label(level.concept, "body", wrap=True))
        card.body.addSpacing(6)
        card.body.addWidget(divider())

        soon = QHBoxLayout()
        soon.setSpacing(18)
        soon.addWidget(StepIcon("plan", 80))
        text = QVBoxLayout()
        text.addWidget(label("The playing field is still being built", "subheading"))
        text.addWidget(label("Soon you'll tune the controller here, press Run and watch the "
                             "ball follow its plan.", "body", wrap=True))
        soon.addLayout(text, 1)
        card.body.addLayout(soon)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        start = Button("Start level", variant="primary")
        start.setEnabled(False)
        start.setToolTip("Coming soon")
        buttons.addWidget(start)
        card.body.addLayout(buttons)

        if DEV_MODE:
            card.body.addWidget(divider())
            dev = QHBoxLayout()
            dev.addWidget(label("Dev: pretend I finished with", "caption"))
            for n in range(1, MAX_STARS + 1):
                b = Button("★" * n)
                b.clicked.connect(lambda _=False, n=n: self._dev_finish(n))
                dev.addWidget(b)
            dev.addStretch(1)
            card.body.addLayout(dev)

        column = QVBoxLayout()
        column.setContentsMargins(4, 4, 4, 8)
        column.addWidget(card)
        column.addStretch(1)
        outer.addLayout(column, 20)
        outer.addStretch(1)
        return scrollable(page)

    def _dev_finish(self, stars: int) -> None:
        if self.level is not None:
            self.ctx.state.record_result(self.level.id, stars)
            self.go(ScreenId.LEVEL_SELECT)
