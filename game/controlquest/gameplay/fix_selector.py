"""Choose one fix for a level (Level 3): a list of small selectable cards.

    selector = FixSelector(data.fixes)      # FixSpec(id, label, idea) from the level file
    selector.changed.connect(...)           # emits the id of the chosen fix
    selector.current()                      # e.g. "horizon"

Only one fix is active at a time, so the player can see which idea solved the problem.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ..ui.widgets import label
from .level_data import FixSpec


class FixOption(QFrame):
    clicked = Signal(str)

    def __init__(self, spec: FixSpec, number: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.spec = spec
        self.setProperty("role", "choice")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(1)
        title = f"{number}. {spec.label}" if number else spec.label
        box.addWidget(label(f"<b>{title}</b>", "body"))
        self._idea = label(spec.idea, "caption", wrap=True)  # shown for the chosen fix only
        box.addWidget(self._idea)
        if spec.idea:
            self.setToolTip(spec.idea)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self._idea.setVisible(selected and bool(self.spec.idea))
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit(self.spec.id)


class FixSelector(QWidget):
    changed = Signal(str)

    def __init__(self, fixes: list[FixSpec], parent: QWidget | None = None):
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self._options: dict[str, FixOption] = {}
        number = 0
        for spec in fixes:
            number = number + 1 if spec.id != "none" else 0  # "No fix" has no number
            opt = FixOption(spec, number)
            opt.clicked.connect(self.select)
            col.addWidget(opt)
            self._options[spec.id] = opt
        self._current = fixes[0].id if fixes else ""
        if fixes:
            self._options[self._current].set_selected(True)

    def current(self) -> str:
        return self._current

    def select(self, fix_id: str) -> None:
        if fix_id == self._current or fix_id not in self._options:
            return
        self._options[self._current].set_selected(False)
        self._current = fix_id
        self._options[fix_id].set_selected(True)
        self.changed.emit(fix_id)

    def label_of(self, fix_id: str) -> str:
        opt = self._options.get(fix_id)
        return opt.spec.label if opt else fix_id
