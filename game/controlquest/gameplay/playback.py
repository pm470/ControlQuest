"""Replay of a computed run (PRD 9.1: compute first, then replay).

Playback is the clock: it emits time_changed(t) about 60 times per second while
playing; widgets (map, battery, ...) draw the run at that time.
PlaybackBar is the control strip: play/pause, scrubber, time, speed.
"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSlider, QWidget

from ..ui import theme
from ..ui.widgets import Button, label

SPEEDS = [1.0, 2.0, 4.0, 8.0]
DEFAULT_SPEED = 2.0


class Playback(QObject):
    time_changed = Signal(float)
    playing_changed = Signal(bool)
    finished = Signal()  # reached the end (by playing or by seeking there)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.duration = 0.0
        self.speed = DEFAULT_SPEED
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._end_reported = False

    @property
    def time(self) -> float:
        return self._t

    @property
    def playing(self) -> bool:
        return self._timer.isActive()

    def load(self, duration: float) -> None:
        self.pause()
        self.duration = max(0.0, duration)
        self._end_reported = False
        self.seek(0.0)

    def play(self) -> None:
        if self.duration <= 0:
            return
        if self._t >= self.duration:
            self.seek(0.0)
        self._clock.restart()
        self._timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.playing_changed.emit(False)

    def replay(self) -> None:
        """From the start again; finished is emitted again at the end."""
        self._end_reported = False
        self.seek(0.0)
        self.play()

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def seek(self, t: float) -> None:
        self._t = min(max(t, 0.0), self.duration)
        self.time_changed.emit(self._t)
        if self._t >= self.duration and self.duration > 0:
            self.pause()
            if not self._end_reported:
                self._end_reported = True
                self.finished.emit()

    def _tick(self) -> None:
        dt = self._clock.restart() / 1000.0
        self.seek(self._t + dt * self.speed)


class PlayButton(QAbstractButton):
    """Coral square button with a painted play / pause icon (fonts lack a pause glyph)."""

    SIZE = 38

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._playing = False
        self.setFixedSize(self.SIZE, self.SIZE + 3)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self.setAccessibleName("Pause" if playing else "Play")
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SIZE
        on = self.isEnabled()
        down = 2 if self.isDown() else 0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.PRIMARY_PRESSED if on else theme.BLOCK))
        p.drawRoundedRect(QRectF(0, 3, s, s), 13, 13)
        p.setBrush(QColor(theme.PRIMARY if on else theme.LOCKED))
        body = QRectF(0, down, s, s)
        p.drawRoundedRect(body, 13, 13)
        p.setBrush(QColor("white"))
        c = body.center()
        if self._playing:
            for dx in (-4.5, 1.5):
                p.drawRoundedRect(QRectF(c.x() + dx, c.y() - 6.5, 3.5, 13), 1.5, 1.5)
        else:
            p.drawPolygon(QPolygonF([QPointF(c.x() - 4.5, c.y() - 7), QPointF(c.x() + 7, c.y()),
                                     QPointF(c.x() - 4.5, c.y() + 7)]))


class PlaybackBar(QWidget):
    """Play/pause, scrubber, time and speed. Sits in the replay well under the map,
    next to the MPC solve stepper."""

    def __init__(self, playback: Playback, parent: QWidget | None = None):
        super().__init__(parent)
        self.pb = playback
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.play_button = PlayButton()
        self.play_button.setToolTip("Play / pause the replay")
        self.play_button.set_playing(False)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setProperty("role", "scrubber")
        self.slider.setRange(0, 0)
        self.slider.setMinimumWidth(60)
        self.slider.setToolTip("Drag to any moment of the run")
        self.time_label = label("0.0 / 0.0 s", "caption")
        self.time_label.setStyleSheet(f"font-weight: 800; color: {theme.INK_SOFT};")
        self.speed = Button(f"{DEFAULT_SPEED:g}×", variant="chip")
        self.speed.setToolTip("Replay speed (click to change)")
        row.addWidget(self.play_button)
        row.addWidget(self.slider, 1)
        row.addWidget(self.time_label)
        row.addWidget(self.speed)

        self.play_button.clicked.connect(self.pb.toggle)
        self.slider.sliderMoved.connect(lambda v: self.pb.seek(v / 100.0))
        self.slider.sliderPressed.connect(self.pb.pause)
        self.speed.clicked.connect(self._next_speed)
        self.pb.time_changed.connect(self._show_time)
        self.pb.playing_changed.connect(self.play_button.set_playing)
        self.set_enabled_for_run(False)

    def _next_speed(self) -> None:
        i = (SPEEDS.index(self.pb.speed) + 1) % len(SPEEDS) if self.pb.speed in SPEEDS else 0
        self.pb.speed = SPEEDS[i]
        self.speed.setText(f"{SPEEDS[i]:g}×")

    def set_enabled_for_run(self, has_run: bool) -> None:
        for w in (self.play_button, self.slider, self.speed):
            w.setEnabled(has_run)
        self.slider.setRange(0, round(self.pb.duration * 100))
        self._show_time(self.pb.time)

    def _show_time(self, t: float) -> None:
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(round(t * 100))
            self.slider.blockSignals(False)
        self.time_label.setText(f"{t:.1f} / {self.pb.duration:.1f} s")
