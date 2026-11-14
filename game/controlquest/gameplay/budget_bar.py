"""A budget bar under the map (Level 1: battery energy; Level 5: MPC solves).

One row: name, a rounded bar that fills as the budget is used, "used / budget".
A small star-coloured tick marks the ★★★ par (stay left of it). The bar turns red
when the budget is used up.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui import theme


class BudgetBar(QWidget):
    HEIGHT = 30

    def __init__(self, title: str, budget: float, par: float | None = None, unit: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._title, self._budget, self._par, self._unit = title, budget, par, unit
        self._used = 0.0
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_used(self, used: float) -> None:
        self._used = max(0.0, used)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        frac = max(0.0, min(1.0, self._used / self._budget)) if self._budget > 0 else 0.0

        # name (left) and "used / budget" (right)
        name_font = theme.font(14, QFont.Weight.Black)
        p.setFont(name_font)
        p.setPen(QColor(theme.INK))
        name_w = QFontMetricsF(name_font).horizontalAdvance(self._title) + 14
        p.drawText(QRectF(4, 0, name_w, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)
        used = f"{self._used:.0f}" if float(self._used).is_integer() else f"{self._used:.1f}"
        value = f"{used}"
        rest = f" / {self._budget:g}{self._unit}"
        value_font, rest_font = theme.font(14, QFont.Weight.Black), theme.font(14, QFont.Weight.Bold)
        vw = QFontMetricsF(value_font).horizontalAdvance(value)
        rw = QFontMetricsF(rest_font).horizontalAdvance(rest)
        x_text = w - 4 - rw - vw
        p.setFont(value_font)
        p.setPen(QColor(theme.DANGER if frac >= 1 else theme.INK))
        p.drawText(QRectF(x_text, 0, vw + 1, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)
        p.setFont(rest_font)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(x_text + vw, 0, rw + 1, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, rest)

        # the bar
        bar = QRectF(name_w, h / 2 - 8, max(10.0, x_text - 14 - name_w), 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.WELL))
        p.drawRoundedRect(bar, 8, 8)
        if frac > 0:
            p.setBrush(QColor(theme.DANGER if frac >= 1 else theme.PRIMARY))
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), max(16.0, bar.width() * frac), bar.height()), 8, 8)
        if self._par is not None and self._budget > 0:  # ★★★ par: a star-coloured tick
            x = bar.left() + bar.width() * min(1.0, self._par / self._budget)
            p.setBrush(QColor(theme.STAR_DARK))
            p.drawRoundedRect(QRectF(x - 2, bar.top() - 4, 4, bar.height() + 8), 2, 2)
