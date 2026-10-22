"""The clickable card for one level in the level select (custom painted)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from ..core.config import MAX_STARS
from ..levels.base import LevelInfo
from . import painting, theme

CARD_SIZE = QSize(212, 244)


class LevelCard(QAbstractButton):
    """Shows number, title, topic and stars; greyed out with a lock when locked.

    Locked cards stay clickable so the screen can explain how to unlock them.
    """

    def __init__(self, level: LevelInfo, parent: QWidget | None = None):
        super().__init__(parent)
        self.level = level
        self._stars = 0
        self._locked = False
        self._lock_text = ""
        self._hover = False
        self.setFixedSize(CARD_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Level {level.number}: {level.title}")

    def set_progress(self, stars: int, locked: bool, lock_text: str = "") -> None:
        self._stars, self._locked, self._lock_text = stars, locked, lock_text
        self.setToolTip(lock_text if locked else f"{self.level.topic}: {self.level.concept}")
        self.update()

    @property
    def locked(self) -> bool:
        return self._locked

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
        accent = QColor(theme.accent(self.level.accent))
        lifted = self._hover and not locked
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -14)
        if lifted:
            rect.translate(0, -4)

        # shadow + body
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(43, 45, 66, 38 if lifted else (12 if locked else 22)))
        p.drawRoundedRect(rect.translated(0, 7 if lifted else 5), theme.RADIUS_CARD, theme.RADIUS_CARD)
        border = accent if lifted else QColor(theme.BALL if self.hasFocus() else theme.LINE)
        p.setPen(QPen(border, 2.5))
        p.setBrush(QColor(theme.SURFACE_ALT if locked else theme.SURFACE))
        p.drawRoundedRect(rect, theme.RADIUS_CARD, theme.RADIUS_CARD)

        # number badge (a lock when locked)
        badge_c = QPointF(rect.left() + 42, rect.top() + 42)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.LOCKED) if locked else accent)
        p.drawEllipse(badge_c, 24, 24)
        if locked:
            painting.draw_lock(p, badge_c + QPointF(0, 2), 24, color=theme.SURFACE, hole=theme.LOCKED)
        else:
            p.setPen(QColor("white"))
            p.setFont(theme.font(22, QFont.Weight.ExtraBold))
            p.drawText(QRectF(badge_c.x() - 24, badge_c.y() - 24, 48, 48),
                       Qt.AlignmentFlag.AlignCenter, str(self.level.number))

        # title
        p.setPen(QColor(theme.MUTED if locked else theme.INK))
        p.setFont(theme.font(18, QFont.Weight.ExtraBold))
        left = rect.left() + 20
        title_rect = QRectF(left, rect.top() + 80, rect.width() - 40, 50)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                   | Qt.TextFlag.TextWordWrap, self.level.title)

        if locked:  # how to unlock instead of topic and stars
            p.setPen(QColor(theme.INK_SOFT))
            p.setFont(theme.font(13, QFont.Weight.Bold))
            p.drawText(QRectF(left, rect.top() + 136, rect.width() - 40, 40),
                       Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self._lock_text)
            return

        # topic tag
        tag_font = theme.font(12, QFont.Weight.Bold)
        p.setFont(tag_font)
        tw = QFontMetricsF(tag_font).horizontalAdvance(self.level.topic) + 22
        tag = QRectF(left, rect.top() + 136, min(tw, rect.width() - 40), 24)
        tag_bg = QColor(accent)
        tag_bg.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tag_bg)
        p.drawRoundedRect(tag, 12, 12)
        p.setPen(QColor(theme.INK_SOFT))
        p.drawText(tag, Qt.AlignmentFlag.AlignCenter, self.level.topic)

        # stars
        cy = rect.bottom() - 28
        for i in range(MAX_STARS):
            painting.draw_star(p, QPointF(rect.center().x() + (i - 1) * 32, cy), 11.5,
                               filled=i < self._stars)
