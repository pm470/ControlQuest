"""Player progress and preferences for one session.

Progress is kept in memory (nothing is written to disk yet). If we want to keep
it between sessions later, only this file needs to change (load in __init__,
save in _emit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from .config import MAX_STARS

if TYPE_CHECKING:
    from ..levels.base import LevelInfo


class GameState(QObject):
    """Stars per level, free mode and settings. Emits `changed` on every change."""

    changed = Signal()
    engine_url_changed = Signal(str)

    def __init__(self, engine_url: str, parent: QObject | None = None):
        super().__init__(parent)
        self._stars: dict[str, int] = {}
        self._free_mode = False
        self._animations = True
        self._engine_url = engine_url

    # --- progress --------------------------------------------------------------
    def stars(self, level_id: str) -> int:
        return self._stars.get(level_id, 0)

    def total_stars(self) -> int:
        return sum(self._stars.values())

    def record_result(self, level_id: str, stars: int) -> None:
        """Store a finished run; only an improvement changes the saved stars."""
        stars = max(0, min(MAX_STARS, int(stars)))
        if stars > self.stars(level_id):
            self._stars[level_id] = stars
            self.changed.emit()

    def reset_progress(self) -> None:
        if self._stars:
            self._stars.clear()
            self.changed.emit()

    def is_unlocked(self, level: LevelInfo, levels: list[LevelInfo]) -> bool:
        """PRD 5.1: level 1 is open; each passed level unlocks the next; free mode opens all."""
        if self._free_mode:
            return True
        index = levels.index(level)
        return index == 0 or self.stars(levels[index - 1].id) > 0

    # --- preferences -----------------------------------------------------------
    @property
    def free_mode(self) -> bool:
        return self._free_mode

    def set_free_mode(self, on: bool) -> None:
        if on != self._free_mode:
            self._free_mode = on
            self.changed.emit()

    @property
    def animations(self) -> bool:
        return self._animations

    def set_animations(self, on: bool) -> None:
        if on != self._animations:
            self._animations = on
            self.changed.emit()

    @property
    def engine_url(self) -> str:
        return self._engine_url

    def set_engine_url(self, url: str) -> None:
        url = url.strip().rstrip("/")
        if url and url != self._engine_url:
            self._engine_url = url
            self.engine_url_changed.emit(url)
            self.changed.emit()
