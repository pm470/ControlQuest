"""Creates the Qt application, the shared services and the main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import APP_NAME
from .core.config import DEFAULT_ENGINE_URL
from .core.context import AppContext
from .core.game_state import GameState
from .engine.client import EngineClient
from .levels import discover_levels
from .main_window import MainWindow
from .ui import theme


def create_app(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    """Build everything without entering the event loop (also used by tests)."""
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(theme.app_font())
    app.setStyleSheet(theme.stylesheet())

    state = GameState(DEFAULT_ENGINE_URL)
    engine = EngineClient(state.engine_url)
    state.engine_url_changed.connect(engine.set_base_url)
    ctx = AppContext(state=state, engine=engine, levels=discover_levels())

    window = MainWindow(ctx)
    engine.start_polling()
    return app, window


def run(argv: list[str] | None = None) -> int:
    app, window = create_app(argv)
    window.show()
    return app.exec()
