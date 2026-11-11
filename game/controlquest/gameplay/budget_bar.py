"""A battery-style bar for a budget (Level 1: energy; later Level 5: solves).

Drains as the budget is used; turns orange and red when it runs low. A small
star marks the ★★★ par (use at most this much).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui import painting, theme


class BudgetBar(QWidget):
    def __init__(self, title: str, budget: float, par: float | None = None, unit: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._title, self._budget, self._par, self._unit = title, budget, par, unit
        self._used = 0.0
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_used(self, used: float) -> None:
        self._used = max(0.0, used)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        left = self._budget - self._used
        frac = max(0.0, min(1.0, left / self._budget)) if self._budget > 0 else 0.0

        p.setPen(QColor(theme.INK))
        p.setFont(theme.font(15, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, w, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)
        p.setPen(QColor(theme.DANGER if left < 0 else theme.INK_SOFT))
        p.setFont(theme.font(14, QFont.Weight.DemiBold))
        used = f"{self._used:.0f}" if float(self._used).is_integer() else f"{self._used:.2f}"
        p.drawText(QRectF(0, 0, w, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"used {used} / {self._budget:g}{self._unit}")

        body = QRectF(1, 30, w - 12, 26)
        p.setPen(QPen(QColor(theme.INK_SOFT), 2))
        p.setBrush(QColor(theme.SURFACE))
        p.drawRoundedRect(body, 8, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.INK_SOFT))
        p.drawRoundedRect(QRectF(body.right() + 2, body.top() + 7, 6, 12), 2, 2)  # battery nub

        color = theme.SUCCESS if frac > 0.5 else theme.WARNING if frac > 0.2 else theme.DANGER
        inner = body.adjusted(4, 4, -4, -4)
        if frac > 0:
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width() * frac, inner.height()), 5, 5)

        if self._par is not None and self._budget > 0:  # ★★★ mark: stay right of it
            x = inner.left() + inner.width() * max(0.0, 1 - self._par / self._budget)
            p.setPen(QPen(QColor(theme.STAR_DARK), 2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, body.top() - 2), QPointF(x, body.bottom() + 2))
            painting.draw_star(p, QPointF(x, body.top() - 5), 5)
