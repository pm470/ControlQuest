""""Your experiments": the best run of each fix side by side (Level 3).

    card = ComparisonCard(data.fixes)
    card.record(result)          # after every run; keeps the best run per fix

Best = more stars, then success, then shorter time. The table lets the player see
which fix works at all and what it costs per MPC solve. Kept for this visit of
the level only (like the rest of the progress, in memory).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget

from ..engine.protocol import OUTCOMES, RunResult
from ..ui import theme
from ..ui.widgets import Card, ColorDot, StarRow, label
from .level_data import FixSpec


def _rank(r: RunResult) -> tuple:
    return (r.stars, r.success, -r.metrics.get("time", 0.0))


class ComparisonCard(Card):
    def __init__(self, fixes: list[FixSpec], parent: QWidget | None = None):
        super().__init__(parent, padding=14, spacing=8, shadow=False)
        self.body.addWidget(label("Your experiments", "subheading"))
        self.body.addWidget(label("Best run of each fix so far. Which one works, and what does it "
                                  "cost per MPC solve (ms)?", "caption", wrap=True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for c, head in enumerate(("Fix", "Best", "ms", "")):
            h = label(head, "caption")
            h.setToolTip({"Best": "Best run of this fix", "ms": "Mean time per MPC solve [ms]"}.get(head, ""))
            grid.addWidget(h, 0, c)
        self._best: dict[str, RunResult] = {}
        self._cells: dict[str, tuple] = {}
        for i, f in enumerate(fixes, start=1):
            dot = ColorDot(theme.LINE, 9)
            result = label("–", "caption")
            cell = QHBoxLayout()  # colour dot + result, one column (the side column is narrow)
            cell.setSpacing(5)
            cell.addWidget(dot)
            cell.addWidget(result, 1)
            ms = label("–", "caption")
            stars = StarRow(0, 3, star_radius=6)
            grid.addWidget(label(f.label, "body", wrap=True), i, 0)
            grid.addLayout(cell, i, 1)
            grid.addWidget(ms, i, 2, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(stars, i, 3)
            self._cells[f.id] = (dot, result, ms, stars)
        grid.setColumnStretch(0, 1)
        self.body.addLayout(grid)

    def record(self, r: RunResult) -> None:
        fix = r.fix
        if fix not in self._cells:
            return
        best = self._best.get(fix)
        if best is not None and _rank(best) >= _rank(r):
            return
        self._best[fix] = r
        dot, result, ms, stars = self._cells[fix]
        title, color = OUTCOMES.get(r.outcome, (r.outcome, "NEUTRAL"))
        dot.set_color(getattr(theme, color))
        t = r.metrics.get("time", 0.0)
        result.setText(f"{t:.1f} s" if r.success else title)
        result.setProperty("role", "body")
        result.style().unpolish(result)
        result.style().polish(result)
        ms.setText(f"{r.metrics.get('mean_solve_ms', 0.0):.2f}")
        stars.set_stars(r.stars)
