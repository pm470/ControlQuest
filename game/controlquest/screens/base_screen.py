"""Base class for all screens (one full-window page each).

A screen:
- gets the shared AppContext in its constructor,
- asks for navigation by calling self.go(ScreenId.X, payload) (never touches
  other screens directly),
- is created once and reused; on_enter(payload) / on_leave() are called when it
  is shown / hidden (start and stop timers there),
- sets `back_target` if Esc / the back button should lead somewhere.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..core.context import AppContext
from ..core.navigation import ScreenId
from ..ui import painting, theme


class BaseScreen(QWidget):
    navigate = Signal(str, object)  # (ScreenId value, payload)

    back_target: ScreenId | None = None
    show_dot_grid: bool = True

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx

    # --- lifecycle hooks (override as needed) ---------------------------------------
    def on_enter(self, payload: Any = None) -> None:
        """Called every time the screen becomes visible."""

    def on_leave(self) -> None:
        """Called when another screen replaces this one."""

    # --- navigation ------------------------------------------------------------------------
    def go(self, screen: ScreenId, payload: Any = None) -> None:
        self.navigate.emit(screen.value, payload)

    def go_back(self) -> None:
        if self.back_target is not None:
            self.go(self.back_target)

    # --- background ----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BACKGROUND))
        if self.show_dot_grid:
            painting.draw_dot_grid(p, QRectF(self.rect()), self.devicePixelRatioF())
