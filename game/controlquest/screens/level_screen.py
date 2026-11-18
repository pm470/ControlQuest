"""Level screen: hosts one level.

Opening a level (from the level select or "Next level") first shows its intro
(gameplay/level_intro.py, if the level file sets `intro`); "Start level" then shows the
gameplay widget (usually a gameplay.LevelPlayWidget) built by `play_screen`. Back on the
play screen returns to the intro, Back on the intro to the level select. The play screen
is kept while the player stays in the level (knobs, last run, experiments survive a look
at the intro); leaving the level or opening another one starts fresh. Levels without
`play_screen` show a "coming soon" card with the briefing. A body widget with a `navigate`
signal (str, object) can ask for another screen, e.g. "Next level".
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..core.config import DEV_MODE, MAX_STARS
from ..core.navigation import ScreenId
from ..gameplay.level_data import load_level_data
from ..gameplay.level_intro import LevelIntroWidget
from ..levels.base import LevelInfo
from ..ui.widgets import Button, Card, ScreenHeader, StarRow, StepIcon, divider, label, scrollable
from .base_screen import BaseScreen


class LevelScreen(BaseScreen):
    back_target = ScreenId.LEVEL_SELECT

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        self.level: LevelInfo | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 18, 32, 18)
        root.setSpacing(14)
        self.stars = StarRow(0, MAX_STARS, star_radius=13)
        self.header = ScreenHeader("", right=self.stars, back_text="Back to the levels")
        self.header.back_clicked.connect(self.go_back)
        root.addWidget(self.header)
        self._body_host = QVBoxLayout()
        root.addLayout(self._body_host, 1)
        self._intro: QWidget | None = None  # the level intro (built when the level opens)
        self._play: QWidget | None = None  # the play screen (built at the first "Start level")
        self._other: QWidget | None = None  # the "coming soon" card
        self._on_play = False  # which one is shown: play screen or intro
        ctx.state.changed.connect(self._refresh_stars)

    def _refresh_stars(self) -> None:
        if self.level is not None:
            self.stars.set_stars(self.ctx.state.stars(self.level.id))

    def on_enter(self, payload: Any = None) -> None:
        if isinstance(payload, LevelInfo):
            self.level = payload
        if self.level is None:  # opened without a level: nothing to show
            self.go(ScreenId.LEVEL_SELECT)
            return
        level = self.level
        self.header.set_title(level.title)
        self.header.set_badge(level.number, level.accent)
        self.stars.set_stars(self.ctx.state.stars(level.id))
        self.stars.setVisible(not level.tutorial)  # the tutorial has no stars
        self._clear()  # a level always opens fresh (also "Next level" from the result card)
        if not level.is_playable:
            self._other = self._add(self._coming_soon(level))
            self.header.set_back_text("Back to the levels")
        elif level.intro is None:
            self.show_play()
        else:
            self.show_intro()

    def on_leave(self) -> None:
        self._clear()

    def go_back(self) -> None:
        """From the play screen back to the intro; from the intro to the level select."""
        if self._on_play and self._intro is not None:
            self.show_intro()
        else:
            super().go_back()

    # --- intro and play screen -----------------------------------------------------------
    def show_intro(self) -> None:
        level = self.level
        if self._intro is None:
            self._intro = self._add(LevelIntroWidget(level, load_level_data(level.id)))
            self._intro.start.connect(self.show_play)
        if self._play is not None and hasattr(self._play, "playback"):
            self._play.playback.pause()  # don't keep replaying behind the intro
        self._show(self._intro)
        self._on_play = False
        self.header.set_back_text("Back to the levels")

    def show_play(self) -> None:
        if self._play is None:
            self._play = self._add(self.level.play_screen(self.ctx, self.level))
        self._show(self._play)
        self._on_play = True
        self.header.set_back_text("Back to the level intro" if self._intro is not None
                                  else "Back to the levels")

    def _add(self, widget: QWidget) -> QWidget:
        widget.hide()
        self._body_host.addWidget(widget)
        if hasattr(widget, "navigate"):
            widget.navigate.connect(self.navigate)
        return widget

    def _show(self, widget: QWidget) -> None:
        for w in (self._intro, self._play, self._other):
            if w is not None and w is not widget:
                w.hide()
        widget.show()

    def _clear(self) -> None:
        for w in (self._intro, self._play, self._other):
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._intro = self._play = self._other = None
        self._on_play = False

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
