"""Rules of Level 0, "Hello, MPC" (tutorial): a guided tour of the MPC loop.

A small open field (20 m), so plans and inputs are easy to see; the start velocity comes
from the level file ("start_velocity", now at rest). Everything is fixed (no knobs:
the tutorial only shows the loop; changing N is Level 2's topic). The run is the plain
closed loop: measure -> solve the OCP -> apply u_0 -> repeat. Nothing to fail on purpose
and no stars (the game shows this level as a tutorial).
"""

from __future__ import annotations

import numpy as np

from mpc.closed_loop import simulate
from mpc.controller import SolverCache

from .common import (clean_knobs, closed_loop_cost, configured_controller, solver_metrics,
                     trajectory_json, weights)


def run(level: dict, knobs: dict, cache: SolverCache) -> dict:
    knobs = clean_knobs(level, knobs)
    N = int(level["N"])  # no knobs: the tutorial only shows the loop
    mpc = configured_controller(cache, level, knobs, N=N)
    v0 = level.get("start_velocity", [0.0, 0.0])  # start velocity from the level file
    sim = simulate(mpc, [*level["start"], *v0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"],
                   p_min=level["workspace"]["min"], p_max=level["workspace"]["max"],
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"])

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    target = np.array(level["target"])
    metrics = {
        "time": sim.t[-1],
        "N": N,
        "horizon_s": round(N * level["dt"], 6),
        "energy": sim.energy[-1],
        "distance_left": float(np.linalg.norm(X[-1, :2] - target)),
        "max_accel": float(np.abs(U).max()) if len(U) else 0.0,
        "max_speed": float(np.linalg.norm(X[:, 2:], axis=1).max()),
        "closed_loop_cost": closed_loop_cost(sim, *weights(level, knobs)[:2], level["target"], level["dt"]),
        **solver_metrics(sim),
    }
    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": 0,  # tutorial: no stars
        "metrics": metrics,
        "messages": explain(level, sim.outcome, sim.detail, metrics),
        "knobs": knobs,
        "trajectory": trajectory_json(sim, level["dt"]),
    }


def explain(level, outcome, detail, m) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    N, T = m["N"], m["horizon_s"]
    if outcome == "success":
        return [f"Arrived in {m['time']:.1f} s. The MPC solved its OCP {m.get('solves', 0)} times, "
                f"once every {level['dt']:g} s, each time planning $N = {N}$ steps ({T:g} s) ahead "
                "from the measured state, and applied only the first input of each plan."]
    if outcome == "time_out":
        return [f"Time is up after {m['time']:.0f} s: the ball is still {m['distance_left']:.2f} m "
                "from the target."]
    if outcome == "controller_failure":
        return [f"The solver found no valid plan ({detail})."]
    return ["The ball left the field."]
