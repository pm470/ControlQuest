"""Which class implements which screen. One line per screen."""

from __future__ import annotations

from ..core.navigation import ScreenId
from .base_screen import BaseScreen
from .how_to_play_screen import HowToPlayScreen
from .level_screen import LevelScreen
from .level_select_screen import LevelSelectScreen
from .settings_screen import SettingsScreen
from .title_screen import TitleScreen

SCREENS: dict[ScreenId, type[BaseScreen]] = {
    ScreenId.TITLE: TitleScreen,
    ScreenId.LEVEL_SELECT: LevelSelectScreen,
    ScreenId.HOW_TO_PLAY: HowToPlayScreen,
    ScreenId.SETTINGS: SettingsScreen,
    ScreenId.LEVEL: LevelScreen,
}
