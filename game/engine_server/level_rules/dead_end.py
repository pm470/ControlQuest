"""Rules of Level 3, "Dead End" (PRD 7, Level 3): nonconvexity and local optima.

A U-shaped trap opens towards the start. Without help the MPC drives into the U and
gets stuck in front of the back wall: a local optimum (time out). The weights and the
margin are locked; the player picks ONE fix (level["fixes"]) and tunes only its control:

    "none"       the default MPC (N = level["N"]): fails
    "horizon"    a longer horizon: the knob N (any whole number in its range; a new N
                 compiles its solver once, ~2-3 s); calibrated: it never escapes
    "waypoints"  up to level["waypoints"]["max"] waypoints; the MPC reference is the next
                 waypoint and switches within level["waypoints"]["switch_radius"]

Controls of the other fixes are ignored (e.g. placed waypoints when "horizon" is picked).
Stars: 1 = reach the target; 2 = also within pars.time; 3 = also <= pars.waypoints waypoints.
"""

from __future__ import annotations

import numpy as np

import time

from mpc.closed_loop import simulate
from mpc.controller import SolverCache
from mpc.obstacles import block_distance

from .common import (clean_knobs, clean_waypoints, closed_loop_cost, configured_controller,
                     level_blocks, level_ellipses, solver_metrics, trajectory_json, weights)


def run(level: dict, knobs: dict, cache: SolverCache, waypoints=(), fix: str = "none") -> dict:
    if fix not in {f["id"] for f in level["fixes"]}:
        raise ValueError(f"unknown fix {fix!r} for this level")
    knobs = clean_knobs(level, knobs)
    N = int(knobs["N"]) if fix == "horizon" else int(level["N"])
    waypoints = clean_waypoints(level, waypoints, knobs) if fix == "waypoints" else []
    new_solver = not cache.has(N, level["dt"])
    t0 = time.time()
    mpc = configured_controller(cache, level, knobs, N=N)
    compile_s = time.time() - t0 if new_solver else 0.0
    blocks = level_blocks(level)

    sim = simulate(mpc, [*level["start"], 0.0, 0.0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"],
                   p_min=level["workspace"]["min"], p_max=level["workspace"]["max"],
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"],
                   waypoints=waypoints, switch_radius=level["waypoints"]["switch_radius"],
                   blocks=blocks)

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    target = np.array(level["target"])
    refs = np.array([*waypoints, level["target"]], dtype=float)
    clearances = [min(block_distance(b, p) for b in blocks) for p in X[:, :2]]
    metrics = {
        "fix": fix,
        "N": N,
        "solver_compile_s": round(compile_s, 2),  # > 0 if this run built a new solver
        "horizon_s": N * level["dt"],
        "time": sim.t[-1],
        "energy": sim.energy[-1],
        "waypoints": len(waypoints),
        "waypoints_reached": int(max(sim.ref_index, default=0)),
        "distance_left": float(np.linalg.norm(X[-1, :2] - target)),
        "final_speed": float(np.linalg.norm(X[-1, 2:])),
        "min_clearance": float(min(clearances)),
        "max_accel": float(np.abs(U).max()) if len(U) else 0.0,
        "max_speed": float(np.linalg.norm(X[:, 2:], axis=1).max()),
        "closed_loop_cost": closed_loop_cost(sim, *weights(level, knobs)[:2],
                                             refs[sim.ref_index[:len(U)]], level["dt"]),
        **solver_metrics(sim),
    }
    stars = 0
    if sim.outcome == "success":
        stars = 1
        if metrics["time"] <= level["pars"]["time"]:
            stars = 2
            if len(waypoints) <= level["pars"]["waypoints"]:
                stars = 3

    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": stars,
        "metrics": metrics,
        "messages": explain(level, knobs, sim, metrics, stars)
                    + ([f"(Building the solver for N = {N} took {compile_s:.1f} s, once: it is "
                        "cached now.)"] if compile_s else []),
        "knobs": {**knobs, "N": N},
        "waypoints": waypoints,
        "fix": fix,
        "trajectory": trajectory_json(sim, level["dt"]),
    }


