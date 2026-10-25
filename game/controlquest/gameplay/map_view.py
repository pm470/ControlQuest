"""The playing field: the world in metres, drawn with the same scale in x and y
and y pointing up (PRD 9.2). Shows start, target, the ball, its trail, the
current MPC plan (dashed, one dot per stage) and the applied acceleration.

    view.set_level(data)            # world size, start, target
    view.set_trajectory(traj)       # a RunResult.trajectory (or None to clear)
    view.set_time(t)                # replay position in seconds (interpolated)
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..engine.protocol import Trajectory
from ..ui import painting, theme
from .level_data import LevelData

MARGIN_PX = 34  # room for axis labels
BALL_RADIUS_M = 0.9


class MapView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(320, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._data: LevelData | None = None
        self._traj: Trajectory | None = None
        self._t = 0.0
        self.show_plan = True

    # --- data -------------------------------------------------------------------------
    def set_level(self, data: LevelData) -> None:
        self._data = data
        self.update()

    def set_trajectory(self, traj: Trajectory | None) -> None:
        self._traj = traj
        self._t = 0.0
        self.update()

    def set_time(self, t: float) -> None:
        self._t = t
        self.update()

    # --- world <-> screen ----------------------------------------------------------------
    def _transform(self):
        (x0, y0), (x1, y1) = self._data.workspace
        w = self.width() - 2 * MARGIN_PX
        h = self.height() - 2 * MARGIN_PX
        s = max(1e-6, min(w / (x1 - x0), h / (y1 - y0)))  # px per metre, same in x and y
        ox = (self.width() - s * (x1 - x0)) / 2
        oy = (self.height() + s * (y1 - y0)) / 2

        def to_px(px: float, py: float) -> QPointF:
            return QPointF(ox + s * (px - x0), oy - s * (py - y0))

        return to_px, s

    def _state_at(self, t: float):
        """Interpolated state at time t, the index of the current sample, and progress."""
        tr = self._traj
        k, a = tr.index_at(t)
        xa, xb = tr.x[k], tr.x[min(k + 1, len(tr.x) - 1)]
        x = [xa[i] + a * (xb[i] - xa[i]) for i in range(4)]
        return x, k

    # --- painting -----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        if self._data is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        to_px, s = self._transform()
        (x0, y0), (x1, y1) = self._data.workspace

        # field
        field = QRectF(to_px(x0, y1), to_px(x1, y0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(43, 45, 66, 18))
        p.drawRoundedRect(field.translated(0, 5), 14, 14)
        p.setBrush(QColor(theme.SURFACE))
        p.setPen(QPen(QColor(theme.LINE), 2))
        p.drawRoundedRect(field, 14, 14)

        # grid every 5 m, labels every 10 m
        p.setFont(theme.font(11, QFont.Weight.DemiBold))
        for gx in range(int(math.ceil(x0)), int(x1) + 1, 5):
            p.setPen(QPen(QColor(theme.SURFACE_ALT), 1.5))
            p.drawLine(to_px(gx, y0), to_px(gx, y1))
            if gx % 10 == 0:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRectF(to_px(gx, y0).x() - 20, field.bottom() + 4, 40, 18),
                           Qt.AlignmentFlag.AlignHCenter, f"{gx}")
        for gy in range(int(math.ceil(y0)), int(y1) + 1, 5):
            p.setPen(QPen(QColor(theme.SURFACE_ALT), 1.5))
            p.drawLine(to_px(x0, gy), to_px(x1, gy))
            if gy % 10 == 0:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRectF(field.left() - 32, to_px(x0, gy).y() - 9, 26, 18),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{gy}")

        r_px = max(9.0, min(18.0, s * BALL_RADIUS_M))
        start, target = to_px(*self._data.start), to_px(*self._data.target)

        # start ring and target star
        p.setPen(QPen(QColor(theme.BALL), 2.5, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(start, r_px * 0.9, r_px * 0.9)
        painting.draw_star(p, target, r_px * 1.2)

        if self._traj is None or not self._traj.x:
            painting.draw_ball(p, start, r_px, look=QPointF(1, 0))
            return

        tr = self._traj
        x, k = self._state_at(self._t)
        ball = to_px(x[0], x[1])

        # trail
        trail = QPainterPath(to_px(*tr.x[0][:2]))
        for xi in tr.x[1:k + 1]:
            trail.lineTo(to_px(xi[0], xi[1]))
        trail.lineTo(ball)
        p.setPen(QPen(theme.qcolor(theme.BALL, 70), r_px * 0.7, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(trail)

        # current plan (receding horizon): the plan computed at the current sample
        if self.show_plan and tr.plans:
            plan = tr.plans[min(k, len(tr.plans) - 1)]
            at_end = k >= len(tr.x) - 1 and len(tr.plans) < len(tr.x)
            if not at_end:
                painting.draw_plan(p, [to_px(q[0], q[1]) for q in plan], width=max(2.0, r_px * 0.22))

        # applied acceleration (arrow length ~ |a|)
        if k < len(tr.u):
            ax, ay = tr.u[k]
            mag = math.hypot(ax, ay)
            if mag > 1e-3:
                L = r_px * (0.9 + 1.4 * mag / max(self._data.a_max, 1e-6))
                d = QPointF(ax / mag, -ay / mag)
                a0, a1 = ball + d * (r_px * 1.15), ball + d * (r_px * 1.15 + L)
                pen = QPen(QColor(theme.BALL_DARK), max(2.0, r_px * 0.2), Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(a0, a1)
                n = QPointF(-d.y(), d.x())
                p.drawLine(a1, a1 - d * (r_px * 0.45) + n * (r_px * 0.3))
                p.drawLine(a1, a1 - d * (r_px * 0.45) - n * (r_px * 0.3))

        speed = math.hypot(x[2], x[3])
        look = QPointF(x[2], -x[3]) if speed > 0.05 else QPointF(0.4, 0.2)
        painting.draw_ball(p, ball, r_px, look=look)

        # HUD
        p.setPen(QColor(theme.INK_SOFT))
        p.setFont(theme.font(13, QFont.Weight.Bold))
        p.drawText(QRectF(field.left() + 12, field.top() + 8, 260, 20), Qt.AlignmentFlag.AlignLeft,
                   f"t = {min(self._t, tr.duration):5.1f} s    |v| = {speed:4.2f} m/s")
