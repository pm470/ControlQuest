"""What every level file provides: a LevelInfo describing the level.

For now LevelInfo holds what the menus show. When a level becomes playable, its
file sets `play_screen` to a function that builds the level's gameplay widget;
the level screen then shows that instead of the "coming soon" card. More fields
(map, knobs, budgets, pars, see PRD 9.4) are added here as we need them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from ..core.context import AppContext


@dataclass(frozen=True)
class LevelInfo:
    number: int  # order in the level select (1, 2, ...)
    id: str  # stable key, e.g. "price_of_speed" (used for progress and the engine)
    title: str  # shown on the card, e.g. "The Price of Speed"
    topic: str  # short MPC topic tag, e.g. "Cost trade-off"
    briefing: str  # the in-game story line (PRD 7, "Briefing")
    concept: str  # what the player learns (PRD 7, "Concept")
    hints: tuple[str, ...] = ()  # PRD 5.8: from "points at the concept" to "almost the answer"
    accent: str = "coral"  # colour key in ui.theme.ACCENTS
    # builds the gameplay widget: play_screen(ctx, level) -> QWidget; None = not built yet
    play_screen: Optional[Callable[[AppContext, LevelInfo], QWidget]] = None

    @property
    def is_playable(self) -> bool:
        return self.play_screen is not None
