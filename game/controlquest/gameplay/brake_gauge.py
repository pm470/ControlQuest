"""Level 2's "brake check" display (PRD 7, Level 2 "extra plot"), shown under the map:
three bars on one metre scale, for the current replay time:

    Wall ahead        distance to the wall in the direction of motion
    Braking needs     v^2 / (2 a_max): the room needed to stop from the current speed
    Plan looks ahead  N * dt * v: how far the horizon reaches at the current speed

As long as "braking needs" is shorter than "wall ahead" the ball can still stop; the
moment it is longer, it is too late (the point of no return).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui import theme

ROWS = (("Wall ahead", "wall"), ("Braking needs", "brake"), ("Plan looks ahead", "reach"))


class BrakeGauge(QWidget):
    def __init__(self, scale_m: float = 20.0, parent: QWidget | None = None):
        super().__init__(parent)
        self._scale = scale_m  # metres at the right end of the bars
        self._v = {"wall": None, "brake": None, "reach": None}
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, wall: float | None, brake: float | None, reach: float | None) -> None:
        self._v = {"wall": wall, "brake": brake, "reach": reach}
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        wall, brake = self._v["wall"], self._v["brake"]
        known = wall is not None and brake is not None
        too_late = known and brake > wall + 1e-6

        p.setPen(QColor(theme.INK))
        p.setFont(theme.font(15, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Brake check")
        p.setFont(theme.font(13, QFont.Weight.Bold))
        if known:
            p.setPen(QColor(theme.DANGER if too_late else theme.SUCCESS))
            verdict = "Too late to stop before the wall" if too_late else "Can still stop in time"
        else:
            p.setPen(QColor(theme.MUTED))
            verdict = "Press Run"
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, verdict)

        name_w, value_w = 118, 58
        x0, x1 = name_w, w - value_w
        colors = {"wall": theme.BALL, "brake": theme.DANGER if too_late else theme.WARNING,
                  "reach": theme.PRIMARY}
        for i, (name, key) in enumerate(ROWS):
            y = 26 + i * 20
            p.setPen(QColor(theme.INK_SOFT))
            p.setFont(theme.font(12, QFont.Weight.DemiBold))
            p.drawText(QRectF(0, y, name_w - 8, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            track = QRectF(x0, y + 4, x1 - x0, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.SURFACE_ALT))
            p.drawRoundedRect(track, 4, 4)
            value = self._v[key]
            if value is None:
                continue
            shown = min(value, self._scale) if math.isfinite(value) else self._scale
            if shown > 0:
                p.setBrush(QColor(colors[key]))
                p.drawRoundedRect(QRectF(x0, y + 4, track.width() * shown / self._scale, 8), 4, 4)
            p.setPen(QColor(theme.INK))
            p.setFont(theme.font(12, QFont.Weight.Bold))
            text = f"{value:.1f} m" if math.isfinite(value) else "–"
            if math.isfinite(value) and value > self._scale:
                text = f">{self._scale:g} m"
            p.drawText(QRectF(x1 + 6, y, value_w - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
