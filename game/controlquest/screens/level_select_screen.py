"""Level select: one card per level, stars earned, locks, and the free-mode switch."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..core.config import MAX_STARS
from ..core.navigation import ScreenId
from ..ui.level_card import CARD_SIZE, LevelCard
from ..ui.widgets import ScreenHeader, StarRow, ToggleSwitch, label, scrollable
from .base_screen import BaseScreen

CARD_SPACING = 14


class LevelSelectScreen(BaseScreen):
    back_target = ScreenId.TITLE

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 18, 32, 18)
        root.setSpacing(6)

        # header: back, title; right: free-mode switch (PRD 5.1) and the total stars
        right = QWidget()
        right_row = QHBoxLayout(right)
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(10)
        free_label = label("Free mode", "body")
        free_label.setStyleSheet("font-weight: 800;")
        free_label.setToolTip("Unlock all levels (for demos and presentations)")
        self.free_switch = ToggleSwitch(ctx.state.free_mode)
        self.free_switch.setToolTip(free_label.toolTip())
        right_row.addWidget(free_label)
        right_row.addWidget(self.free_switch)
        right_row.addSpacing(10)
        total = QFrame()
        total.setProperty("role", "pill")
        total_row = QHBoxLayout(total)
        total_row.setContentsMargins(12, 6, 16, 6)
        total_row.setSpacing(6)
        self.total_stars = StarRow(1, 1, star_radius=10)
        self.total_label = label("", "subheading")
        total_row.addWidget(self.total_stars)
        total_row.addWidget(self.total_label)
        right_row.addWidget(total)
        header = ScreenHeader("Choose a level", right=right, back_text="Back to the title")
        header.back_clicked.connect(self.go_back)
        root.addWidget(header)

        subtitle = label("Every level breaks the controller in one way. Fix it with one MPC idea.", "body")
        subtitle.setContentsMargins(58, 0, 0, 0)  # under the title, past the back button
        root.addWidget(subtitle)

        # cards
        grid_host = QWidget()
        self.grid = QGridLayout(grid_host)
        self.grid.setContentsMargins(0, 8, 0, 8)
        self.grid.setHorizontalSpacing(CARD_SPACING)
        self.grid.setVerticalSpacing(CARD_SPACING)
        self.cards: list[LevelCard] = []
        for level in ctx.levels:
            card = LevelCard(level)
            card.clicked.connect(lambda _=False, c=card: self._open(c))
            self.cards.append(card)
        self._columns = 0
        self._reflow()
        centered = QWidget()  # grid centred both ways inside the scroll area
        outer = QVBoxLayout(centered)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(grid_host)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        root.addWidget(scrollable(centered), 1)

        # message line for locked cards
        self.message = label("", "body", align=Qt.AlignmentFlag.AlignCenter)
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.setInterval(3500)
        self._message_timer.timeout.connect(lambda: self.message.setText(""))
        root.addWidget(self.message)

        self.free_switch.toggled.connect(ctx.state.set_free_mode)
        ctx.state.changed.connect(self.refresh)
        self.refresh()

    def on_enter(self, payload: Any = None) -> None:
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self) -> None:
        """As many cards per row as fit (all 5 in one row on a wide window)."""
        avail = max(1, self.width() - 100)
        cols = max(1, min(len(self.cards), (avail + CARD_SPACING) // (CARD_SIZE.width() + CARD_SPACING)))
        if cols == self._columns:
            return
        self._columns = cols
        for card in self.cards:
            self.grid.removeWidget(card)
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // cols, i % cols, alignment=Qt.AlignmentFlag.AlignCenter)

    def refresh(self) -> None:
        state, levels = self.ctx.state, self.ctx.levels
        self.free_switch.set_checked_silently(state.free_mode)
        if state.free_mode:
            self.message.setText("")
        # the next level to play: the first unlocked one without stars
        nxt = next((c.level for c in self.cards if state.is_unlocked(c.level, levels)
                    and state.stars(c.level.id) == 0 and c.level.is_playable
                    and not c.level.tutorial), None)  # the tutorial is never the suggested level
        for card in self.cards:
            level = card.level
            locked = not state.is_unlocked(level, levels)
            prev = self.ctx.previous_level(level)
            hint = f"Finish level {prev.number} to unlock" if prev else ""
            card.set_progress(state.stars(level.id), locked, hint, is_next=level is nxt)
        rated = [lvl for lvl in levels if not lvl.tutorial]  # the tutorial has no stars
        self.total_label.setText(f"{state.total_stars()} / {MAX_STARS * len(rated)}")

    def _open(self, card: LevelCard) -> None:
        if card.locked:
            prev = self.ctx.previous_level(card.level)
            self.message.setText(f"Level {card.level.number} is locked. Pass level "
                                 f"{prev.number} first, or turn on Free mode.")
            self._message_timer.start()
            return
        self.go(ScreenId.LEVEL, card.level)
