"""Rules of Level 5, "Crosswind" (PRD 7, Level 5): feedback, i.e. why we re-plan.

The real ball is pushed by wind (level["wind"]: a constant part plus gusts that stay
constant for gust_period seconds, from a fixed seed, so every run is the same). The
controller does not know the wind. The player chooses the re-plan interval k (solve
every k samples, open-loop in between) and the obstacle margin. Every solve uses one
unit of the compute budget; the run stops the moment it is used up ("solve_budget").

Stars: 1 = reach the target; 2 = also within pars.time; 3 = also <= pars.solves solves.
"""

from __future__ import annotations

import numpy as np

from mpc.closed_loop import simulate
from mpc.controller import SolverCache
from mpc.obstacles import block_distance

from .common import (clean_knobs, closed_loop_cost, configured_controller, level_blocks,
                     solver_metrics, trajectory_json, weights)


def wind_function(level: dict):
    """wind(k) -> acceleration [m/s^2] at sample k: constant + piecewise-constant gusts."""
    w = level["wind"]
    const, amp = np.asarray(w["constant"], float), np.asarray(w["gust_amplitude"], float)
    per = max(1, int(round(w["gust_period"] / level["dt"])))
    n = int(round(level["t_limit"] / level["dt"])) // per + 2
    gusts = np.random.default_rng(w["seed"]).uniform(-1.0, 1.0, size=(n, 2)) * amp

    def wind(k: int) -> np.ndarray:
        return const + gusts[min(k // per, n - 1)]
    return wind


def drift(sim) -> np.ndarray:
    """Per sample k (length n+1): distance [m] between where the plan being executed said
    the ball would be at t_k and where it is. Grows during an open-loop stretch."""
    out = np.zeros(len(sim.x))
    s = 0
    for k in range(len(sim.x)):
        while s + 1 < len(sim.solve_steps) and sim.solve_steps[s + 1] <= k:
            s += 1
        if not sim.solve_steps:
            break
        m = k - sim.solve_steps[s]
        plan = sim.plans[s]
        if 0 <= m < len(plan):
            out[k] = np.linalg.norm(np.asarray(plan[m][:2]) - np.asarray(sim.x[k][:2]))
    return out


def run(level: dict, knobs: dict, cache: SolverCache) -> dict:
    knobs = clean_knobs(level, knobs)
    k_replan = int(knobs["k"])
    budget = int(level["budget"]["solves"])
    mpc = configured_controller(cache, level, knobs)
    blocks = level_blocks(level)

    def out_of_budget(sim) -> str | None:
        return "solve_budget" if len(sim.solve_time) >= budget and \
            (len(sim.u) - sim.solve_steps[-1]) >= k_replan else None

    sim = simulate(mpc, [*level["start"], 0.0, 0.0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"],
                   p_min=level["workspace"]["min"], p_max=level["workspace"]["max"],
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"],
                   blocks=blocks, replan_every=k_replan, disturbance=wind_function(level),
                   stop_rule=out_of_budget)

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    target = np.array(level["target"])
    d = drift(sim)
    metrics = {
        "time": sim.t[-1],
        "energy": sim.energy[-1],
        "k": k_replan,
        "margin": knobs["margin"],
        "solves_used": len(sim.solve_time),
        "solve_budget": budget,
        "max_drift": float(d.max()) if len(d) else 0.0,
        "distance_left": float(np.linalg.norm(X[-1, :2] - target)),
        "min_clearance": float(min(block_distance(b, p) for b in blocks for p in X[:, :2])),
        "max_accel": float(np.abs(U).max()) if len(U) else 0.0,
        "max_speed": float(np.linalg.norm(X[:, 2:], axis=1).max()),
        "closed_loop_cost": closed_loop_cost(sim, *weights(level, knobs)[:2], level["target"], level["dt"]),
        **solver_metrics(sim),
    }
    stars = 0
    if sim.outcome == "success":
        stars = 1
        if metrics["time"] <= level["pars"]["time"]:
            stars = 2
            if metrics["solves_used"] <= level["pars"]["solves"]:
                stars = 3

    traj = trajectory_json(sim, level["dt"])
    traj["drift"] = [round(float(v), 4) for v in d]
    traj["solve_budget"] = budget
    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": stars,
        "metrics": metrics,
        "messages": explain(level, knobs, sim, metrics, d, stars),
        "knobs": knobs,
        "trajectory": traj,
    }


def explain(level, knobs, sim, m, d, stars) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    pars, dt, k = level["pars"], level["dt"], m["k"]
    msgs = []
    if sim.outcome == "solve_budget":
        msgs.append(f"The compute budget ({m['solve_budget']} solves) ran out at t = {m['time']:.1f} s, "
                    f"{m['distance_left']:.1f} m before the target.")
        msgs.append(f"Re-planning every {k} sample(s) = every {k * dt:g} s costs about "
                    f"{m['time'] / (k * dt):.0f} solves for this stretch alone: re-plan less often.")
    elif sim.outcome in ("crash_block", "controller_failure", "crash_wall"):
        what = {"crash_block": "The ball hit a block", "crash_wall": "The ball left the field",
                "controller_failure": "The solver found no valid plan"}[sim.outcome]
        msgs.append(f"{what} at t = {m['time']:.1f} s.")
        if k > 1:
            msgs.append(f"Between re-plans the ball ran open-loop for {k * dt:g} s and the wind pushed "
                        f"it up to {m['max_drift']:.2f} m off the plan. Re-plan more often, or give it "
                        "more room (margin).")
        elif sim.outcome == "controller_failure":
            msgs.append(f"({sim.detail})")
    elif sim.outcome == "time_out":
        msgs.append(f"Time is up after {m['time']:.0f} s: the ball is still {m['distance_left']:.1f} m "
                    "from the target.")
        if knobs["margin"] > 1.5:
            msgs.append(f"A {knobs['margin']:g} m margin closes most of the gap between the blocks.")
    else:
        msgs.append(f"Through the gap in {m['time']:.1f} s with {m['solves_used']} of "
                    f"{m['solve_budget']} solves (re-plan every {k * dt:g} s); the wind pushed the "
                    f"ball up to {m['max_drift']:.2f} m off its plan.")
        if stars < 2:
            msgs.append(f"For ★★, arrive within {pars['time']:g} s.")
        elif stars < 3:
            msgs.append(f"For ★★★, use at most {pars['solves']:g} solves: re-plan less often, and "
                        "maybe give the wind more room.")
        else:
            msgs.append("Just enough feedback: re-planning corrects the wind before it matters.")
    return msgs
