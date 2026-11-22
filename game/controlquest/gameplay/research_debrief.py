"""The Research debrief of a level (reduced scope, AGENTS.md section 8, 2026-11-19).

Opened from the result card ("Insights", after any outcome) or from the level intro
("Research background", no run yet). Two tiles like the level intro, each scrolling its own
content, the main button pinned at the bottom of the right tile:

- left: the research question (headline) and the takeaway; a well "Your latest run" (outcome,
  the level's result rows, and one of the level's existing visuals frozen at the run's end;
  right under the takeaway so it is visible without scrolling); "The problem"; "Why it
  matters"; "What this level showed"; "Limits of this level";
- right: "What research does": two paper cards (title, authors, venue, problem, approach,
  link to this level; links open in the browser only when clicked), then the buttons:
  "‹ Back to the level" + "Next level ›" (only when the result card offers it), or
  "Start level ▶" when opened from the intro.

The static content comes from controlquest/research/<level_id>.py; nothing is fetched online.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..core.config import MAX_STARS
from ..engine.protocol import OUTCOMES, RunResult
from ..levels.base import LevelInfo
from ..research import PaperRef, ResearchInfo
from ..ui import theme
from ..ui.math_text import align_baselines, math_text, to_plain
from ..ui.widgets import Button, Card, ColorDot, StarRow, label, scrollable, well
from .level_intro import MAX_WIDTH, SECTION_GAP, TILE_PADDING, _Content


def _open(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def run_summary(result: RunResult) -> str:
    """One sentence about the run: a time to the target only for a success."""
    m = result.metrics
    t = m.get("time", result.trajectory.duration)
    if result.success:
        return f"Reached the target in {t:.1f} s."
    title = OUTCOMES.get(result.outcome, (result.outcome, ""))[0]
    left = m.get("distance_left")
    where = f", {left:.1f} m from the target" if left is not None else ""
    return f"{title}: stopped after {t:.1f} s{where}."


class ResearchDebriefWidget(QWidget):
    back = Signal()  # "‹ Back to the level"
    next_level = Signal()  # "Next level ›"
    start = Signal()  # "Start level ▶" (opened from the intro)

    def __init__(self, level: LevelInfo, info: ResearchInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.level, self.info = level, info

        # --- left tile: question, takeaway, problem, relevance, this level, limits ---
        left = _Content()
        left.body.addWidget(label("Research question", "eyebrow"))
        left.body.addWidget(math_text(info.question, "quote"))
        left.body.addSpacing(6)
        left.body.addWidget(math_text(info.takeaway, "goal"))
        left.body.addSpacing(10)
        # the player's own run first (decided 2026-11-19: visible without scrolling)
        self.run_well = well()
        self._run = QVBoxLayout(self.run_well)
        self._run.setContentsMargins(16, 12, 16, 14)
        self._run.setSpacing(8)
        left.body.addWidget(self.run_well)
        left.body.addSpacing(SECTION_GAP)
        self._section(left.body, "The problem", info.problem)
        left.body.addSpacing(SECTION_GAP)
        self._section(left.body, "Why it matters", info.relevance)
        left.body.addSpacing(SECTION_GAP)
        self._section(left.body, "What this level showed", info.shown)
        left.body.addSpacing(SECTION_GAP)
        self._section(left.body, "Limits of this level", info.limits)
        left.body.addStretch(1)

        # --- right tile: the two papers, then the buttons ---
        right = _Content()
        right.body.addWidget(label("What research does", "eyebrow"))
        right.body.addWidget(math_text("Two recent papers on this problem. The summaries paraphrase "
                                       "their abstracts; links open in your browser.", "caption"))
        self.paper_cards = []
        for paper in info.papers:
            right.body.addSpacing(8)
            card = self._paper(paper)
            self.paper_cards.append(card)
            right.body.addWidget(card)
        right.body.addStretch(1)

        self.back_button = Button("‹  Back to the level", scale="tall")
        self.back_button.setToolTip("Back to the play screen (your run is kept)")
        self.next_button = Button("Next level  ›", variant="primary", scale="large")
        self.start_button = Button("Start level  ▶", variant="primary", scale="large")
        self.start_button.setToolTip("Tune the controller and run it")
        self.back_button.clicked.connect(self.back)
        self.next_button.clicked.connect(self.next_level)
        self.start_button.clicked.connect(self.start)
        self._foot = QHBoxLayout()
        self._foot.setContentsMargins(TILE_PADDING, 8, TILE_PADDING, TILE_PADDING)
        self._foot.setSpacing(10)
        for b in (self.back_button, self.next_button, self.start_button):
            self._foot.addWidget(b)

        # --- two tiles side by side (like the level intro) ---
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addStretch(1)
        for content, foot in ((left, None), (right, self._foot)):
            outer = Card(padding=0, spacing=0, shadow=False)
            outer.setMaximumWidth((MAX_WIDTH - 16) // 2)
            outer.body.addWidget(scrollable(content), 1)
            if foot is not None:
                outer.body.addLayout(foot)
            root.addWidget(outer, 1000)
        root.addStretch(1)
        self.show_run(None)

    # --- the latest run -----------------------------------------------------------------------
    def show_run(self, result: RunResult | None, rows: list[tuple[str, str, str]] = (),
                 visual: QWidget | None = None, can_next: bool = False,
                 from_intro: bool = False) -> None:
        """Fill "What this level showed" with the run (None: "No run yet") and set the buttons:
        from the play screen Back (+ Next if the result card offers it), from the intro Start."""
        _clear(self._run)
        if result is None:
            self._run.addWidget(label("No run yet", "subheading"))
            self._run.addWidget(math_text("Run the level to see your own numbers here.", "caption"))
        else:
            head = QHBoxLayout()
            head.setSpacing(10)
            color = OUTCOMES.get(result.outcome, (result.outcome, "NEUTRAL"))[1]
            head.addWidget(ColorDot(getattr(theme, color), 12))
            head.addWidget(label("Your latest run", "subheading"), 1)
            if not self.level.tutorial:
                head.addWidget(StarRow(result.stars, MAX_STARS, star_radius=9))
            self._run.addLayout(head)
            self._run.addWidget(math_text(run_summary(result), "goal"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(4)
            for i, (name, value, note) in enumerate(rows):
                grid.addWidget(math_text(name, "body", wrap=False), i, 0)
                grid.addWidget(math_text(value, "goal", wrap=False), i, 1)
                grid.addWidget(math_text(note, "caption"), i, 2)  # notes wrap: narrow tiles
            align_baselines(grid)  # name, value and note on one baseline per row
            grid.setColumnStretch(2, 1)
            self._run.addLayout(grid)
            if visual is not None:
                self._run.addSpacing(4)
                self._run.addWidget(visual)
        self.back_button.setVisible(not from_intro)
        self.next_button.setVisible(can_next and not from_intro)
        self.start_button.setVisible(from_intro)
        # the only button left takes the whole row
        self._foot.setStretchFactor(self.back_button, 0 if self.next_button.isVisibleTo(self) else 1)
        self._foot.setStretchFactor(self.next_button, 1)
        self._foot.setStretchFactor(self.start_button, 1)

    # --- building blocks ------------------------------------------------------------------------
    @staticmethod
    def _section(layout: QVBoxLayout, eyebrow: str, text: str) -> None:
        layout.addWidget(label(eyebrow, "eyebrow"))
        layout.addWidget(math_text(text, "body"))

    @staticmethod
    def _paper(paper: PaperRef) -> QWidget:
        """One paper as a well: title, authors · year, venue, problem / approach / link, links."""
        card = well()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(6)
        v.addWidget(math_text(paper.title, "goal"))
        v.addWidget(math_text(f"{paper.authors} · {paper.year}<br><i>{paper.venue}</i>", "caption"))
        v.addSpacing(2)
        for name, text in (("Problem", paper.problem), ("Approach", paper.approach),
                           ("Link to this level", paper.connection)):
            v.addWidget(math_text(f"<b>{name}:</b> {text}", "body"))
        links = QHBoxLayout()
        links.setContentsMargins(0, 2, 0, 0)
        links.setSpacing(14)
        main = Button("Open the paper  ›", variant="link")
        main.setToolTip(paper.url)
        main.clicked.connect(lambda _=False, u=paper.url: _open(u))
        links.addWidget(main)
        if paper.free_url:
            free = Button("Free version (arXiv)  ›", variant="link")
            free.setToolTip(paper.free_url)
            free.clicked.connect(lambda _=False, u=paper.free_url: _open(u))
            links.addWidget(free)
        links.addStretch(1)
        v.addLayout(links)
        card.setToolTip(to_plain(f"[{paper.key}] {paper.title}"))
        return card


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())
            item.layout().deleteLater()
