"""Reusable QPainter drawings: the ball mascot, stars, blocks, locks, the dot grid.

Everything that draws the game's "characters" lives here, so the menu and the
future level map look the same. All functions take an active QPainter and leave
its state unchanged (save/restore).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from . import theme

_dot_tiles: dict[tuple, QPixmap] = {}


def draw_dot_grid(p: QPainter, rect: QRectF, dpr: float = 1.0, spacing: int = 28,
                  radius: float = 1.6, color: str = theme.DOT) -> None:
    """Fill rect with a soft dot grid (graph paper feel). Cached as one tile."""
    key = (spacing, radius, color, round(dpr, 2))
    tile = _dot_tiles.get(key)
    if tile is None:
        tile = QPixmap(round(spacing * dpr), round(spacing * dpr))
        tile.setDevicePixelRatio(dpr)
        tile.fill(Qt.GlobalColor.transparent)
        tp = QPainter(tile)
        tp.setRenderHint(QPainter.RenderHint.Antialiasing)
        tp.setPen(Qt.PenStyle.NoPen)
        tp.setBrush(QColor(color))
        tp.drawEllipse(QPointF(spacing / 2, spacing / 2), radius, radius)
        tp.end()
        _dot_tiles[key] = tile
    p.drawTiledPixmap(rect, tile)


def draw_ball(p: QPainter, center: QPointF, r: float, look: QPointF = QPointF(0, 0),
              blink: float = 0.0, shadow: bool = True) -> None:
    """The ball mascot. look = direction it looks in (any length), blink in [0, 1]."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    cx, cy = center.x(), center.y()

    if shadow:
        p.setBrush(QColor(43, 45, 66, 26))
        p.drawEllipse(QPointF(cx, cy + r * 1.02), r * 0.78, r * 0.2)

    grad = QRadialGradient(QPointF(cx - r * 0.35, cy - r * 0.45), r * 1.5)
    grad.setColorAt(0.0, QColor(theme.BALL).lighter(135))
    grad.setColorAt(0.55, QColor(theme.BALL))
    grad.setColorAt(1.0, QColor(theme.BALL_DARK))
    p.setBrush(QBrush(grad))
    p.drawEllipse(center, r, r)

    # shine
    p.setBrush(QColor(255, 255, 255, 170))
    p.drawEllipse(QPointF(cx - r * 0.45, cy - r * 0.48), r * 0.17, r * 0.11)

    # blush
    p.setBrush(QColor(255, 128, 170, 105))
    for sx in (-1, 1):
        p.drawEllipse(QPointF(cx + sx * r * 0.52, cy + r * 0.28), r * 0.14, r * 0.085)

    # eyes, pupils shifted towards `look`
    n = math.hypot(look.x(), look.y())
    lx, ly = (look.x() / n, look.y() / n) if n > 1e-9 else (0.0, 0.0)
    open_ = max(0.0, 1.0 - blink)
    for sx in (-1, 1):
        ex, ey = cx + sx * r * 0.3 + lx * r * 0.06, cy - r * 0.08 + ly * r * 0.05
        if open_ < 0.2:
            p.setPen(QPen(QColor(theme.INK), max(1.5, r * 0.06), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(ex - r * 0.11, ey), QPointF(ex + r * 0.11, ey))
            p.setPen(Qt.PenStyle.NoPen)
            continue
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(ex, ey), r * 0.16, r * 0.21 * open_)
        p.setBrush(QColor(theme.INK))
        p.drawEllipse(QPointF(ex + lx * r * 0.06, ey + ly * r * 0.07), r * 0.085, r * 0.11 * open_)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(ex + lx * r * 0.06 + r * 0.03, ey + ly * r * 0.07 - r * 0.04),
                      r * 0.03, r * 0.03 * open_)

    # smile
    p.setPen(QPen(QColor(theme.INK), max(1.5, r * 0.065), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(cx - r * 0.15, cy + r * 0.06, r * 0.3, r * 0.22), 200 * 16, 140 * 16)
    p.restore()


def star_polygon(center: QPointF, r: float, inner: float = 0.48, rotation_deg: float = 0.0) -> QPolygonF:
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36 + rotation_deg)
        rr = r if i % 2 == 0 else r * inner
        pts.append(QPointF(center.x() + rr * math.cos(a), center.y() + rr * math.sin(a)))
    return QPolygonF(pts)


