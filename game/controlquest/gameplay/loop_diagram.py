"""The MPC loop as a small drawing (Level 0's intro): four steps in a clockwise cycle.

    ┌ 1 Measure ┐ ──▶ ┌ 2 Predict  ┐
         ▲          every         │
         │         Δt = 0.1 s     ▼
    ┌ 4 Apply   ┐ ◀── ┌ 3 Optimise ┐

Flat, borderless tonal chips in the knob colours (coral, blue, mint, lilac), soft arrows,
no formulas drawn as text (design rules, AGENTS.md section 10).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui import theme
from ..ui.math_render import _DPR_EVENTS
from ..ui.math_text import MATH_SCALE, inline_image

STEPS = [  # (title, subtitle)
    ("Measure", "position & speed"),
    ("Predict", "with the model"),
    ("Optimise", "pick the best plan"),
    ("Apply", "only the first input"),
]
CHIP_H, GAP_X, GAP_Y = 62, 56, 38  # chip height, room for the arrows between the chips


class LoopDiagram(QWidget):
    def __init__(self, dt: float = 0.1, parent: QWidget | None = None):
        super().__init__(parent)
        self._dt = dt
        self._prepare_math()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(2 * CHIP_H + GAP_Y + 8)
        self.setToolTip("The MPC loop: it runs once every Δt, for the whole run")

    def sizeHint(self) -> QSize:
        return QSize(420, self.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(300, self.height())

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = min(self.width(), 520)
        left = (self.width() - w) / 2
        chip_w = (w - GAP_X) / 2
        top = 2.0
        cells = [  # clockwise: top-left, top-right, bottom-right, bottom-left
            QRectF(left, top, chip_w, CHIP_H),
            QRectF(left + chip_w + GAP_X, top, chip_w, CHIP_H),
            QRectF(left + chip_w + GAP_X, top + CHIP_H + GAP_Y, chip_w, CHIP_H),
            QRectF(left, top + CHIP_H + GAP_Y, chip_w, CHIP_H),
        ]
        for i, (rect, (title, sub)) in enumerate(zip(cells, STEPS)):
            self._chip(p, rect, i, title, sub)

        # arrows between the chips (clockwise)
        pen = QPen(QColor(theme.MUTED), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        a, b, c, d = cells
        y_top, y_bot = a.center().y(), c.center().y()
        self._arrow(p, QPointF(a.right() + 8, y_top), QPointF(b.left() - 8, y_top))
        self._arrow(p, QPointF(b.center().x(), b.bottom() + 6), QPointF(c.center().x(), c.top() - 6))
        self._arrow(p, QPointF(c.left() - 8, y_bot), QPointF(d.right() + 8, y_bot))
        self._arrow(p, QPointF(d.center().x(), d.top() - 6), QPointF(a.center().x(), a.bottom() + 6))

        # in the middle: how often the loop runs ("repeat every Δt = 0.1 s", Δt in the LaTeX font)
        p.setPen(QColor(theme.INK_SOFT))
        p.setFont(theme.font(theme.FS_SMALL, QFont.Weight.Bold))
        fm = p.fontMetrics()
        mid = QRectF(a.left(), a.bottom(), c.right() - a.left(), GAP_Y)
        before, after = "repeat every ", " s"
        if self._math is None:  # not typeset (yet): plain text, never render while painting
            p.drawText(mid, Qt.AlignmentFlag.AlignCenter, f"repeat every Δt = {self._dt:g} s")
            return
        img, depth = self._math
        dpr = img.devicePixelRatio()
        width = fm.horizontalAdvance(before) + img.width() / dpr + fm.horizontalAdvance(after)
        x = mid.center().x() - width / 2
        baseline = mid.center().y() + (fm.ascent() - fm.descent()) / 2
        p.drawText(QPointF(x, baseline), before)
        x += fm.horizontalAdvance(before)
        p.drawImage(QPointF(x, baseline - img.height() / dpr + depth), img)
        p.drawText(QPointF(x + img.width() / dpr, baseline), after)

    def _prepare_math(self) -> None:
        """Typeset Δt = ... for this display's pixel ratio (outside paintEvent). Bold like the
        words around it (2026-11-22), with the OCP's letters: inline_image(weight=700)."""
        self._dpr = self.devicePixelRatioF() or 1.0
        self._math = inline_image(rf"\Delta t = {self._dt:g}", 11 * MATH_SCALE, theme.INK_SOFT,
                                  self._dpr, weight=700)  # the words: theme.font(FS_SMALL, Bold)

    def event(self, e) -> bool:
        if e.type() in _DPR_EVENTS and abs(self.devicePixelRatioF() - self._dpr) > 1e-6:
            self._prepare_math()
            self.update()
        return super().event(e)

    @staticmethod
    def _chip(p: QPainter, rect: QRectF, i: int, title: str, sub: str) -> None:
        kc = theme.knob_color(i)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(kc.tint))
        p.drawRoundedRect(rect, 14, 14)
        # number in a round badge
        r = 13
        c = QPointF(rect.left() + 12 + r, rect.center().y())
        p.setBrush(QColor(kc.main))
        p.drawEllipse(c, r, r)
        p.setPen(QColor("white"))
        p.setFont(theme.font(theme.FS_SMALL, QFont.Weight.Black))
        p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, str(i + 1))
        # title + subtitle
        text = QRectF(c.x() + r + 9, rect.top() + 8, rect.right() - c.x() - r - 15, rect.height() - 16)
        p.setPen(QColor(kc.ink))
        p.setFont(theme.font(theme.FS_BODY, QFont.Weight.ExtraBold))
        p.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, title)
        p.setPen(QColor(theme.INK_SOFT))
        p.setFont(theme.font(theme.FS_MICRO, QFont.Weight.DemiBold))
        p.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                   p.fontMetrics().elidedText(sub, Qt.TextElideMode.ElideRight, int(text.width())))

    @staticmethod
    def _arrow(p: QPainter, a: QPointF, b: QPointF) -> None:
        p.drawLine(a, b)
        d = b - a
        length = max(1e-6, (d.x() ** 2 + d.y() ** 2) ** 0.5)
        u = QPointF(d.x() / length, d.y() / length)
        n = QPointF(-u.y(), u.x())
        p.drawLine(b, b - u * 7 + n * 5)
        p.drawLine(b, b - u * 7 - n * 5)
