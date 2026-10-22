"""Animated scene on the title screen: the ball follows its (dashed) MPC plan
over a block to the star, celebrates, and starts again.

It is purely decorative, so it is cheap: a 30 fps timer that only runs while the
title screen is visible and animations are enabled.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.config import ANIMATION_FRAME_MS
from . import painting, theme

TRAVEL_S = 3.4  # time from start to star
CELEBRATE_S = 1.4  # time resting at the star
CYCLE_S = TRAVEL_S + CELEBRATE_S
HORIZON = 0.24  # how far ahead the drawn plan reaches (fraction of the path)


def _ease_in_out(u: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


class TitleScene(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._timer = QTimer(self)
        self._timer.setInterval(ANIMATION_FRAME_MS)
        self._timer.timeout.connect(self.update)
        self._clock = QElapsedTimer()
        self._animated = True

    # --- control -------------------------------------------------------------
    def set_animated(self, animated: bool) -> None:
        self._animated = animated
        if not animated:
            self._timer.stop()
        self.update()

    def start(self) -> None:
        if self._animated:
            self._clock.restart()
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # --- geometry ------------------------------------------------------------
    def _layout(self):
        w, h = self.width(), self.height()
        sw = min(w - 40, 820.0)
        x0 = (w - sw) / 2
        r = max(16.0, min(30.0, h * 0.11))
        base = h * 0.72
        start = QPointF(x0 + 70, base)
        target = QPointF(x0 + sw - 70, base)
        top = base - h * 0.78
        path = QPainterPath(start)
        path.cubicTo(QPointF(x0 + sw * 0.33, top), QPointF(x0 + sw * 0.67, top), target)
        bw, bh = sw * 0.13, h * 0.24
        block = QRectF(w / 2 - bw / 2, base - bh * 0.85, bw, bh)
        return path, start, target, block, r

    # --- painting ------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path, start, target, block, r = self._layout()

        t = self._clock.elapsed() / 1000.0 if (self._animated and self._clock.isValid()) else 0.0
        phase = t % CYCLE_S
        s = _ease_in_out(phase / TRAVEL_S) if self._animated else 0.0
        arrived = self._animated and phase >= TRAVEL_S

        # obstacle and the ellipse the solver avoids
        painting.draw_dashed_ellipse(p, block.adjusted(-block.width() * 0.32, -block.height() * 0.3,
                                                       block.width() * 0.32, block.height() * 0.3))
        painting.draw_block(p, block)

        # start ring
        p.setPen(QPen(QColor(theme.BALL), 3, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(start, r * 0.75, r * 0.75)

        # trail behind the ball
        if s > 0.005:
            trail = QPainterPath(path.pointAtPercent(0.0))
            for i in range(1, 41):
                trail.lineTo(path.pointAtPercent(s * i / 40))
            p.setPen(QPen(theme.qcolor(theme.BALL, 70), r * 0.5, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawPath(trail)

        # the plan ahead of the ball (receding horizon)
        if not arrived:
            end = min(1.0, s + (HORIZON if self._animated else 1.0))
            n = 14 if self._animated else 40
            pts = [path.pointAtPercent(s + (end - s) * i / n) for i in range(n + 1)]
            painting.draw_plan(p, pts, width=3.2)

        # target star (pulses; sparkles when reached)
        pulse = 1.0 + 0.07 * math.sin(2 * math.pi * 1.1 * t)
        if arrived:
            k = (phase - TRAVEL_S) / CELEBRATE_S
            self._draw_sparkles(p, target, r * (1.2 + 2.0 * k), 1.0 - k)
            pulse += 0.25 * math.sin(math.pi * min(1.0, k * 2.5))
        painting.draw_star(p, target + QPointF(0, -r * 0.2), r * 0.95 * pulse,
                           rotation_deg=8 * math.sin(2 * math.pi * 0.5 * t))

        # the ball (looks where it goes, blinks now and then, hops when it arrives)
        pos = path.pointAtPercent(min(s, 1.0))
        ang = math.radians(path.angleAtPercent(min(max(s, 0.001), 0.999)))
        look = QPointF(math.cos(ang), -math.sin(ang))
        if arrived:
            k = (phase - TRAVEL_S) / CELEBRATE_S
            pos = pos + QPointF(0, -abs(math.sin(math.pi * 2 * k)) * r * 0.8 * (1 - k))
            look = QPointF(0.2, 0.6)
        blink_phase = t % 3.7
        blink = 1.0 - abs(blink_phase - 3.55) / 0.15 if blink_phase > 3.4 else 0.0
        painting.draw_ball(p, pos + QPointF(0, -r * 0.6), r, look=look, blink=max(0.0, blink))

    @staticmethod
    def _draw_sparkles(p: QPainter, c: QPointF, radius: float, alpha: float) -> None:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(8):
            a = 2 * math.pi * i / 8
            col = QColor(theme.STAR if i % 2 == 0 else theme.PRIMARY)
            col.setAlphaF(max(0.0, min(1.0, alpha)))
            p.setBrush(col)
            p.drawEllipse(QPointF(c.x() + radius * math.cos(a), c.y() - radius * 0.2 + radius * math.sin(a)),
                          3.5, 3.5)
        p.restore()
