"""What every level file provides: a LevelInfo describing the level.

LevelInfo holds what the menus and the level intro show. When a level becomes
playable, its file sets `play_screen` to a function that builds the level's gameplay
widget; the level screen then shows that instead of the "coming soon" card. With
`intro` set too, the level screen first shows the level intro (gameplay/level_intro.py:
story, what you learn, how the level teaches it, goal, stars, the OCP with what is
new) and the play screen after "Start level".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from ..core.context import AppContext
    from ..gameplay.level_data import LevelData
    from ..gameplay.level_intro import LevelIntro


@dataclass(frozen=True)
class LevelInfo:
    number: int  # order in the level select (1, 2, ...)
    id: str  # stable key, e.g. "price_of_speed" (used for progress and the engine)
    title: str  # shown on the card, e.g. "The Price of Speed"
    topic: str  # short MPC topic tag, e.g. "Cost trade-off"
    briefing: str  # the in-game story line (PRD 7, "Briefing"); the quote in the intro
    concept: str  # what the player learns (PRD 7, "Concept"); intro: "What you learn"
    teaching: str = ""  # intro: "How this level teaches it" (how the default fails, fix ideas)
    hints: tuple[str, ...] = ()  # PRD 5.8: from "points at the concept" to "almost the answer"
    accent: str = "coral"  # colour key in ui.theme.ACCENTS
    icon: str = ""  # tile icon in the level select (ui.painting.draw_level_icon): bolt, wall, ...
    # a tutorial (Level 0): no stars, always open, never locks the next level, never the
    # suggested "next level" in the level select, a "Tutorial" tag instead of stars
    tutorial: bool = False
    # builds the gameplay widget: play_screen(ctx, level) -> QWidget; None = not built yet
    play_screen: Optional[Callable[[AppContext, LevelInfo], QWidget]] = None
    # the intro's numbers and math: intro(data) -> LevelIntro (goal, stars, OCP with the new
    # parts marked, ...); None = the level opens straight on the play screen
    intro: Optional[Callable[[LevelData], LevelIntro]] = None

    @property
    def is_playable(self) -> bool:
        return self.play_screen is not None
