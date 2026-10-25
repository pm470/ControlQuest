"""Closed-loop simulation: the "real" ball driven by the MPC, one sample at a time.

    measure x -> solve the OCP -> apply only u0 -> the plant moves the ball by dt -> repeat

The plant (the real ball) is separate from the controller's model on purpose:
later levels give it a different actuator gain or add wind, and the controller
does not know. A level adds its own rules (e.g. a battery) through `stop_rule`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .controller import MPCController


def plant_step(x: np.ndarray, u: np.ndarray, dt: float, gain: float = 1.0,
               disturbance: Optional[np.ndarray] = None) -> np.ndarray:
    """The real ball (exact double integrator). disturbance = extra acceleration, e.g. wind."""
    a = gain * np.asarray(u, dtype=float)
    if disturbance is not None:
        a = a + disturbance
    p, v = x[:2], x[2:]
    return np.concatenate([p + dt * v + 0.5 * dt**2 * a, v + dt * a])


@dataclass
class Simulation:
    """Everything that happened in one run (n = number of applied inputs)."""

    t: list = field(default_factory=list)  # n+1 times [s]
    x: list = field(default_factory=list)  # n+1 states
    u: list = field(default_factory=list)  # n applied inputs
    plans: list = field(default_factory=list)  # one plan (N+1, 4) per solve, plan k at t[k]
    energy: list = field(default_factory=lambda: [0.0])  # n+1 cumulative sum dt*|u|^2
    # per solve (same length as plans: n, or n+1 if the last solve failed)
    solve_time: list = field(default_factory=list)  # [s]
    iterations: list = field(default_factory=list)  # SQP iterations
    costs: list = field(default_factory=list)  # optimal OCP cost J* (None if failed)
    status: list = field(default_factory=list)  # acados status (0 = success)
    outcome: str = ""  # see END_REASONS
    detail: str = ""  # e.g. the acados status for a controller failure


END_REASONS = ("success", "time_out", "controller_failure", "crash_wall")


def simulate(mpc: MPCController, x0, target, *, dt: float, t_limit: float,
             p_min, p_max, pos_tol: float = 0.05, speed_tol: float = 0.05,
             plant_gain: float = 1.0,
             stop_rule: Optional[Callable[[Simulation], Optional[str]]] = None) -> Simulation:
    """Run until success, time out, controller failure, leaving the workspace,
    or until stop_rule(sim) returns an outcome name (e.g. "battery_empty")."""
    sim = Simulation()
    x = np.asarray(x0, dtype=float)
    target = np.asarray(target, dtype=float)
    p_min, p_max = np.asarray(p_min, float), np.asarray(p_max, float)
    sim.t.append(0.0)
    sim.x.append(x)
    mpc.reset()
    n_max = int(round(t_limit / dt))

    for k in range(n_max + 1):
        if np.linalg.norm(x[:2] - target[:2]) < pos_tol and np.linalg.norm(x[2:]) < speed_tol:
            sim.outcome = "success"
            break
        if k == n_max:
            sim.outcome = "time_out"
            break

        plan = mpc.solve(x)
        sim.plans.append(plan.X)  # kept even if it failed (shown in the replay)
        sim.solve_time.append(plan.solve_time)
        sim.iterations.append(plan.iterations)
        sim.costs.append(plan.cost)
        sim.status.append(plan.status)
        if not plan.ok:
            sim.outcome, sim.detail = "controller_failure", plan.message
            break

        u = plan.u0
        x = plant_step(x, u, dt, gain=plant_gain)
        sim.u.append(u)
        sim.t.append((k + 1) * dt)
        sim.x.append(x)
        sim.energy.append(sim.energy[-1] + dt * float(u @ u))

        if np.any(x[:2] < p_min - 1e-6) or np.any(x[:2] > p_max + 1e-6):
            sim.outcome = "crash_wall"
            break
        if stop_rule is not None:
            reason = stop_rule(sim)
            if reason:
                sim.outcome = reason
                break
    return sim
