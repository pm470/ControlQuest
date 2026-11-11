"""Rules of Level 2, "Brake Check" (PRD 7, Level 2): horizon length, recursive
feasibility, terminal constraint.

A fast ball with weak brakes (braking from full speed: v_max / a_max seconds,
v_max^2 / (2 a_max) metres) must stop on a target just in front of the wall. The
weights are locked; the player picks the horizon N (precompiled choices) and can
switch on the terminal constraint v_N = 0 ("terminal stop").

- Short N, no stop: the plan sees the wall too late; once the braking distance is
  longer than the room left, no feasible plan exists -> controller failure.
- Terminal stop: every plan ends at rest, so a way to stop always exists (recursive
  feasibility), but the ball may only drive as fast as it can stop within the horizon.

Stars: 1 = reach the target; 2 = also within pars.time; 3 = also N <= pars.max_N.
Calibrated so that N <= pars.max_N only reaches the target with the terminal stop:
without it even N = 20 sees the wall too late (target 2 m in front of the wall).
"""

from __future__ import annotations

import numpy as np

from mpc.closed_loop import simulate
from mpc.controller import SolverCache

from .common import (clean_knobs, closed_loop_cost, configured_controller, solver_metrics,
                     trajectory_json, weights)


def wall_ahead(p, v, lo, hi) -> float:
    """Distance [m] from p to the workspace wall in the direction of motion v (inf if at rest)."""
    speed = float(np.hypot(v[0], v[1]))
    if speed < 1e-6:
        return float("inf")
    d = np.asarray(v, float) / speed
    dists = [((hi[i] if d[i] > 0 else lo[i]) - p[i]) / d[i] for i in range(2) if abs(d[i]) > 1e-9]
    return max(0.0, float(min(dists)))


def run(level: dict, knobs: dict, cache: SolverCache) -> dict:
    knobs = clean_knobs(level, knobs)
    N, stop = int(knobs["N"]), bool(knobs["stop"])
    mpc = configured_controller(cache, level, knobs, N=N)
    mpc.set_terminal_stop(stop)

    lo, hi = level["workspace"]["min"], level["workspace"]["max"]
    sim = simulate(mpc, [*level["start"], 0.0, 0.0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"], p_min=lo, p_max=hi,
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"])

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    a_max, dt = level["limits"]["a_max"], level["dt"]
    speeds = np.linalg.norm(X[:, 2:], axis=1)
    braking = speeds**2 / (2 * a_max)
    ahead = np.array([wall_ahead(x[:2], x[2:], lo, hi) for x in X])
    late = np.flatnonzero(braking > ahead + 1e-6)  # samples where stopping before the wall is impossible
    k_late = int(late[0]) if len(late) else None
    wall = np.minimum.reduce([X[:, 0] - lo[0], hi[0] - X[:, 0], X[:, 1] - lo[1], hi[1] - X[:, 1]])

    metrics = {
        "N": N,
        "terminal_stop": stop,
        "horizon_s": N * dt,
        "time": sim.t[-1],
        "energy": sim.energy[-1],
        "distance_left": float(np.linalg.norm(X[-1, :2] - np.array(level["target"]))),
        "max_speed": float(speeds.max()),
        "max_accel": float(np.abs(U).max()) if len(U) else 0.0,
        "min_wall_distance": float(wall.min()),
        "overshoot": float(max(0.0, X[:, 0].max() - level["target"][0])),
        "point_of_no_return": None if k_late is None else {
            "t": sim.t[k_late], "wall_ahead": float(ahead[k_late]), "speed": float(speeds[k_late]),
            "braking": float(braking[k_late]), "reach": float(N * dt * speeds[k_late])},
        "closed_loop_cost": closed_loop_cost(sim, *weights(level, knobs)[:2], level["target"], dt),
        **solver_metrics(sim),
    }
    pars = level["pars"]
    stars = 0
    if sim.outcome == "success":
        stars = 1
        if metrics["time"] <= pars["time"]:
            stars = 2
            if N <= pars["max_N"]:
                stars = 3

    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": stars,
        "metrics": metrics,
        "messages": explain(level, sim, metrics, stars),
        "knobs": knobs,
        "trajectory": trajectory_json(sim, dt),
    }


def explain(level, sim, m, stars) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    pars, a_max = level["pars"], level["limits"]["a_max"]
    T, N, stop = m["horizon_s"], m["N"], m["terminal_stop"]
    v_cap = a_max * T  # fastest speed from which the ball can still stop within the horizon
    pnr = m["point_of_no_return"]
    msgs = []
    if sim.outcome in ("controller_failure", "crash_wall"):
        if pnr is not None:
            v, stop_s = pnr["speed"], pnr["speed"] / a_max
            msgs.append(f"At t = {pnr['t']:.1f} s the ball was {pnr['wall_ahead']:.1f} m from the wall at "
                        f"{v:.1f} m/s; braking needs {pnr['braking']:.1f} m and {stop_s:.1f} s.")
            if pnr["reach"] < pnr["braking"] - 0.05:
                msgs.append(f"Your horizon covered {T:g} s (≈ {pnr['reach']:.1f} m), less than the braking "
                            "distance: the plan saw the wall too late.")
            else:
                msgs.append(f"Your horizon covered {T:g} s (≈ {pnr['reach']:.1f} m), just about the braking "
                            "distance: the wall came into view only when braking already had to start, with "
                            f"no margin. A {T:g} s plan cannot even contain a full stop from {v:.1f} m/s.")
        msgs.append(("From then on no plan could stop before the wall, so the OCP had no solution "
                     f"(at t = {m['time']:.1f} s): the controller lost recursive feasibility."
                     if sim.outcome == "controller_failure" else "The ball hit the wall."))
        msgs.append("Look further ahead (a longer N), or require every plan to end at rest "
                    "(terminal stop).")
    elif sim.outcome == "time_out":
        if stop:
            msgs.append(f"Time is up: with the terminal stop every plan must end at rest within {T:g} s, "
                        f"so the ball may drive at most ≈ {v_cap:.1f} m/s (a_max · N·Δt). Safe, but "
                        f"too slow with N = {N}.")
        else:
            msgs.append(f"Time is up after {m['time']:.0f} s: the ball is still "
                        f"{m['distance_left']:.1f} m from the target.")
    else:
        msgs.append(f"Arrived in {m['time']:.1f} s with N = {N} ({T:g} s ahead), terminal stop "
                    f"{'on' if stop else 'off'}; it overshot the star by {m['overshoot']:.2f} m.")
        if stars < 2:
            msgs.append(f"For ★★, arrive within {pars['time']:g} s. With the terminal stop the ball may only "
                        f"drive ≈ {v_cap:.1f} m/s here: a longer horizon allows more speed.")
        elif stars < 3:
            msgs.append(f"For ★★★, use N ≤ {pars['max_N']}: smaller, faster solves "
                        f"({m['mean_solve_ms']:.2f} ms each now). A short horizon alone sees the wall "
                        "too late, so it needs something that keeps a way to stop in every plan.")
        else:
            msgs.append("Short horizon + terminal stop: every plan keeps a way to stop, so the "
                        "controller stays feasible and calm with cheap solves.")
    return msgs
