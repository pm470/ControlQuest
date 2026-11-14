"""Pick one MPC solve of the run: "‹ [k] /n ›", in the replay well under the map.

Follows the replay while it plays; choosing a solve emits solve_selected(k)
(0-based), and the level pauses the replay at that solve's time, so the map shows
exactly the plan computed in that solve. The number can be typed (Enter). When the
solve was computed is shown in the tooltip and in the solver info ("This solve").
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from ..ui import theme
from ..ui.widgets import Button, label


class SolveSelector(QWidget):
    solve_selected = Signal(int)  # 0-based solve index

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._dt = 0.1
        self._times: list[float] | None = None
        self._n = 0
        self._k = 0
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        self.prev_button = Button("‹", variant="chip")
        self.prev_button.setFixedWidth(30)
        self.prev_button.setToolTip("Previous MPC solve")
        self.field = QLineEdit("–")
        self.field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.field.setFixedWidth(48)
        self.field.setStyleSheet(f"font-size: 13px; font-weight: 800; padding: 2px 5px; "
                                 f"border-radius: 10px; background: {theme.SURFACE};")
        self._validator = QIntValidator(1, 1, self)
        self.field.setValidator(self._validator)
        self.of_label = label("/0", "caption")
        self.of_label.setStyleSheet(f"font-weight: 800; color: {theme.MUTED};")
        self.next_button = Button("›", variant="chip")
        self.next_button.setFixedWidth(30)
        self.next_button.setToolTip("Next MPC solve")
        row.addWidget(self.prev_button)
        row.addWidget(self.field)
        row.addWidget(self.of_label)
        row.addWidget(self.next_button)

        self.prev_button.clicked.connect(lambda: self._select(self._k - 1))
        self.next_button.clicked.connect(lambda: self._select(self._k + 1))
        self.field.editingFinished.connect(self._on_typed)
        self.set_count(0, 0.1)

    def set_count(self, n: int, dt: float, times: list[float] | None = None) -> None:
        """n solves in the current run (0 = no run yet). times: when each solve was computed
        (default: one solve per dt; Level 5 re-plans less often)."""
        self._dt, self._times, self._n, self._k = dt, times, n, 0
        self._validator.setRange(1, max(1, n))
        self.of_label.setText(f"/{n}")
        for w in (self.prev_button, self.field, self.next_button):
            w.setEnabled(n > 0)
        self._show(0)

    def set_current(self, k: int) -> None:
        """Follow the replay (does not emit solve_selected)."""
        if not self.field.hasFocus():
            self._show(k)

    def _select(self, k: int) -> None:
        if self._n <= 0:
            return
        k = max(0, min(k, self._n - 1))
        self._show(k)
        self.solve_selected.emit(k)

    def _on_typed(self) -> None:
        text = self.field.text().strip()
        if text.isdigit():
            self._select(int(text) - 1)
        else:
            self._show(self._k)

    def _show(self, k: int) -> None:
        self._k = k
        self.field.setText(str(k + 1) if self._n > 0 else "–")
        times = self._times
        t = times[k] if times and 0 <= k < len(times) else k * self._dt
        self.field.setToolTip(f"MPC solve {k + 1}, computed at t = {t:.1f} s. Type a number and press "
                              "Enter to jump to it." if self._n > 0 else "MPC solve (press Run first)")
