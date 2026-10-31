"""Pick one MPC solve of the run: "MPC solve ‹ [k] › of n  ·  t = 12.3 s".

Follows the replay while it plays; choosing a solve emits solve_selected(k)
(0-based), and the level pauses the replay at that solve's time, so the map shows
exactly the plan computed in that solve.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSpinBox, QWidget

from ..ui.widgets import Button, label


class SolveSelector(QWidget):
    solve_selected = Signal(int)  # 0-based solve index

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._dt = 0.1
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(label("MPC solve", "subheading"))
        self.prev_button = Button("‹", variant="default")
        self.prev_button.setStyleSheet("padding: 4px 0px; font-size: 20px;")
        self.prev_button.setFixedWidth(42)
        self.prev_button.setToolTip("Previous solve")
        self.spin = QSpinBox()
        self.spin.setRange(1, 1)
        self.spin.setToolTip("Type a solve number, or use the arrow keys")
        self.spin.setFixedWidth(84)
        self.next_button = Button("›", variant="default")
        self.next_button.setStyleSheet("padding: 4px 0px; font-size: 20px;")
        self.next_button.setFixedWidth(42)
        self.next_button.setToolTip("Next solve")
        self.of_label = label("of 0", "body")
        self.time_label = label("", "caption")
        row.addWidget(self.prev_button)
        row.addWidget(self.spin)
        row.addWidget(self.next_button)
        row.addWidget(self.of_label)
        row.addStretch(1)
        row.addWidget(self.time_label)

        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button.clicked.connect(lambda: self._step(+1))
        self.spin.valueChanged.connect(self._on_spin)
        self.set_count(0, 0.1)

    def set_count(self, n: int, dt: float, times: list[float] | None = None) -> None:
        """n solves in the current run (0 = no run yet). times: when each solve was computed
        (default: one solve per dt; Level 5 re-plans less often)."""
        self._dt = dt
        self._times = times
        self.spin.blockSignals(True)
        self.spin.setRange(1, max(1, n))
        self.spin.setValue(1)
        self.spin.blockSignals(False)
        self.of_label.setText(f"of {n}")
        for w in (self.prev_button, self.spin, self.next_button):
            w.setEnabled(n > 0)
        self._show_time(0)

    def set_current(self, k: int) -> None:
        """Follow the replay (does not emit solve_selected)."""
        if self.spin.value() != k + 1:
            self.spin.blockSignals(True)
            self.spin.setValue(k + 1)
            self.spin.blockSignals(False)
        self._show_time(k)

    def _step(self, d: int) -> None:
        self.spin.setValue(self.spin.value() + d)  # emits via _on_spin (clamped by the range)

    def _on_spin(self, value: int) -> None:
        self._show_time(value - 1)
        self.solve_selected.emit(value - 1)

    def _show_time(self, k: int) -> None:
        times = getattr(self, "_times", None)
        t = times[k] if times and 0 <= k < len(times) else k * self._dt
        self.time_label.setText(f"computed at t = {t:.1f} s" if self.spin.isEnabled() else "")
