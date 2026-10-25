"""Rules of Level 1, "The Price of Speed" (PRD 7, Level 1).

The MPC drives the ball from start to target with the player's weights. The
battery holds level["budget"]["energy"] units of E = sum dt*|u_k|^2; the run
stops the moment it is empty (outcome "battery_empty").

Stars: 1 = reach the target; 2 = also within pars.time; 3 = also energy <= pars.energy.
"""

from __future__ import annotations

import numpy as np

from mpc.closed_loop import simulate
from mpc.controller import SolverCache

from .common import (clean_knobs, closed_loop_cost, configured_controller, same_ratios_as_default,
                     solver_metrics, trajectory_json, weights)


def run(level: dict, knobs: dict, cache: SolverCache) -> dict:
    knobs = clean_knobs(level, knobs)
    budget = level["budget"]["energy"]
    mpc = configured_controller(cache, level, knobs)

    def battery(sim) -> str | None:
        return "battery_empty" if sim.energy[-1] > budget else None

    sim = simulate(mpc, [*level["start"], 0.0, 0.0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"],
                   p_min=level["workspace"]["min"], p_max=level["workspace"]["max"],
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"],
                   stop_rule=battery)

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    target = np.array(level["target"])
    metrics = {
        "time": sim.t[-1],
        "energy": sim.energy[-1],
        "distance_left": float(np.linalg.norm(X[-1, :2] - target)),
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
            if metrics["energy"] <= level["pars"]["energy"]:
                stars = 3

    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": stars,
        "metrics": metrics,
        "messages": explain(level, knobs, sim.outcome, sim.detail, metrics, stars),
        "knobs": knobs,
        "trajectory": trajectory_json(sim, level["dt"]),
    }


def explain(level, knobs, outcome, detail, m, stars) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    budget, pars, a_max = level["budget"]["energy"], level["pars"], level["limits"]["a_max"]
    msgs = []
    if outcome == "battery_empty":
        msgs.append(f"The battery ran out at t = {m['time']:.1f} s, {m['distance_left']:.1f} m "
                    f"before the target.")
        if m["max_accel"] >= 0.99 * a_max:
            msgs.append("The controller accelerated and braked at full power: inputs are cheap "
                        "compared with being away from the target. Make inputs more expensive "
                        "(higher r) or being far away cheaper (lower q_p).")
        else:
            msgs.append("Even gentle driving used too much energy over the whole trip.")
    elif outcome == "time_out":
        msgs.append(f"Time is up after {m['time']:.0f} s: the ball is still "
                    f"{m['distance_left']:.2f} m from the target.")
        if m["distance_left"] < 1.0:
            msgs.append("It got close but crept in too slowly: near the target the pull towards "
                        "it (q_p) is too weak compared with the cost of moving (r, q_v).")
        else:
            msgs.append(f"It never went faster than {m['max_speed']:.1f} m/s: moving is too "
                        "expensive. Lower r or q_v, or raise q_p.")
    elif outcome == "controller_failure":
        msgs.append(f"The solver found no valid plan ({detail}).")
    elif outcome == "crash_wall":
        msgs.append("The ball left the field.")
    else:
        msgs.append(f"Arrived in {m['time']:.1f} s using {m['energy']:.2f} of {budget:g} energy.")
        if stars < 2:
            msgs.append(f"For ★★, arrive within {pars['time']:g} s: make moving a bit cheaper.")
        elif stars < 3:
            msgs.append(f"For ★★★, also use at most {pars['energy']:g} energy. Hint: the velocity "
                        "weight q_v acts like damping.")
        else:
            msgs.append("Perfect balance between fast and cheap!")
    if same_ratios_as_default(level, knobs):
        msgs.append("Note: you scaled all weights by the same factor. That does not change the "
                    "optimal plan: only the ratios between Q and R matter.")
    return msgs
