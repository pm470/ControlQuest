"""Replay of a computed run (PRD 9.1: compute first, then replay).

Playback is the clock: it emits time_changed(t) about 60 times per second while
playing; widgets (map, battery, ...) draw the run at that time.
PlaybackBar is the control strip: play/pause, scrubber, time, speed.
"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSlider, QWidget

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


class PlaybackBar(QWidget):
    def __init__(self, playback: Playback, parent: QWidget | None = None):
        super().__init__(parent)
        self.pb = playback
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.play_button = Button("Play", variant="default")
        self.play_button.setFixedWidth(96)
        self.play_button.setToolTip("Play / pause the replay")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.time_label = label("0.0 / 0.0 s", "body")
        self.time_label.setMinimumWidth(110)
        self.speed = QComboBox()
        for s in SPEEDS:
            self.speed.addItem(f"{s:g}×", s)
        self.speed.setCurrentIndex(SPEEDS.index(DEFAULT_SPEED))
        self.speed.setToolTip("Replay speed")
        self.speed.setFixedWidth(84)
        row.addWidget(self.play_button)
        row.addWidget(self.slider, 1)
        row.addWidget(self.time_label)
        row.addWidget(self.speed)

        self.play_button.clicked.connect(self.pb.toggle)
        self.slider.sliderMoved.connect(lambda v: self.pb.seek(v / 100.0))
        self.slider.sliderPressed.connect(self.pb.pause)
        self.speed.currentIndexChanged.connect(lambda i: setattr(self.pb, "speed", SPEEDS[i]))
        self.pb.time_changed.connect(self._show_time)
        self.pb.playing_changed.connect(lambda on: self.play_button.setText("Pause" if on else "Play"))
        self.set_enabled_for_run(False)

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
