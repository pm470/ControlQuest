"""Helpers shared by all level rules: loading level files, knobs -> MPC settings,
configuring a controller, and turning a Simulation into the RunResult JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mpc.closed_loop import Simulation
from mpc.controller import MPCController, SolverCache

LEVEL_DATA_DIR = Path(__file__).resolve().parents[2] / "level_data"  # game/level_data


def load_level(level_id: str) -> dict:
    path = LEVEL_DATA_DIR / f"{level_id}.json"
    if not path.is_file():
        raise ValueError(f"unknown level '{level_id}' (no {path.name})")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def clean_knobs(level: dict, knobs: dict) -> dict:
    """Knob values from the request, clamped to their range; missing ones use defaults."""
    out = {}
    for spec in level["knobs"]:
        value = knobs.get(spec["name"], spec["default"])
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"knob {spec['name']} must be a number, got {value!r}") from None
        if not np.isfinite(value):
            raise ValueError(f"knob {spec['name']} must be finite")
        out[spec["name"]] = min(max(value, spec["min"]), spec["max"])
    unknown = set(knobs) - set(out)
    if unknown:
        raise ValueError(f"unknown knob(s) for this level: {sorted(unknown)}")
    return out


def weights(level: dict, knobs: dict):
    """Q = diag(q_p, q_p, q_v, q_v), R = r*I, P = terminal_factor * Q."""
    qp, qv, r = knobs["q_p"], knobs["q_v"], knobs["r"]
    Q = np.diag([qp, qp, qv, qv])
    return Q, r * np.eye(2), level["terminal_factor"] * Q


def configured_controller(cache: SolverCache, level: dict, knobs: dict,
                          model_gain: float = 1.0) -> MPCController:
    """Get the (cached) solver for this level's shape and load this run's numbers into it."""
    mpc = cache.get(level["N"], level["dt"])
    a, v = level["limits"]["a_max"], level["limits"]["v_max"]
    p_min, p_max = level["workspace"]["min"], level["workspace"]["max"]
    mpc.set_weights(*weights(level, knobs))
    mpc.set_bounds([*p_min, -v, -v], [*p_max, v, v], [-a, -a], [a, a])
    mpc.set_model_gain(model_gain)
    mpc.set_target([*level["target"], 0.0, 0.0])
    return mpc


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
    sum over applied steps of dt * ( |x_k - x_ref|_Q^2 + |u_k|_R^2 )."""
    x_ref = np.concatenate([np.asarray(target, float), [0.0, 0.0]])
    X = np.array(sim.x[:len(sim.u)]) - x_ref
    U = np.array(sim.u).reshape(-1, 2)
    if not len(U):
        return 0.0
    return float(dt * (np.einsum("ki,ij,kj->", X, Q, X) + np.einsum("ki,ij,kj->", U, R, U)))


def same_ratios_as_default(level: dict, knobs: dict, rel: float = 0.01) -> bool:
    """True if the knobs are the defaults all multiplied by one factor (!= 1)."""
    factors = [knobs[s["name"]] / s["default"] for s in level["knobs"]]
    f0 = factors[0]
    return abs(f0 - 1.0) > rel and all(abs(f / f0 - 1.0) < rel for f in factors)
