"""The AppContext bundles the shared services every screen receives.

Pass this one object around instead of many arguments; new shared services
(e.g. a sound player) are added here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine.client import EngineClient
    from ..levels.base import LevelInfo
    from .game_state import GameState


@dataclass
class AppContext:
    state: GameState
    engine: EngineClient
    levels: list[LevelInfo]

    def level_by_id(self, level_id: str) -> LevelInfo | None:
        return next((lvl for lvl in self.levels if lvl.id == level_id), None)

    def previous_level(self, level: LevelInfo) -> LevelInfo | None:
        i = self.levels.index(level)
        return self.levels[i - 1] if i > 0 else None

    def next_level(self, level: LevelInfo) -> LevelInfo | None:
        i = self.levels.index(level)
        return self.levels[i + 1] if i + 1 < len(self.levels) else None
