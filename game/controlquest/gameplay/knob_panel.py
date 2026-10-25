"""Knobs a level unlocks (slider + typed value), built from the level file (PRD 5.4).

Weights use logarithmic sliders: only ratios matter, and useful values span decades.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSlider, QToolTip, QVBoxLayout, QWidget

from ..ui.widgets import label
from .level_data import KnobSpec

STEPS_PER_DECADE = 100  # log slider resolution


def format_value(v: float) -> str:
    return f"{v:.4g}" if 1e-3 <= abs(v) < 1e5 else f"{v:.2e}"


class KnobRow(QWidget):
    """One knob: name, a value field you can type into, and a slider.

    Typing a number (Enter or leaving the field) sets the exact value and moves the
    slider; moving the slider sets the value from the slider. Values are clamped to
    [min, max] of the level file; invalid text is rejected.
    """

    changed = Signal()

    def __init__(self, spec: KnobSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.spec = spec
        self._value = spec.default
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        top = QHBoxLayout()
        name = label(f"<b>{spec.symbol}</b>&nbsp;&nbsp;{spec.label}", "body")
        name.setTextFormat(Qt.TextFormat.RichText)
        self.edit = QLineEdit()
        self.edit.setProperty("role", "knob_value")
        self.edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit.setFixedWidth(92)
        self.edit.setToolTip(f"Type a value between {format_value(spec.min)} and "
                             f"{format_value(spec.max)}, then press Enter")
        top.addWidget(name, 1)
        top.addWidget(self.edit)
        col.addLayout(top)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        if spec.scale == "log":
            self._lo = math.log10(spec.min)
            self.slider.setRange(0, round((math.log10(spec.max) - self._lo) * STEPS_PER_DECADE))
        else:
            self.slider.setRange(0, 1000)
        col.addWidget(self.slider)
        name.setToolTip(spec.help)
        self.slider.setToolTip(spec.help)
        self.slider.valueChanged.connect(self._on_slider)
        self.edit.editingFinished.connect(self._on_edit)
        self.set_value(spec.default)

    # --- slider position <-> value ------------------------------------------------------
    def _to_value(self, pos: int) -> float:
        if self.spec.scale == "log":
            return 10 ** (self._lo + pos / STEPS_PER_DECADE)
        return self.spec.min + (self.spec.max - self.spec.min) * pos / 1000

    def _to_pos(self, value: float) -> int:
        value = self._clamp(value)
        if self.spec.scale == "log":
            return round((math.log10(value) - self._lo) * STEPS_PER_DECADE)
        return round(1000 * (value - self.spec.min) / (self.spec.max - self.spec.min))

    def _clamp(self, value: float) -> float:
        return min(max(value, self.spec.min), self.spec.max)

    # --- public -------------------------------------------------------------------------
    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Set the value (clamped) and move the slider; emits changed if it changed."""
        old = self._value
        self._value = self._clamp(float(value))
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_pos(self._value))
        self.slider.blockSignals(False)
        self.edit.setText(format_value(self._value))
        if self._value != old:
            self.changed.emit()

    # --- user input ---------------------------------------------------------------------
    def _on_slider(self, pos: int) -> None:
        v = self._to_value(pos)
        # round numbers from the slider (2 significant digits, e.g. 3.0, 0.098, 12);
        # exactly the default when the slider sits on it. Typed values keep full precision.
        v = self.spec.default if pos == self._to_pos(self.spec.default) else float(f"{v:.2g}")
        v = self._clamp(v)
        self._value = v
        self.edit.setText(format_value(v))
        self.changed.emit()

    def _on_edit(self) -> None:
        text = self.edit.text().strip().replace(",", ".")
        try:
            typed = float(text)
            if not math.isfinite(typed):
                raise ValueError
        except ValueError:
            QToolTip.showText(self.edit.mapToGlobal(self.edit.rect().bottomLeft()),
                              f"'{text}' is not a number", self.edit)
            self.edit.setText(format_value(self._value))  # revert
            return
        if typed != self._clamp(typed):
            QToolTip.showText(self.edit.mapToGlobal(self.edit.rect().bottomLeft()),
                              f"Allowed range: {format_value(self.spec.min)} to "
                              f"{format_value(self.spec.max)}", self.edit)
        self.set_value(typed)


class KnobPanel(QWidget):
    """All knob rows of a level. Emits changed() when any value changes."""

    changed = Signal()

    def __init__(self, specs: list[KnobSpec], parent: QWidget | None = None):
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        self.rows = [KnobRow(spec) for spec in specs]
        for row in self.rows:
            row.changed.connect(self.changed)
            col.addWidget(row)

    def values(self) -> dict[str, float]:
        return {row.spec.name: row.value() for row in self.rows}

    def set_values(self, values: dict[str, float]) -> None:
        for row in self.rows:
            if row.spec.name in values:
                row.set_value(values[row.spec.name])

    def reset(self) -> None:
        for row in self.rows:
            row.set_value(row.spec.default)
