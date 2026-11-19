"""Research content of the levels, for the Research debrief (gameplay/research_debrief.py).

Every module in this package except `base` defines `RESEARCH = ResearchInfo(...)` for one
level (file name = level id). Adding one never requires editing a shared file.

    info = research_for("brake_check")   # ResearchInfo or None
"""

from __future__ import annotations

import importlib
import pkgutil

from .base import PaperRef, ResearchInfo

__all__ = ["PaperRef", "ResearchInfo", "research_for", "all_research"]

_REGISTRY: dict[str, ResearchInfo] | None = None


def all_research() -> dict[str, ResearchInfo]:
    global _REGISTRY
    if _REGISTRY is None:
        found: dict[str, ResearchInfo] = {}
        for module_info in pkgutil.iter_modules(__path__):
            if module_info.name == "base":
                continue
            module = importlib.import_module(f"{__name__}.{module_info.name}")
            info = getattr(module, "RESEARCH", None)
            if not isinstance(info, ResearchInfo):
                raise TypeError(f"{module.__name__} must define RESEARCH = ResearchInfo(...)")
            if info.level_id in found:
                raise ValueError(f"two research files for level {info.level_id!r}")
            found[info.level_id] = info
        _REGISTRY = found
    return _REGISTRY


def research_for(level_id: str) -> ResearchInfo | None:
    return all_research().get(level_id)
