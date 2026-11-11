"""Helpers shared by all level rules: loading level files, knobs -> MPC settings,
configuring a controller, and turning a Simulation into the RunResult JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mpc.closed_loop import Simulation
from mpc.controller import MPCController, SolverCache
from mpc.obstacles import Ellipse, ellipse_from_corners

LEVEL_DATA_DIR = Path(__file__).resolve().parents[2] / "level_data"  # game/level_data


def load_level(level_id: str) -> dict:
    path = LEVEL_DATA_DIR / f"{level_id}.json"
    if not path.is_file():
        raise ValueError(f"unknown level '{level_id}' (no {path.name})")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def clean_knobs(level: dict, knobs: dict) -> dict:
    """Knob values from the request, clamped to their range; missing ones use defaults.
    Knobs with "choices" snap to the nearest allowed value; "scale": "int" knobs
    (e.g. horizon N) are rounded to a whole number."""
    out = {}
    for spec in level["knobs"]:
        value = knobs.get(spec["name"], spec["default"])
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"knob {spec['name']} must be a number, got {value!r}") from None
        if not np.isfinite(value):
            raise ValueError(f"knob {spec['name']} must be finite")
        if "choices" in spec:
            out[spec["name"]] = min(spec["choices"], key=lambda c: abs(c - value))
        elif spec.get("scale") == "int":
            out[spec["name"]] = int(min(max(round(value), spec["min"]), spec["max"]))
        else:
            out[spec["name"]] = min(max(value, spec["min"]), spec["max"])
    unknown = set(knobs) - set(out)
    if unknown:
        raise ValueError(f"unknown knob(s) for this level: {sorted(unknown)}")
    return out


def weights(level: dict, knobs: dict):
    """Q = diag(q_p, q_p, q_v, q_v), R = r*I, P = terminal_factor * Q.
    Weights that are not knobs of this level come from level["locked"]."""
    knobs = {**level.get("locked", {}), **knobs}
    qp, qv, r = knobs["q_p"], knobs["q_v"], knobs["r"]
    Q = np.diag([qp, qp, qv, qv])
    return Q, r * np.eye(2), level["terminal_factor"] * Q


def configured_controller(cache: SolverCache, level: dict, knobs: dict,
                          model_gain: float = 1.0, N: int | None = None) -> MPCController:
    """Get the (cached) solver for this level's shape and load this run's numbers into it.
    N overrides the level's horizon (a knob in some levels)."""
    mpc = cache.get(int(N or level["N"]), level["dt"])
    a, v = level["limits"]["a_max"], level["limits"]["v_max"]
    p_min, p_max = level["workspace"]["min"], level["workspace"]["max"]
    mpc.set_weights(*weights(level, knobs))
    mpc.set_bounds([*p_min, -v, -v], [*p_max, v, v], [-a, -a], [a, a])
    mpc.set_model_gain(model_gain)
    ellipses = level_ellipses(level, knobs)
    mpc.set_obstacles([(e.center, e.E) for e in ellipses])
    mpc.set_damping(level.get("solver", {}).get("levenberg_marquardt", 1e-2) if ellipses else 0.0)
    # level["solver"]["ellipse_entry_fails"] = false: entering an ellipse is not a failure
    # (Level 5: the wind pushes the ball into the safety zone; touching a block still crashes)
    mpc.set_strict_obstacles(level.get("solver", {}).get("ellipse_entry_fails", True))
    mpc.set_target([*level["target"], 0.0, 0.0])
    return mpc


def horizons(level: dict) -> list[int]:
    """Every horizon N a level can use (its N plus the choices of an "N" knob)."""
    ns = {int(level["N"])}
    for spec in level.get("knobs", []):
        if spec["name"] == "N":
            ns.update(int(c) for c in spec.get("choices", []))
    return sorted(ns)


def level_blocks(level: dict) -> list:
    """The level's blocks, each a list of 4 corners [[x, y], ...] (what crashes are checked against)."""
    return [b["corners"] for b in level.get("blocks", [])]


def level_ellipses(level: dict, knobs: dict | None = None) -> list[Ellipse]:
    """What the solver avoids: each block's enclosing ellipse, enlarged by the obstacle
    margin (a knob in some levels, otherwise level["locked"]["margin"])."""
    margin = float({**level.get("locked", {}), **(knobs or {})}.get("margin", 0.0))
    return [ellipse_from_corners(c, margin) for c in level_blocks(level)]


