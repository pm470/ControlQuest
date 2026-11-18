"""The clickable tile for one level in the level select (custom painted).

    ┌──────────────┐   top block in the level's accent colour: number + icon
    │ 2        ⟶|  │   (locked: muted, with a lock)
    ├──────────────┤
    │ Brake Check  │   title, topic
    │ Horizon & …  │
    │ ★ ★ ☆  / Play│   stars, a Play pill on the next level to play, or a
                       "Tutorial" tag (Level 0, no stars)
    └──────────────┘   stands on a lip like every tile; the next level is lifted
                       and ringed in its colour (no mascot on this screen).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from ..core.config import MAX_STARS
from ..levels.base import LevelInfo
from . import painting, theme
from .widgets import is_keyboard_focus

TILE_W, TILE_H, BLOCK_H = 200, 290, 132
PAD_X, PAD_TOP, PAD_BOTTOM = 10, 20, 12  # room for the ring, the lift and the lip
CARD_SIZE = QSize(TILE_W + 2 * PAD_X, TILE_H + PAD_TOP + PAD_BOTTOM)
RADIUS = theme.RADIUS_CARD


class LevelCard(QAbstractButton):
    """Shows number, icon, title, topic and stars; muted with a lock when locked.

    Locked tiles stay clickable so the screen can explain how to unlock them.
    """

    def __init__(self, level: LevelInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.level = level
        self._stars = 0
        self._locked = False
        self._next = False
        self._lock_text = ""
        self._hover = False
        self._keyboard_focus = False  # focus ring only when focused with Tab
        self.setFixedSize(CARD_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Level {level.number}: {level.title}")

    def set_progress(self, stars: int, locked: bool, lock_text: str = "", is_next: bool = False) -> None:
        self._stars, self._locked, self._lock_text = stars, locked, lock_text
        self._next = is_next and not locked
        # rich text, so Qt wraps the (several sentences long) concept
        self.setToolTip(lock_text if locked else
                        f"<p><b>{self.level.topic}</b>: {self.level.concept}</p>")
        self.update()

    @property
    def locked(self) -> bool:
        return self._locked

    def focusInEvent(self, event) -> None:
        self._keyboard_focus = is_keyboard_focus(event)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self._keyboard_focus = False
        super().focusOutEvent(event)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        locked = self._locked
        accent = theme.accent(self.level.accent)
        rect = QRectF(PAD_X, PAD_TOP, TILE_W, TILE_H)
        lift = (8 if self._next else 0) + (3 if self._hover and not locked else 0)
        rect.translate(0, -lift + 8)  # resting tiles sit a little lower than the lifted one

        # ring around the next level, lip, body
        if self._next:
            ring = QColor(accent)
            ring.setAlpha(110)
            p.setPen(QPen(ring, 4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(-6, -6, 6, 6 + 7), RADIUS + 6, RADIUS + 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.LIP))
        p.drawRoundedRect(rect.translated(0, 7), RADIUS, RADIUS)
        body = QPainterPath()
        body.addRoundedRect(rect, RADIUS, RADIUS)
        p.save()
        p.setClipPath(body)
        p.fillRect(rect, QColor(theme.SURFACE_ALT if locked else theme.SURFACE))
        block = QRectF(rect.left(), rect.top(), rect.width(), BLOCK_H)
        p.fillRect(block, QColor(theme.LOCKED if locked else accent))
        p.restore()
        if self.hasFocus() and self._keyboard_focus:
            p.setPen(QPen(QColor(theme.FOCUS), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), RADIUS - 1, RADIUS - 1)

        # number + icon (lock when locked)
        p.setPen(QColor(theme.SURFACE_ALT if locked else "white"))
        p.setFont(theme.font(60, QFont.Weight.Black))
        p.drawText(QRectF(block.left() + 22, block.top(), 90, block.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(self.level.number))
        icon_c = QPointF(block.right() - 44, block.center().y())
        if locked:
            painting.draw_lock(p, icon_c + QPointF(0, 3), 34, color=theme.SURFACE_ALT, hole=theme.LOCKED)
        elif self.level.icon:
            painting.draw_level_icon(p, self.level.icon, icon_c, 44, "white")

        # title, topic (or how to unlock)
        left, width = rect.left() + 18, rect.width() - 36
        p.setPen(QColor(theme.MUTED if locked else theme.INK))
        p.setFont(theme.font(18, QFont.Weight.ExtraBold))
        title_rect = QRectF(left, block.bottom() + 14, width, 48)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                   | Qt.TextFlag.TextWordWrap, self.level.title)
        title_h = p.fontMetrics().boundingRect(title_rect.toRect(), Qt.TextFlag.TextWordWrap,
                                               self.level.title).height()
        p.setFont(theme.font(13, QFont.Weight.Bold))
        p.setPen(QColor(theme.MUTED if locked else theme.INK_SOFT))
        p.drawText(QRectF(left, block.bottom() + 16 + title_h, width, 40),
                   Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                   self._lock_text if locked else self.level.topic)
        if locked:
            return

        # bottom: a Play pill on the next level, stars otherwise
        bottom = rect.bottom() - 22
        if self.level.tutorial:  # no stars: a tag instead
            p.setFont(theme.font(12, QFont.Weight.Bold))
            text = "Tutorial"
            tag = QRectF(left, bottom - 13, p.fontMetrics().horizontalAdvance(text) + 22, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.SURFACE_ALT))
            p.drawRoundedRect(tag, 13, 13)
            p.setPen(QColor(theme.INK_SOFT))
            p.drawText(tag, Qt.AlignmentFlag.AlignCenter, text)
        elif self._next and self._stars == 0:
            pill = QRectF(left, bottom - 17, 78, 34)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.PRIMARY_PRESSED))
            p.drawRoundedRect(pill.translated(0, 3), 12, 12)
            p.setBrush(QColor(theme.PRIMARY))
            p.drawRoundedRect(pill, 12, 12)
            p.setPen(QColor("white"))
            p.setFont(theme.font(15, QFont.Weight.Black))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, "Play")
        else:
            for i in range(MAX_STARS):
                painting.draw_star(p, QPointF(left + 12 + i * 30, bottom), 11.5, filled=i < self._stars)