def draw_star(p: QPainter, center: QPointF, r: float, filled: bool = True,
              rotation_deg: float = 0.0) -> None:
    """A rounded five-point star. filled=False draws an empty (not earned) star."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill, line = (theme.STAR, theme.STAR_DARK) if filled else (theme.SURFACE_ALT, theme.LINE)
    pen = QPen(QColor(line), max(1.5, r * 0.16))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QColor(fill))
    p.drawPolygon(star_polygon(center, r, rotation_deg=rotation_deg))
    p.restore()


def draw_block(p: QPainter, rect: QRectF) -> None:
    """An obstacle block (rounded, slightly 3D)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.BLOCK_DARK))
    p.drawRoundedRect(rect.translated(0, 4), 8, 8)
    p.setBrush(QColor(theme.BLOCK))
    p.drawRoundedRect(rect, 8, 8)
    p.restore()


def draw_dashed_ellipse(p: QPainter, rect: QRectF, color: str = theme.BLOCK_DARK) -> None:
    """The ellipse the solver sees around a block."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2, Qt.PenStyle.CustomDashLine, Qt.PenCapStyle.RoundCap)
    pen.setDashPattern([3, 3])
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(rect)
    p.restore()


def draw_block_polygon(p: QPainter, corners: list[QPointF], depth: float = 4.0) -> None:
    """An obstacle block given by its corners (screen points), same look as draw_block."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    poly = QPolygonF(corners)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.BLOCK_DARK))
    p.drawPolygon(poly.translated(0, depth))
    p.setBrush(QColor(theme.BLOCK))
    p.drawPolygon(poly)
    p.restore()


def draw_dashed_outline(p: QPainter, points: list[QPointF], color: str = theme.BLOCK_DARK,
                        width: float = 2.0) -> None:
    """A closed dashed outline, e.g. the ellipse the solver sees around a block."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), width, Qt.PenStyle.CustomDashLine, Qt.PenCapStyle.RoundCap)
    pen.setDashPattern([3, 3])
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolygon(QPolygonF(points))
    p.restore()


def draw_waypoint(p: QPainter, center: QPointF, r: float, number: int, active: bool = False,
                  done: bool = False) -> None:
    """A waypoint: a lilac diamond with its number. active = the MPC's current reference."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = theme.WAYPOINT if not done else theme.NEUTRAL
    if active:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.qcolor(fill, 70))
        p.drawEllipse(center, r * 1.7, r * 1.7)
    diamond = QPolygonF([center + QPointF(0, -r), center + QPointF(r, 0),
                         center + QPointF(0, r), center + QPointF(-r, 0)])
    p.setPen(QPen(QColor(theme.SURFACE), 2))
    p.setBrush(QColor(fill))
    p.drawPolygon(diamond)
    p.setPen(QColor(theme.SURFACE))
    p.setFont(theme.font(max(8, int(r * 0.95)), QFont.Weight.Black))
    p.drawText(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter,
               str(number))
    p.restore()


def draw_plan(p: QPainter, points: list[QPointF], color: str = theme.PRIMARY, width: float = 3.0,
              stage_dots: bool = True) -> None:
    """A predicted plan: dashed line with a dot per stage."""
    if len(points) < 2:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(points[0])
    for q in points[1:]:
        path.lineTo(q)
    pen = QPen(QColor(color), width, Qt.PenStyle.CustomDashLine, Qt.PenCapStyle.RoundCap)
    pen.setDashPattern([2, 2.2])
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    if stage_dots:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        for q in points[2::2]:
            p.drawEllipse(q, width * 0.9, width * 0.9)
    p.restore()


def draw_lock(p: QPainter, center: QPointF, size: float, color: str = theme.INK_SOFT,
              hole: str = theme.SURFACE) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy, s = center.x(), center.y(), size
    p.setPen(QPen(QColor(color), s * 0.13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(cx - s * 0.24, cy - s * 0.52, s * 0.48, s * 0.6), 0, 180 * 16)
    p.drawLine(QPointF(cx - s * 0.24, cy - s * 0.22), QPointF(cx - s * 0.24, cy - s * 0.08))
    p.drawLine(QPointF(cx + s * 0.24, cy - s * 0.22), QPointF(cx + s * 0.24, cy - s * 0.08))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(cx - s * 0.4, cy - s * 0.1, s * 0.8, s * 0.62), s * 0.14, s * 0.14)
    p.setBrush(QColor(hole))
    p.drawEllipse(QPointF(cx, cy + s * 0.16), s * 0.08, s * 0.08)
    p.restore()


def app_icon() -> QIcon:
    """Window icon: the ball mascot."""
    icon = QIcon()
    for size in (16, 32, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        draw_ball(p, QPointF(size / 2, size / 2), size * 0.44, shadow=False)
        p.end()
        icon.addPixmap(pm)
    return icon
