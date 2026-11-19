"""Reusable QPainter drawings: the ball mascot, stars, blocks, locks, the dot grid.

Everything that draws the game's "characters" lives here, so the menu and the
future level map look the same. All functions take an active QPainter and leave
its state unchanged (save/restore).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
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


BALL_EYES = "#1F2440"
BALL_BLUSH = "#FF8FA8"


def draw_ball(p: QPainter, center: QPointF, r: float, look: QPointF = QPointF(0, 0),
              blink: float = 0.0, shadow: bool = True) -> None:
    """The ball mascot (flat, like the 2026-11-14 design sketch): a flat blue disc with a
    soft highlight, two dark dot eyes with a shine, pink blush and a small smile.
    look = direction it looks in (any length; the eyes shift a little), blink in [0, 1]."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    cx, cy = center.x(), center.y()
    u = r / 13.0  # the sketch was drawn with r = 13 units

    if shadow:
        p.setBrush(QColor(43, 45, 66, 26))
        p.drawEllipse(QPointF(cx, cy + 16 * u), 10 * u, 2.6 * u)

    p.setBrush(QColor(theme.BALL))
    p.drawEllipse(center, r, r)

    # highlight (top left)
    p.setBrush(QColor(255, 255, 255, 153))
    p.drawEllipse(QPointF(cx - 4.5 * u, cy - 6.5 * u), 4 * u, 2.4 * u)

    # blush
    blush = QColor(BALL_BLUSH)
    blush.setAlpha(179)
    p.setBrush(blush)
    for sx in (-1, 1):
        p.drawEllipse(QPointF(cx + sx * 7.2 * u, cy + 3.2 * u), 2 * u, 1.2 * u)

    # eyes: dark dots with a shine, shifted a little towards `look`
    n = math.hypot(look.x(), look.y())
    lx, ly = (look.x() / n, look.y() / n) if n > 1e-9 else (0.0, 0.0)
    open_ = max(0.0, 1.0 - blink)
    for sx in (-1, 1):
        ex, ey = cx + sx * 4 * u + lx * 0.8 * u, cy - 0.5 * u + ly * 0.6 * u
        if open_ < 0.2:
            p.setPen(QPen(QColor(BALL_EYES), max(1.2, 1.3 * u), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(ex - 2 * u, ey), QPointF(ex + 2 * u, ey))
            p.setPen(Qt.PenStyle.NoPen)
            continue
        p.setBrush(QColor(BALL_EYES))
        p.drawEllipse(QPointF(ex, ey), 2.1 * u, 2.1 * u * open_)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(ex + 0.6 * u, ey - 0.7 * u * open_), 0.7 * u, 0.7 * u * open_)

    # smile
    p.setPen(QPen(QColor(BALL_EYES), max(1.0, 1.3 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    smile = QPainterPath(QPointF(cx - 2.6 * u, cy + 3.4 * u))
    smile.quadTo(QPointF(cx, cy + 5.8 * u), QPointF(cx + 2.6 * u, cy + 3.4 * u))
    p.drawPath(smile)
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
    fill, line = (theme.STAR, theme.STAR_DARK) if filled else (theme.LIP, theme.LIP)  # no outline
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


def draw_pill(p: QPainter, rect: QRectF, text: str, font_px: float = 13) -> None:
    """A small white HUD pill with a lip (e.g. '|v| = 2.00 m/s' on the map)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = rect.height() / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.LIP))
    p.drawRoundedRect(rect.translated(0, 3), r, r)
    p.setBrush(QColor(theme.SURFACE))
    p.drawRoundedRect(rect, r, r)
    p.setPen(QColor(theme.INK))
    p.setFont(theme.font(font_px, QFont.Weight.ExtraBold))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.restore()


def draw_level_icon(p: QPainter, kind: str, center: QPointF, size: float, color: str) -> None:
    """Small line icons for the level tiles: loop, bolt, wall, trap, wind."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(2.0, size * 0.09), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s, cx, cy = size / 24, center.x() - size / 2, center.y() - size / 2

    def pt(x: float, y: float) -> QPointF:
        return QPointF(cx + x * s, cy + y * s)

    if kind == "loop":  # the MPC loop: a circle with an arrow head (Level 0)
        p.drawArc(QRectF(pt(4, 4), pt(20, 20)), 100 * 16, 290 * 16)
        p.drawPolyline([pt(9, 2.5), pt(13, 4.2), pt(9.6, 7)])
        p.drawEllipse(pt(12, 12), 1.6 * s, 1.6 * s)
    elif kind == "bolt":
        p.drawPolygon(QPolygonF([pt(13, 2), pt(4, 14), pt(11, 14), pt(10, 22), pt(19, 10), pt(12, 10)]))
    elif kind == "wall":
        p.drawLine(pt(20, 3), pt(20, 21))
        p.drawLine(pt(3, 12), pt(14, 12))
        p.drawPolyline([pt(10, 8), pt(14, 12), pt(10, 16)])
    elif kind == "trap":
        p.drawPolyline([pt(6, 4), pt(18, 4), pt(18, 20), pt(6, 20)])
        p.drawEllipse(pt(9, 12), 2.5 * s, 2.5 * s)
    elif kind == "wind":
        path = QPainterPath(pt(3, 8))
        path.lineTo(pt(15, 8))
        path.quadTo(pt(20, 8), pt(18, 4))
        p.drawPath(path)
        path = QPainterPath(pt(3, 13))
        path.lineTo(pt(19, 13))
        path.quadTo(pt(23, 13), pt(21, 17))
        p.drawPath(path)
        p.drawLine(pt(3, 18), pt(11, 18))
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
