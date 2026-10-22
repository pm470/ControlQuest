"""The main window: a stack of screens and the navigation between them.

Screens are created on first use (from screens/registry.py) and kept alive.
Esc goes back on every screen that has a back_target.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from .core.config import WINDOW_DEFAULT_SIZE, WINDOW_MIN_SIZE, WINDOW_TITLE
from .core.context import AppContext
from .core.navigation import ScreenId
from .screens.base_screen import BaseScreen
from .screens.registry import SCREENS
from .ui import painting


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(painting.app_icon())
        self._fit_to_screen()

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._screens: dict[ScreenId, BaseScreen] = {}
        self._current: BaseScreen | None = None

        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape)
        self.show_screen(ScreenId.TITLE)

    def _fit_to_screen(self) -> None:
        """Preferred size, but never larger than the screen (high display scaling
        leaves little room in logical pixels, e.g. 1920x1080 at 175% ~ 1100x600)."""
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRect(0, 0, 1280, 800)
        w = min(WINDOW_DEFAULT_SIZE[0], int(avail.width() * 0.94))
        h = min(WINDOW_DEFAULT_SIZE[1], int(avail.height() * 0.92))
        self.setMinimumSize(min(WINDOW_MIN_SIZE[0], w), min(WINDOW_MIN_SIZE[1], h))
        self.resize(w, h)
        self.move(avail.center().x() - w // 2, avail.center().y() - h // 2)

    @property
    def current_screen(self) -> BaseScreen | None:
        return self._current

    def screen(self, screen_id: ScreenId) -> BaseScreen:
        """The screen for an id, created on first use."""
        if screen_id not in self._screens:
            screen = SCREENS[screen_id](self.ctx)
            screen.navigate.connect(self._on_navigate)
            self._stack.addWidget(screen)
            self._screens[screen_id] = screen
        return self._screens[screen_id]

    def show_screen(self, screen_id: ScreenId, payload: Any = None) -> None:
        target = self.screen(screen_id)
        if self._current is not None and self._current is not target:
            self._current.on_leave()
        self._current = target
        self._stack.setCurrentWidget(target)
        target.on_enter(payload)

    def _on_navigate(self, screen_id: str, payload: Any) -> None:
        self.show_screen(ScreenId(screen_id), payload)

    def _on_escape(self) -> None:
        if self._current is not None:
            self._current.go_back()

    def closeEvent(self, event) -> None:
        if self._current is not None:
            self._current.on_leave()
        self.ctx.engine.stop_polling()
        super().closeEvent(event)
