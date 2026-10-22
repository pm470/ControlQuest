"""Level registry.

Every module in this package named `level_*.py` that defines `LEVEL = LevelInfo(...)`
is picked up automatically and sorted by `LevelInfo.number`. Adding a level never
requires editing a shared file, which avoids merge conflicts.
"""

from __future__ import annotations

import importlib
import pkgutil

from .base import LevelInfo

__all__ = ["LevelInfo", "discover_levels"]


def discover_levels() -> list[LevelInfo]:
    levels: list[LevelInfo] = []
    for module_info in pkgutil.iter_modules(__path__):
        if not module_info.name.startswith("level_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        level = getattr(module, "LEVEL", None)
        if not isinstance(level, LevelInfo):
            raise TypeError(f"{module.__name__} must define LEVEL = LevelInfo(...)")
        levels.append(level)
    levels.sort(key=lambda lvl: lvl.number)

    for attr in ("number", "id"):
        values = [getattr(lvl, attr) for lvl in levels]
        dupes = {v for v in values if values.count(v) > 1}
        if dupes:
            raise ValueError(f"Duplicate level {attr}(s): {sorted(dupes)}")
    return levels
