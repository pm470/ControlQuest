"""The level intro: what the player sees after picking a level, before the play screen.

Two tiles (agreed 2026-11-17, AGENTS.md section 8):
- left, "learn": the story (briefing quote), "What you learn" (LevelInfo.concept),
  "How this level teaches it" (LevelInfo.teaching: how the default fails, the fix ideas)
  and "What you control": one line per knob (coloured chip, name, its help text from the
  level file), extra notes (Level 3: the fixes) and what stays fixed;
- right, "play": the goal, the three star conditions, "What changes in the OCP" (the
  level's OCP at the default knob values, knob parts in the knob colours, parts that are
  new in this level on a soft highlight) and the "Start level" button.
Each tile scrolls its own content; "Start level" stays visible at the bottom of the right
tile at every window size (down to 900x560, where the formulas shrink to fit).

A level provides the numbers and math with `LevelInfo.intro(data) -> LevelIntro`. Mark the
new parts of the OCP with \\new{...}, or \\newknob{name}{...} for a knob part that is new
(ui/math_render.py).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ..levels.base import LevelInfo
from ..ui.math_render import MathLabel
from ..ui.widgets import Button, Card, StarRow, label, scrollable
from .knob_panel import knob_colors, name_row
from .level_data import LevelData
from .ocp_card import OcpCard, OcpSpec

TILE_PADDING = 24
SECTION_GAP = 14  # extra space between the sections of a tile
MAX_WIDTH = 1240  # content width on very wide windows (lines stay readable)


@dataclass(frozen=True)
class LevelIntro:
    goal: str  # one or two sentences, with the level's numbers
    ocp: OcpSpec  # the OCP at the default knob values; new parts marked with \new / \newknob
    stars: tuple[str, ...] = ()  # what ★, ★★, ★★★ need ("reach the star", "within 30 s", ...);
    #                              empty for a tutorial (no stars)
    fixed: str = ""  # what the player cannot change, e.g. "N = 30, P = 10·Q"
    notes: tuple[str, ...] = ()  # extra lines under the knobs (Level 3: what each fix changes)
    ocp_title: str = "What changes in the OCP"  # Level 0: "The OCP your MPC solves"
    # a drawing under "What you learn" (Level 0: the MPC loop diagram); builds a QWidget
    illustration: Optional[Callable[[], QWidget]] = None


class _Content(QWidget):
    """The content of one tile (inside the tile's scroll area); add widgets to .body."""

    def __init__(self):
        super().__init__()
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(TILE_PADDING, TILE_PADDING, TILE_PADDING, 8)
        self.body.setSpacing(6)


def _has_new(spec: OcpSpec) -> bool:
    return any("\\new" in line for line in spec.objective + spec.constraints)


class LevelIntroWidget(QWidget):
    """The intro of one level. Emits start() when the player presses "Start level"."""

    start = Signal()

    def __init__(self, level: LevelInfo, data: LevelData, parent: QWidget | None = None):
        super().__init__(parent)
        intro = level.intro(data)

        # --- left tile: the story, what the level teaches, what the player controls ---
        learn = _Content()
        learn.body.addWidget(label(f"“{level.briefing}”", "quote", wrap=True))
        learn.body.addSpacing(SECTION_GAP + 4)
        self._section(learn.body, "What you learn", level.concept)
        if intro.illustration is not None:
            learn.body.addSpacing(8)
            learn.body.addWidget(intro.illustration())
        learn.body.addSpacing(SECTION_GAP)
        self._section(learn.body, "How this level teaches it", level.teaching)
        colors = knob_colors(data.knobs)  # same colours as the knob parts of the OCP
        if data.knobs or intro.notes or intro.fixed:  # Level 0 has nothing to control
            learn.body.addSpacing(SECTION_GAP)
            learn.body.addWidget(label("What you control", "eyebrow"))
        knobs = QVBoxLayout()
        knobs.setContentsMargins(0, 4, 0, 0)
        knobs.setSpacing(10)
        for spec in data.knobs:
            one = QVBoxLayout()
            one.setSpacing(3)
            one.addLayout(name_row(spec, colors[spec.name]))
            one.addWidget(label(spec.help, "caption", wrap=True))
            knobs.addLayout(one)
        learn.body.addLayout(knobs)
        for note in intro.notes:
            learn.body.addWidget(label(note, "caption", wrap=True))
        if intro.fixed:
            fixed = label(f"<b>Fixed:</b> {intro.fixed}", "caption", wrap=True)
            fixed.setContentsMargins(0, 4, 0, 0)
            learn.body.addWidget(fixed)
        learn.body.addStretch(1)

        # --- right tile: goal, stars, the OCP with what is new, Start ---
        play = _Content()
        self._section(play.body, "Goal", intro.goal, role="goal")
        stars = QVBoxLayout()
        stars.setContentsMargins(0, 6, 0, 0)
        stars.setSpacing(4)
        for n, text in enumerate(intro.stars, start=1):
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(StarRow(n, 3, star_radius=8))
            row.addWidget(label(text, "body", wrap=True), 1)
            stars.addLayout(row)
        if intro.stars:  # a tutorial has none
            play.body.addLayout(stars)
        play.body.addSpacing(SECTION_GAP)

        heading = QHBoxLayout()
        heading.addWidget(label(intro.ocp_title, "eyebrow"))
        heading.addStretch(1)
        if _has_new(intro.ocp):  # the key for the highlight, right of the heading
            heading.addLayout(self._new_legend())
        play.body.addLayout(heading)
        # without the play screen's caption ("re-solved every ..."): the knob lines say it
        play.body.addWidget(OcpCard(replace(intro.ocp, notes=""), title=None, knob_colors=colors))
        play.body.addStretch(1)
        self.start_button = Button("Start level  ▶", variant="primary", scale="large")
        self.start_button.setToolTip("Tune the controller and run it")
        self.start_button.clicked.connect(self.start)

        # --- two tiles side by side; each scrolls its content, Start stays at the bottom ---
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addStretch(1)  # centred on very wide windows (tiles grow up to MAX_WIDTH / 2)
        for content, bottom in ((learn, None), (play, self.start_button)):
            outer = Card(padding=0, spacing=0, shadow=False)
            outer.setMaximumWidth((MAX_WIDTH - 16) // 2)
            outer.body.addWidget(scrollable(content), 1)
            if bottom is not None:
                foot = QHBoxLayout()
                foot.setContentsMargins(TILE_PADDING, 8, TILE_PADDING, TILE_PADDING)
                foot.addWidget(bottom)
                outer.body.addLayout(foot)
            root.addWidget(outer, 1000)
        root.addStretch(1)

    @staticmethod
    def _section(layout: QVBoxLayout, eyebrow: str, text: str, role: str = "body") -> None:
        layout.addWidget(label(eyebrow, "eyebrow"))
        layout.addWidget(label(text, role, wrap=True))

    @staticmethod
    def _new_legend() -> QHBoxLayout:
        """One line under the OCP: the highlight means 'new in this level'."""
        row = QHBoxLayout()
        row.setSpacing(6)
        sample = MathLabel(r"\new{\mathrm{new}}", size_px=13)
        sample.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sample.setFixedWidth(sample.sizeHint().width())
        row.addWidget(sample)
        row.addWidget(label("in this level", "caption"))
        return row
