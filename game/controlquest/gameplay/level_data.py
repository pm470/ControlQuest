"""Reads a level file from game/level_data/<id>.json (the same file the engine reads)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LEVEL_DATA_DIR = Path(__file__).resolve().parents[2] / "level_data"  # game/level_data


@dataclass(frozen=True)
class KnobSpec:
    name: str  # key sent to the engine, e.g. "q_p"
    label: str  # "Position weight"
    symbol: str  # "q_p"
    help: str  # tooltip / explanation
    default: float
    min: float
    max: float
    scale: str = "log"  # "log" or "linear"


@dataclass(frozen=True)
class LevelData:
    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def dt(self) -> float:
        return float(self.raw["dt"])

    @property
    def N(self) -> int:
        return int(self.raw["N"])

    @property
    def workspace(self) -> tuple[tuple[float, float], tuple[float, float]]:
        ws = self.raw["workspace"]
        return tuple(ws["min"]), tuple(ws["max"])

    @property
    def start(self) -> tuple[float, float]:
        return tuple(self.raw["start"])

    @property
    def target(self) -> tuple[float, float]:
        return tuple(self.raw["target"])

    @property
    def a_max(self) -> float:
        return float(self.raw["limits"]["a_max"])

    @property
    def v_max(self) -> float:
        return float(self.raw["limits"]["v_max"])

    @property
    def t_limit(self) -> float:
        return float(self.raw["t_limit"])

    @property
    def budget(self) -> dict[str, float]:
        return dict(self.raw.get("budget", {}))

    @property
    def pars(self) -> dict[str, float]:
        return dict(self.raw.get("pars", {}))

    @property
    def blocks(self) -> list[list[tuple[float, float]]]:
        """Obstacle blocks, 4 corners each (what crashes are checked against)."""
        return [[tuple(c) for c in b["corners"]] for b in self.raw.get("blocks", [])]

    @property
    def margin(self) -> float:
        """Obstacle margin added to each ellipse semi-axis (locked value; 0 if none)."""
        return float(self.raw.get("locked", {}).get("margin", 0.0))

    @property
    def locked(self) -> dict[str, float]:
        """Values that are fixed in this level (not knobs), e.g. weights."""
        return dict(self.raw.get("locked", {}))

    @property
    def max_waypoints(self) -> int:
        """How many waypoints the player may place (0 = level without waypoints)."""
        return int(self.raw.get("waypoints", {}).get("max", 0))

    @property
    def switch_radius(self) -> float:
        return float(self.raw.get("waypoints", {}).get("switch_radius", 0.0))

    @property
    def knobs(self) -> list[KnobSpec]:
        fields = KnobSpec.__dataclass_fields__
        return [KnobSpec(**{k: v for k, v in spec.items() if k in fields}) for spec in self.raw["knobs"]]


def load_level_data(level_id: str) -> LevelData:
    path = LEVEL_DATA_DIR / f"{level_id}.json"
    with path.open(encoding="utf-8") as f:
        return LevelData(json.load(f))
