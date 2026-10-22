"""Identifiers of all screens. Screens navigate by emitting one of these ids.

Adding a screen: add an id here, write the screen in screens/, and register it
in screens/registry.py.
"""

from __future__ import annotations

from enum import Enum


class ScreenId(str, Enum):
    TITLE = "title"
    LEVEL_SELECT = "level_select"
    HOW_TO_PLAY = "how_to_play"
    SETTINGS = "settings"
    LEVEL = "level"  # payload: the LevelInfo to open
