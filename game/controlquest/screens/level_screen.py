"""Level screen: hosts one level, in one of four views (self._view):

    "intro"    the level intro (gameplay/level_intro.py, if the level file sets `intro`)
    "play"     the gameplay widget built by `play_screen` (usually a LevelPlayWidget)
    "debrief"  the Research debrief (gameplay/research_debrief.py, if the level has research
               content in controlquest/research/): from the result card's "Insights" (with
               the latest run) or from the intro's "Research background" (no run yet)
    "other"    the "coming soon" card of a level that is not playable yet

Opening a level (from the level select or "Next level") shows its intro first; "Start level"
shows the play view. Back: debrief -> where it was opened from; play -> intro; intro -> the
level select. The play view is kept while the player stays in the level (knobs, last run,
replay position, experiments survive a look at the intro or the debrief); leaving the level
or opening another one starts fresh. A body widget with a `navigate` signal (str, object)
can ask for another screen, e.g. "Next level".
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..core.config import DEV_MODE, MAX_STARS
from ..core.navigation import ScreenId
from ..gameplay.level_data import load_level_data
from ..gameplay.level_intro import LevelIntroWidget
from ..gameplay.research_debrief import ResearchDebriefWidget
from ..levels.base import LevelInfo
from ..research import research_for
from ..ui.math_text import math_text
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
        self._debrief: ResearchDebriefWidget | None = None  # built when first opened
        self._other: QWidget | None = None  # the "coming soon" card
        self._view = ""  # "intro" | "play" | "debrief" | "other"
        self._debrief_from = "play"  # where Back on the debrief returns to
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
            self._view = "other"
            self.header.set_back_text("Back to the levels")
        elif level.intro is None:
            self.show_play()
        else:
            self.show_intro()

    def on_leave(self) -> None:
        self._clear()

    def go_back(self) -> None:
        """Debrief -> where it was opened from; play -> intro; intro -> the level select."""
        if self._view == "debrief":
            self.show_play() if self._debrief_from == "play" else self.show_intro()
        elif self._view == "play" and self._intro is not None:
            self.show_intro()
        else:
            super().go_back()

    # --- intro and play screen -----------------------------------------------------------
    def show_intro(self) -> None:
        level = self.level
        if self._intro is None:
            # the tutorial's intro has no research link (its debrief opens from its result card)
            research = research_for(level.id) is not None and not level.tutorial
            self._intro = self._add(LevelIntroWidget(level, load_level_data(level.id),
                                                     research=research))
            self._intro.start.connect(self.show_play)
            self._intro.research.connect(lambda: self.show_debrief(from_intro=True))
        self._pause_play()  # don't keep replaying behind the intro
        self._show(self._intro)
        self._view = "intro"
        self.header.set_back_text("Back to the levels")

    def show_play(self) -> None:
        if self._play is None:
            self._play = self._add(self.level.play_screen(self.ctx, self.level))
            if hasattr(self._play, "insights_requested"):
                self._play.insights_requested.connect(lambda: self.show_debrief(from_intro=False))
        self._show(self._play)
        self._view = "play"
        self.header.set_back_text("Back to the level intro" if self._intro is not None
                                  else "Back to the levels")

    def show_debrief(self, from_intro: bool = False) -> None:
        """The Research debrief: from the intro without a run, from the play view with the
        play view's latest run (its numbers and one of the level's visuals)."""
        info = research_for(self.level.id)
        if info is None:
            return
        if self._debrief is None:
            self._debrief = self._add(ResearchDebriefWidget(self.level, info))
            self._debrief.back.connect(self.go_back)
            self._debrief.start.connect(self.show_play)
            self._debrief.next_level.connect(self._next_level)
        play = self._play
        result = None if from_intro or play is None else getattr(play, "result", None)
        if result is None:
            self._debrief.show_run(None, from_intro=from_intro)
        else:
            # "Next level" exactly when the result card offers it (after a success, unlocked)
            self._debrief.show_run(result, play.debrief_rows(result), play.debrief_visual(result),
                                   can_next=result.success and play.next_unlocked())
        self._pause_play()
        self._debrief_from = "intro" if from_intro else "play"
        self._show(self._debrief)
        self._view = "debrief"
        self.header.set_back_text("Back to the level intro" if from_intro else "Back to the level")

    def _next_level(self) -> None:
        nxt = self.ctx.next_level(self.level)
        if nxt is not None:
            self.go(ScreenId.LEVEL, nxt)

    def _pause_play(self) -> None:
        if self._play is not None and hasattr(self._play, "playback"):
            self._play.playback.pause()

    def _add(self, widget: QWidget) -> QWidget:
        widget.hide()
        self._body_host.addWidget(widget)
        if hasattr(widget, "navigate"):
            widget.navigate.connect(self.navigate)
        return widget

    def _show(self, widget: QWidget) -> None:
        for w in (self._intro, self._play, self._debrief, self._other):
            if w is not None and w is not widget:
                w.hide()
        widget.show()

    def _clear(self) -> None:
        for w in (self._intro, self._play, self._debrief, self._other):
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._intro = self._play = self._debrief = self._other = None
        self._view = ""

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
        card.body.addWidget(math_text(level.concept, "body"))
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
