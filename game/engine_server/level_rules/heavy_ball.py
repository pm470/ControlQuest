"""Rules of Level 4, "Heavy Ball" (PRD 7, Level 4): model mismatch.

The real ball (plant) responds with gain level["plant"]["g_true"] (hidden from the
player); the controller's model uses the knob g. The player has two knobs (PRD):
    margin  enlarge the obstacle ellipses. Calibrated: it does NOT prevent the failure
            here (the danger is braking too late in front of the back wall, and a margin
            does not make the ball brake earlier); too large closes the bay.
    g       identify the real gain with the test drive and put it into the model: works.

Stars: 1 = reach the target; 2 = also within pars.time; 3 = also within pars.time_best.
"""

from __future__ import annotations

import numpy as np

from mpc.closed_loop import plant_step, simulate
from mpc.controller import SolverCache
from mpc.obstacles import block_distance

from .common import (clean_knobs, closed_loop_cost, configured_controller, level_blocks,
                     level_ellipses, solver_metrics, trajectory_json, weights)


def prediction_errors(sim, M: int) -> np.ndarray:
    """Per sample k (length n+1): distance [m] between where the plan computed M samples
    earlier said the ball would be at t_k (stage M of plan k-M) and where the real ball
    is. One-step errors are tiny (re-planning corrects them every step), M steps show
    the mismatch. 0 for k < M."""
    err = np.zeros(len(sim.x))
    for k in range(M, len(sim.x)):
        if k - M < len(sim.plans):
            err[k] = np.linalg.norm(np.asarray(sim.plans[k - M][M][:2]) - np.asarray(sim.x[k][:2]))
    return err


def run(level: dict, knobs: dict, cache: SolverCache) -> dict:
    knobs = clean_knobs(level, knobs)
    mpc = configured_controller(cache, level, knobs, model_gain=knobs["g"])
    blocks = level_blocks(level)
    sim = simulate(mpc, [*level["start"], 0.0, 0.0], [*level["target"], 0.0, 0.0],
                   dt=level["dt"], t_limit=level["t_limit"],
                   p_min=level["workspace"]["min"], p_max=level["workspace"]["max"],
                   pos_tol=level["tolerance"]["position"], speed_tol=level["tolerance"]["speed"],
                   plant_gain=level["plant"]["g_true"], blocks=blocks)

    X, U = np.array(sim.x), np.array(sim.u).reshape(-1, 2)
    target = np.array(level["target"])
    M = int(level.get("prediction_lookahead", 10))
    err = prediction_errors(sim, M)
    metrics = {
        "time": sim.t[-1],
        "energy": sim.energy[-1],
        "margin": knobs["margin"],
        "g": knobs["g"],
        "distance_left": float(np.linalg.norm(X[-1, :2] - target)),
        "min_clearance": float(min(block_distance(b, p) for b in blocks for p in X[:, :2])),
        "max_prediction_error": float(err.max()) if len(err) else 0.0,
        "prediction_lookahead_s": M * level["dt"],
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
            if metrics["time"] <= level["pars"]["time_best"]:
                stars = 3

    traj = trajectory_json(sim, level["dt"])
    traj["prediction_error"] = [round(float(e), 4) for e in err]  # per sample (n+1)
    traj["prediction_lookahead"] = M  # the game draws stage M of plan k-M as a ghost ball
    return {
        "level_id": level["id"],
        "outcome": sim.outcome,
        "stars": stars,
        "metrics": metrics,
        "messages": explain(level, knobs, sim, metrics, err, M, stars),
        "knobs": knobs,
        "trajectory": traj,
    }


def test_drive(level: dict, knobs: dict) -> dict:
    """PRD 7, Level 4 "Test drive": constant ax = accel for `duration` s from rest on an
    empty field. Predicted = what the model (knob g) expects, measured = the real ball."""
    knobs = clean_knobs(level, knobs)
    a, T, dt = level["test_drive"]["accel"], level["test_drive"]["duration"], level["dt"]
    x = np.zeros(4)
    for _ in range(int(round(T / dt))):
        x = plant_step(x, np.array([a, 0.0]), dt, gain=level["plant"]["g_true"])
    predicted = 0.5 * knobs["g"] * a * T**2  # exact for the model's double integrator
    return {"level_id": level["id"], "accel": a, "duration": T, "g": knobs["g"],
            "predicted_m": round(predicted, 3), "measured_m": round(float(x[0]), 3)}


def explain(level, knobs, sim, m, err, M, stars) -> list[str]:
    """The "What happened" sentences (PRD 10.1), with numbers from this run."""
    pars, g = level["pars"], knobs["g"]
    msgs = []
    # quote the worst prediction in the last 3 s (the braking that went wrong), not the start
    tail = max(0, len(err) - int(round(3.0 / level["dt"])))
    k = tail + int(np.argmax(err[tail:])) if len(err) else 0
    mismatch = len(err) and err[k] > 0.05
    if sim.outcome in ("crash_block", "controller_failure"):
        if sim.outcome == "crash_block":
            x, y = sim.crash_point
            msgs.append(f"The ball hit a block at ({x:.1f}, {y:.1f}) after {m['time']:.1f} s.")
        else:
            msgs.append(f"The solver found no valid plan at t = {m['time']:.1f} s: the ball was "
                        "already too close to (or inside) an obstacle ellipse.")
        if mismatch:
            pred, real = sim.plans[k - M][M][:2], sim.x[k][:2]
            msgs.append(f"At t = {k * level['dt']:.1f} s the plan from {M * level['dt']:g} s earlier "
                        f"predicted the ball at ({pred[0]:.2f}, {pred[1]:.2f}); it actually was at "
                        f"({real[0]:.2f}, "
                        f"{real[1]:.2f}). The model (g = {g:g}) assumes the ball reacts more "
                        "strongly than it does, so it brakes too late.")
        if knobs["margin"] > 0.2:
            msgs.append(f"The {knobs['margin']:g} m margin did not help: it keeps plans away from "
                        "the walls, but the ball still brakes as late as the model allows. The "
                        "error is in the model.")
    elif sim.outcome == "time_out":
        msgs.append(f"Time is up after {m['time']:.0f} s: the ball is still {m['distance_left']:.1f} m "
                    "from the target.")
        if knobs["margin"] > 1.0:
            msgs.append(f"A {knobs['margin']:g} m margin makes the bay (almost) too narrow for the "
                        "solver: robustness costs space and time.")
    elif sim.outcome == "crash_wall":
        msgs.append("The ball left the field.")
    else:
        msgs.append(f"Parked in {m['time']:.1f} s with a {knobs['margin']:g} m margin and model gain "
                    f"g = {g:g}; the plans were off by at most {m['max_prediction_error']:.2f} m "
                    f"({M * level['dt']:g} s ahead).")
        if stars < 2:
            msgs.append(f"For ★★, park within {pars['time']:g} s: the controller is driving more "
                        "carefully than it needs to.")
        elif stars < 3:
            msgs.append(f"For ★★★, park within {pars['time_best']:g} s: the closer the model's g is "
                        "to the real ball, the harder it can brake without crashing.")
        elif m["max_prediction_error"] > 0.05:
            msgs.append("The model is not exact, but it errs on the safe side: it expects the ball "
                        "to react less than it does, so the controller brakes in time.")
        else:
            msgs.append("The model matches the real ball: the plan and the ball agree, so the "
                        "controller can drive fast and still stop in time.")
    return msgs
