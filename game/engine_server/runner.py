"""Runs a level: request in (level id + knobs), result out (RunResult dict, PRD 9.4).

One SolverCache for the whole engine; solvers are compiled once per problem
shape and reused by every run and every level.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from level_rules import price_of_speed
from level_rules.common import load_level
from mpc.controller import SolverCache

BUILD_DIR = Path(__file__).resolve().parent / "build"  # generated C code (gitignored)

# level id -> rules module; add one line per playable level
RULES = {
    "price_of_speed": price_of_speed,
}

cache = SolverCache(BUILD_DIR)
_run_lock = threading.Lock()  # acados solvers are not thread-safe: one run at a time


def run_level(level_id: str, knobs: dict) -> dict:
    if level_id not in RULES:
        raise ValueError(f"level '{level_id}' is not playable yet")
    if not isinstance(knobs, dict):
        raise ValueError("knobs must be an object {name: value}")
    level = load_level(level_id)
    with _run_lock:
        t0 = time.time()
        result = RULES[level_id].run(level, knobs, cache)
        result["compute_time_s"] = round(time.time() - t0, 3)
        result["metrics"]["compute_time_s"] = result["compute_time_s"]
    return result


def warm_up() -> None:
    """Compile the solvers of all playable levels now, so the first Run is fast."""
    for level_id in RULES:
        level = load_level(level_id)
        cache.get(level["N"], level["dt"])