def clean_waypoints(level: dict, waypoints, knobs: dict | None = None) -> list[list[float]]:
    """Waypoints from the request, checked against the level's rules (PRD 7, Level 3)."""
    waypoints = list(waypoints or [])
    rules = level.get("waypoints")
    if not waypoints:
        return []
    if rules is None:
        raise ValueError("this level does not take waypoints")
    if len(waypoints) > rules["max"]:
        raise ValueError(f"at most {rules['max']} waypoints, got {len(waypoints)}")
    (x0, y0), (x1, y1) = level["workspace"]["min"], level["workspace"]["max"]
    out = []
    for i, w in enumerate(waypoints, 1):
        try:
            x, y = (float(v) for v in w)
        except (TypeError, ValueError):
            raise ValueError(f"waypoint {i} must be [x, y], got {w!r}") from None
        if not (np.isfinite(x) and np.isfinite(y) and x0 <= x <= x1 and y0 <= y <= y1):
            raise ValueError(f"waypoint {i} ({x}, {y}) is outside the field")
        if any(e.h([x, y]) < 1.0 for e in level_ellipses(level, knobs)):
            raise ValueError(f"waypoint {i} ({x:.1f}, {y:.1f}) is inside an obstacle ellipse")
        out.append([x, y])
    return out


def trajectory_json(sim: Simulation, dt: float) -> dict:
    """The replay data (PRD 9.4), rounded to keep the JSON small."""
    return {
        "dt": dt,
        "t": [round(t, 4) for t in sim.t],
        "x": np.round(np.array(sim.x), 4).tolist(),
        "u": np.round(np.array(sim.u).reshape(-1, 2), 4).tolist(),
        "plans": [np.round(X, 3).tolist() for X in sim.plans],
        "energy": [round(e, 4) for e in sim.energy],
        "solve_time_ms": [round(1e3 * s, 3) for s in sim.solve_time],
        "iterations": list(sim.iterations),
        "costs": [None if c is None else round(c, 4) for c in sim.costs],
        "status": list(sim.status),
        "ref_index": list(sim.ref_index),
        "solve_steps": list(sim.solve_steps),  # sample of each solve (re-plan interval > 1)
        "disturbance": np.round(np.array(sim.disturbance).reshape(-1, 2), 3).tolist(),
        "crash_point": sim.crash_point,
    }


def solver_metrics(sim: Simulation) -> dict:
    """Solver statistics over the whole run (for the Solver info card)."""
    st = np.array(sim.solve_time) * 1e3
    it = np.array(sim.iterations)
    return {
        "solves": len(sim.solve_time),
        "mean_solve_ms": float(st.mean()) if len(st) else 0.0,
        "max_solve_ms": float(st.max()) if len(st) else 0.0,
        "total_solve_ms": float(st.sum()),
        "mean_iterations": float(it.mean()) if len(it) else 0.0,
        "max_iterations": int(it.max()) if len(it) else 0,
    }


def closed_loop_cost(sim: Simulation, Q, R, target, dt: float) -> float:
    """Cost of what actually happened, with the player's weights:
    sum over applied steps of dt * ( |x_k - x_ref|_Q^2 + |u_k|_R^2 ).
    target: one position, or one per applied step (e.g. the active waypoint)."""
    U = np.array(sim.u).reshape(-1, 2)
    if not len(U):
        return 0.0
    ref = np.broadcast_to(np.asarray(target, float).reshape(-1, 2), (len(U), 2))
    X = np.array(sim.x[:len(U)]) - np.hstack([ref, np.zeros((len(U), 2))])
    return float(dt * (np.einsum("ki,ij,kj->", X, Q, X) + np.einsum("ki,ij,kj->", U, R, U)))


def same_ratios_as_default(level: dict, knobs: dict, rel: float = 0.01) -> bool:
    """True if the knobs are the defaults all multiplied by one factor (!= 1)."""
    factors = [knobs[s["name"]] / s["default"] for s in level["knobs"]]
    f0 = factors[0]
    return abs(f0 - 1.0) > rel and all(abs(f / f0 - 1.0) < rel for f in factors)
