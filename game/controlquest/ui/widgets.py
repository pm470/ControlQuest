"""Small reusable widgets shared by all screens.

Add a widget here when a second screen needs it; keep screen-specific widgets
in the screen's own file.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import painting, theme


def label(text: str, role: str = "body", wrap: bool = False,
          align: Qt.AlignmentFlag | None = None) -> QLabel:
    """A QLabel styled by its text role (see theme.stylesheet)."""
    lab = QLabel(text)
    lab.setProperty("role", role)
    lab.setWordWrap(wrap)
    if align is not None:
        lab.setAlignment(align)
    return lab


class Button(QPushButton):
    """Push button: variant = default | primary | ghost | danger, scale = normal | large."""

    def __init__(self, text: str, variant: str = "default", scale: str = "normal",
                 parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        self.setProperty("scale", scale)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


def add_soft_shadow(widget: QWidget, blur: int = 28, dy: int = 6, alpha: int = 28) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(43, 45, 66, alpha))
    widget.setGraphicsEffect(effect)


class Card(QFrame):
    """White rounded card with a soft shadow. Use .body (a QVBoxLayout) to add content."""

    def __init__(self, parent: QWidget | None = None, padding: int = 28, spacing: int = 12,
                 shadow: bool = True):
        super().__init__(parent)
        self.setProperty("role", "card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        if shadow:
            add_soft_shadow(self)


def scrollable(content: QWidget) -> QScrollArea:
    """Wrap content in a frameless, transparent, vertical-only scroll area, so a
    screen stays usable on small windows (high display scaling)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(content)
    return area


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    return line


class ToggleSwitch(QAbstractButton):
    """Animated on/off switch (checkable)."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(54, 30)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self.setChecked(checked)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def set_checked_silently(self, checked: bool) -> None:
        """Set the state without emitting toggled (e.g. when syncing from GameState)."""
        if checked == self.isChecked():
            return
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._anim.stop()
        self._set_offset(1.0 if checked else 0.0)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(54, 30)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off, on = QColor(theme.LOCKED), QColor(theme.PRIMARY)
        t = self._offset
        track = QColor(round(off.red() + (on.red() - off.red()) * t),
                       round(off.green() + (on.green() - off.green()) * t),
                       round(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(QPen(QColor(theme.BALL), 2) if self.hasFocus() else Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 8
        x = r.left() + 4 + t * (r.width() - 8 - d)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(43, 45, 66, 40))
        p.drawEllipse(QRectF(x, r.top() + 5, d, d))
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))


class StarRow(QWidget):
    """Shows earned stars out of max_stars."""

    def __init__(self, stars: int = 0, max_stars: int = 3, star_radius: float = 11,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._stars, self._max, self._r = stars, max_stars, star_radius
        gap = star_radius * 2.7
        self.setFixedSize(round(gap * max_stars), round(star_radius * 2.6))

    def set_stars(self, stars: int) -> None:
        self._stars = stars
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        gap = self.width() / self._max
        for i in range(self._max):
            painting.draw_star(p, QPointF(gap * (i + 0.5), self.height() / 2), self._r,
                               filled=i < self._stars)


class StatusPill(QFrame):
    """Rounded pill with a coloured dot and a short text, e.g. the engine status."""

    COLORS = {"online": theme.SUCCESS, "warning": theme.WARNING, "outdated": theme.WARNING,
              "offline": theme.NEUTRAL,
              "checking": theme.STAR, "error": theme.DANGER}

    def __init__(self, text: str = "", state: str = "checking", parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "pill")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 5, 14, 5)
        row.setSpacing(8)
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._text = label(text, "caption")
        row.addWidget(self._dot)
        row.addWidget(self._text)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_state(state, text)

    def set_state(self, state: str, text: str) -> None:
        color = self.COLORS.get(state, theme.NEUTRAL)
        self._dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self._text.setText(text)


class ScreenHeader(QWidget):
    """Back button + heading (+ optional widget on the right). Emits back_clicked."""

    back_clicked = Signal()

    def __init__(self, title: str, right: QWidget | None = None, back_text: str = "←  Back",
                 parent: QWidget | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        back = Button(back_text, variant="ghost")
        back.setToolTip("Back (Esc)")
        back.clicked.connect(self.back_clicked)
        self.title_label = label(title, "heading")
        row.addWidget(back)
        row.addWidget(self.title_label)
        row.addStretch(1)
        if right is not None:
            row.addWidget(right)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)


class StepIcon(QWidget):
    """Little illustrations for the how-to-play steps: 'ball', 'knobs', 'plan', 'stars'."""

    def __init__(self, kind: str, size: int = 92, parent: QWidget | None = None):
        super().__init__(parent)
        self._kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.SURFACE_ALT))
        p.drawEllipse(QRectF(0, 0, s, s))
        c = QPointF(s / 2, s / 2)
        if self._kind == "ball":
            painting.draw_ball(p, QPointF(s / 2, s * 0.47), s * 0.26, look=QPointF(0.3, 0.4))
        elif self._kind == "knobs":
            for i, frac in enumerate((0.3, 0.7, 0.5)):
                y = s * (0.32 + 0.18 * i)
                x0, x1 = s * 0.24, s * 0.76
                p.setPen(QPen(QColor(theme.LINE), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(x0, y), QPointF(x1, y))
                xk = x0 + frac * (x1 - x0)
                p.setPen(QPen(QColor(theme.PRIMARY), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(x0, y), QPointF(xk, y))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.PRIMARY))
                p.drawEllipse(QPointF(xk, y), 6.5, 6.5)
        elif self._kind == "plan":
            pts = [QPointF(s * (0.3 + 0.5 * t), s * (0.66 - 0.36 * t + 0.25 * t * t))
                   for t in [i / 10 for i in range(11)]]
            painting.draw_plan(p, pts, width=3)
            painting.draw_star(p, pts[-1] + QPointF(4, -6), s * 0.1)
            painting.draw_ball(p, pts[0], s * 0.14, look=QPointF(1, -1), shadow=False)
        elif self._kind == "stars":
            for i, dx in enumerate((-0.22, 0.0, 0.22)):
                painting.draw_star(p, QPointF(c.x() + dx * s, c.y() + (0 if i == 1 else 0.06 * s)),
                                   s * (0.14 if i == 1 else 0.11), filled=i < 2)


class ColorDot(QWidget):
    """A small filled circle, e.g. for legends."""

    def __init__(self, color: str, size: int = 12, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
