"""Runs a level: request in (level id + knobs), result out (RunResult dict, PRD 9.4).

One SolverCache for the whole engine; solvers are compiled once per problem
shape and reused by every run and every level.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from level_rules import crosswind, dead_end, heavy_ball, price_of_speed
from level_rules.common import horizons, load_level
from mpc.controller import SolverCache

BUILD_DIR = Path(__file__).resolve().parent / "build"  # generated C code (gitignored)

# level id -> rules module; add one line per playable level
RULES = {
    "price_of_speed": price_of_speed,
    "dead_end": dead_end,
    "heavy_ball": heavy_ball,
    "crosswind": crosswind,
}

cache = SolverCache(BUILD_DIR)
_run_lock = threading.Lock()  # acados solvers are not thread-safe: one run at a time


def run_level(level_id: str, knobs: dict, waypoints=None, fix=None) -> dict:
    if level_id not in RULES:
        raise ValueError(f"level '{level_id}' is not playable yet")
    if not isinstance(knobs, dict):
        raise ValueError("knobs must be an object {name: value}")
    if waypoints is not None and not isinstance(waypoints, list):
        raise ValueError("waypoints must be a list of [x, y]")
    level = load_level(level_id)
    extra = {}
    if "waypoints" in level:  # only levels with waypoint rules take them (PRD 7, Level 3)
        extra["waypoints"] = waypoints or []
    elif waypoints:
        raise ValueError(f"level '{level_id}' does not take waypoints")
    if "fixes" in level:  # levels where the player picks one fix (Level 3)
        extra["fix"] = fix or "none"
    elif fix:
        raise ValueError(f"level '{level_id}' does not take a fix")
    with _run_lock:
        t0 = time.time()
        result = RULES[level_id].run(level, knobs, cache, **extra)
        result["compute_time_s"] = round(time.time() - t0, 3)
        result["metrics"]["compute_time_s"] = result["compute_time_s"]
    return result


def test_drive(level_id: str, knobs: dict) -> dict:
    """The level's test drive (Level 4): predicted vs measured distance, no MPC involved."""
    rules = RULES.get(level_id)
    if rules is None or not hasattr(rules, "test_drive"):
        raise ValueError(f"level '{level_id}' has no test drive")
    if not isinstance(knobs, dict):
        raise ValueError("knobs must be an object {name: value}")
    return rules.test_drive(load_level(level_id), knobs)


def warm_up() -> None:
    """Compile the solvers of all playable levels now (every horizon N they can use),
    so no Run has to wait for a compilation (PRD 9.3)."""
    for level_id in RULES:
        level = load_level(level_id)
        for N in horizons(level):
            cache.get(N, level["dt"])
