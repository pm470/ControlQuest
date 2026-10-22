"""Settings: animations, the MPC engine address (with a connection test), reset progress."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout, QWidget

from ..core.navigation import ScreenId
from ..engine.protocol import EngineStatus
from ..ui.widgets import (Button, Card, ScreenHeader, StatusPill, ToggleSwitch, divider, label,
                          scrollable)
from .base_screen import BaseScreen


class SettingsScreen(BaseScreen):
    back_target = ScreenId.TITLE

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 22, 40, 16)
        root.setSpacing(14)
        header = ScreenHeader("Settings")
        header.back_clicked.connect(self.go_back)
        root.addWidget(header)

        card = Card(padding=28, spacing=14)
        card.setMaximumWidth(760)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 1)

        # animations
        grid.addWidget(label("Animations", "subheading"), 0, 0)
        grid.addWidget(label("The moving ball on the title screen.", "body"), 1, 0)
        self.animations = ToggleSwitch(ctx.state.animations)
        grid.addWidget(self.animations, 0, 1, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        card.body.addLayout(grid)
        card.body.addWidget(divider())

        # engine
        card.body.addWidget(label("MPC engine", "subheading"))
        card.body.addWidget(label("The engine runs acados in Docker and computes every level "
                                  "run. Start it with engine_server/start_engine "
                                  "(see game/README.md).", "body", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.url = QLineEdit(ctx.state.engine_url)
        self.url.setPlaceholderText("http://127.0.0.1:8000")
        test = Button("Test connection")
        self.pill = StatusPill()
        row.addWidget(self.url, 1)
        row.addWidget(test)
        card.body.addLayout(row)
        card.body.addWidget(self.pill, alignment=Qt.AlignmentFlag.AlignLeft)
        card.body.addWidget(divider())

        # progress
        prog = QHBoxLayout()
        text = QVBoxLayout()
        text.addWidget(label("Progress", "subheading"))
        text.addWidget(label("Forget all stars and lock the levels again.", "body"))
        prog.addLayout(text, 1)
        reset = Button("Reset progress", variant="danger")
        prog.addWidget(reset, alignment=Qt.AlignmentFlag.AlignVCenter)
        card.body.addLayout(prog)

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(4, 4, 4, 8)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(card, 20)
        centered.addStretch(1)
        col.addLayout(centered)
        col.addStretch(1)
        root.addWidget(scrollable(content), 1)

        self.animations.toggled.connect(ctx.state.set_animations)
        self.url.editingFinished.connect(self._apply_url)
        test.clicked.connect(self._test_connection)
        reset.clicked.connect(self._reset_progress)
        ctx.engine.status_changed.connect(self._show_status)
        self._show_status(ctx.engine.status)

    def on_enter(self, payload: Any = None) -> None:
        self.animations.set_checked_silently(self.ctx.state.animations)
        self.url.setText(self.ctx.state.engine_url)

    def _apply_url(self) -> None:
        self.ctx.state.set_engine_url(self.url.text())
        self.url.setText(self.ctx.state.engine_url)

    def _test_connection(self) -> None:
        self.pill.set_state("checking", "Checking...")
        self._apply_url()
        self.ctx.engine.check_health(announce=True)

    def _show_status(self, status: EngineStatus) -> None:
        self.pill.set_state(status.state, status.message)
        self.pill.setToolTip(str(status.details.get("error", "")) or status.message)

    def _reset_progress(self) -> None:
        answer = QMessageBox.question(self, "Reset progress",
                                      "Forget all stars and lock the levels again?")
        if answer == QMessageBox.StandardButton.Yes:
            self.ctx.state.reset_progress()
