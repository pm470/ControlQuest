"""The card shown over the map when a run's replay ends (PRD 5.7):
outcome, stars, the level's metric rows, "What happened", and next actions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget

from ..core.config import MAX_STARS
from ..engine.protocol import OUTCOMES, RunResult
from ..ui import theme
from ..ui.widgets import Button, Card, ColorDot, StarRow, divider, label


class ResultPanel(Card):
    watch_again = Signal()
    try_again = Signal()
    next_level = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, padding=24, spacing=10)
        self.setMaximumWidth(460)

        top = QHBoxLayout()
        self._dot = ColorDot(theme.SUCCESS, 16)
        self._title = label("", "heading")
        self._stars = StarRow(0, MAX_STARS, star_radius=14)
        top.addWidget(self._dot)
        top.addWidget(self._title, 1)
        top.addWidget(self._stars)
        self.body.addLayout(top)

        self._rows = QGridLayout()
        self._rows.setHorizontalSpacing(14)
        self._rows.setVerticalSpacing(4)
        self.body.addLayout(self._rows)
        self.body.addWidget(divider())
        self._messages = QWidget()
        self._messages_layout = QGridLayout(self._messages)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setVerticalSpacing(6)
        self.body.addWidget(self._messages)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._watch = Button("Replay", variant="ghost")
        self._retry = Button("Retry")
        self._retry.setToolTip("Close this card, change the knobs and run again")
        self._next = Button("Next level  ›", variant="primary")
        buttons.addWidget(self._watch)
        buttons.addStretch(1)
        buttons.addWidget(self._retry)
        buttons.addWidget(self._next)
        self.body.addLayout(buttons)

        self._watch.clicked.connect(self.watch_again)
        self._retry.clicked.connect(self.try_again)
        self._next.clicked.connect(self.next_level)

    def show_result(self, result: RunResult, rows: list[tuple[str, str, str]],
                    can_go_next: bool) -> None:
        """rows: (name, value, note) per metric, e.g. ("Time", "26.8 s", "★★ ≤ 30 s")."""
        title, color_name = OUTCOMES.get(result.outcome, (result.outcome, "NEUTRAL"))
        self._dot.set_color(getattr(theme, color_name))
        self._title.setText(title)
        self._stars.set_stars(result.stars)

        _clear(self._rows)
        for i, (name, value, note) in enumerate(rows):
            self._rows.addWidget(label(name, "body"), i, 0)
            self._rows.addWidget(label(value, "subheading"), i, 1)
            self._rows.addWidget(label(note, "caption"), i, 2)
        self._rows.setColumnStretch(2, 1)

        _clear(self._messages_layout)
        for i, msg in enumerate(result.messages):
            self._messages_layout.addWidget(label(msg, "body", wrap=True), i, 0)

        self._next.setVisible(result.success and can_go_next)
        self.show()
        self.raise_()


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