def explain(level, knobs, sim, m, stars) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    pars, horizon, fix = level["pars"], m["horizon_s"], m["fix"]
    blocks = level_blocks(level)
    p_end = np.array(sim.x[-1][:2])
    msgs = []
    if sim.outcome == "time_out":
        dists = [block_distance(b, p_end) for b in blocks]
        j = int(np.argmin(dists))
        if m["final_speed"] < 0.2 and dists[j] < 4.0:
            msgs.append(f"The ball stopped {dists[j]:.1f} m from the block at {_where(blocks[j])} "
                        f"with the target behind it: a local optimum.")
            if fix == "none":
                msgs.append(f"The horizon ({horizon:g} s) cannot see around the obstacle, and every "
                            "small step sideways first costs more. Pick a fix and try it.")
            elif fix == "horizon" and m["N"] <= level["N"]:
                msgs.append(f"A horizon of {horizon:g} s (N = {m['N']}) sees even less than the "
                            f"default {level['N'] * level['dt']:g} s: no way around the wall either. "
                            "Try a longer one.")
            elif fix == "horizon":
                msgs.append(f"Even {horizon:g} s of foresight (N = {m['N']}) did not help: SQP is a "
                            "local method, and warm-started from the previous plan every new plan "
                            "stays on the same side of the wall. The longer horizon only made each "
                            f"solve slower ({m['mean_solve_ms']:.2f} ms on average).")
            else:
                msgs.append(f"It reached {m['waypoints_reached']} of {m['waypoints']} waypoint(s). "
                            "Place them so the straight line to each next one does not lead into "
                            "the trap.")
        else:
            msgs.append(f"Time is up after {m['time']:.0f} s: the ball is still "
                        f"{m['distance_left']:.1f} m from the target."
                        + (" A detour via far-away waypoints takes long." if fix == "waypoints" else ""))
    elif sim.outcome == "crash_block":
        x, y = sim.crash_point
        msgs.append(f"The ball hit the block at {_where(blocks[sim.crash_block])} "
                    f"(contact at ({x:.1f}, {y:.1f})).")
    elif sim.outcome == "controller_failure":
        ell = level_ellipses(level, knobs)
        inside = [j for j, e in enumerate(ell) if e.h(p_end) < 1.0]
        msgs.append(f"The solver found no valid plan at t = {m['time']:.1f} s ({sim.detail}).")
        speed = float(np.linalg.norm(sim.x[-1][2:]))
        brake = speed**2 / (2 * level["limits"]["a_max"])
        gap = min(e.distance(p_end) for e in ell)
        if fix == "horizon" and brake > 0.5 * horizon * speed:
            msgs.append(f"The ball was {gap:.1f} m from an ellipse at {speed:.1f} m/s; stopping needs "
                        f"{brake:.1f} m. Your horizon ({horizon:g} s, N = {m['N']}) saw the wall too "
                        "late: once braking was needed, no plan could avoid the ellipse any more "
                        "(recursive feasibility: the horizon must cover the braking distance).")
        elif inside:
            msgs.append(f"The ball was inside the ellipse of the block at {_where(blocks[inside[0]])}, so no plan "
                        "could satisfy the obstacle constraint.")
        else:
            msgs.append("With obstacles the OCP is nonconvex: SQP can fail when the plan is "
                        "squeezed between two ellipses. Try other waypoints.")
    elif sim.outcome == "crash_wall":
        msgs.append("The ball left the field.")
    else:
        how = f"with {m['waypoints']} waypoint(s)" if fix == "waypoints" else f"with N = {m['N']}"
        msgs.append(f"Arrived in {m['time']:.1f} s {how}, {m['mean_solve_ms']:.2f} ms per solve; "
                    f"closest approach to a block {m['min_clearance']:.1f} m.")
        if stars < 2:
            msgs.append(f"For ★★, arrive within {pars['time']:g} s: a shorter detour helps.")
        elif stars < 3:
            msgs.append(f"For ★★★, use at most {pars['waypoints']:g} waypoint(s): the MPC can find "
                        "its own way once it is out of the trap.")
        else:
            msgs.append("One good hint was enough: the local planner did the rest.")
    return msgs


def _where(corners) -> str:
    """A block named by its centre, e.g. "(31.5, 30.0)" (blocks are not numbered on the map)."""
    c = np.mean(np.asarray(corners, dtype=float), axis=0)
    return f"({c[0]:.0f}, {c[1]:.0f})"
