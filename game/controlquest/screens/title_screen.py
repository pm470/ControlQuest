"""Title screen: logo, the animated mascot, and the main menu."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import __version__
from ..core.navigation import ScreenId
from ..engine.protocol import EngineStatus
from ..ui import theme
from ..ui.title_scene import TitleScene
from ..ui.widgets import Button, StatusPill, label
from .base_screen import BaseScreen

ENGINE_HELP = ("The MPC engine runs in Docker and computes the levels.\n"
               "Start it with engine_server/start_engine (see game/README.md).\n"
               "The menus work without it.")


class TitleScreen(BaseScreen):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 16)
        root.setSpacing(0)

        self.scene = TitleScene()
        root.addWidget(self.scene, 5)

        logo = label(f"Control<span style='color:{theme.PRIMARY};'>Quest</span>", "title",
                     align=Qt.AlignmentFlag.AlignCenter)
        logo.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(logo)
        root.addSpacing(4)
        root.addWidget(label("Design the controller. Let the ball find its way.", "subtitle",
                             align=Qt.AlignmentFlag.AlignCenter))
        root.addSpacing(20)

        menu = QVBoxLayout()
        menu.setSpacing(10)
        self.play_button = Button("Play", variant="primary", scale="large")
        self.play_button.setToolTip("Choose a level")
        how_button = Button("How to play")
        settings_button = Button("Settings")
        quit_button = Button("Quit", variant="ghost")
        for b in (self.play_button, how_button, settings_button, quit_button):
            b.setFixedWidth(300)
            menu.addWidget(b, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addLayout(menu)
        root.addStretch(1)

        footer = QHBoxLayout()
        self.engine_pill = StatusPill()
        self.engine_pill.setToolTip(ENGINE_HELP)
        footer.addWidget(self.engine_pill)
        footer.addStretch(1)
        footer.addWidget(label(f"v{__version__}  ·  an MPC course project", "caption"))
        root.addLayout(footer)

        self.play_button.clicked.connect(lambda: self.go(ScreenId.LEVEL_SELECT))
        how_button.clicked.connect(lambda: self.go(ScreenId.HOW_TO_PLAY))
        settings_button.clicked.connect(lambda: self.go(ScreenId.SETTINGS))
        quit_button.clicked.connect(lambda: self.window().close())

        ctx.engine.status_changed.connect(self._show_engine_status)
        self._show_engine_status(ctx.engine.status)

    def on_enter(self, payload: Any = None) -> None:
        self.scene.set_animated(self.ctx.state.animations)
        self.scene.start()

    def on_leave(self) -> None:
        self.scene.stop()

    def _show_engine_status(self, status: EngineStatus) -> None:
        self.engine_pill.set_state(status.state, status.message)
