"""MPC controller around one compiled acados solver, plus a cache of solvers.

    cache = SolverCache(build_dir)
    mpc = cache.get(N=30, dt=0.1)          # compiled once per shape, then reused
    mpc.set_weights(Q, R, P)               # runtime: no recompilation
    mpc.set_bounds(x_lb, x_ub, u_lb, u_ub)
    mpc.set_model_gain(1.0)
    mpc.set_obstacles([(c, E), ...])       # ellipses (p-c)^T E (p-c) >= 1, up to MAX_OBSTACLES
    mpc.set_damping(1e-2)                  # Levenberg-Marquardt (use with obstacles)
    mpc.set_target(x_ref)
    mpc.reset()                            # forget the warm start (new run)
    plan = mpc.solve(x)                    # plan.u0 is applied, plan.X is drawn
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from acados_template import AcadosOcpSolver

from .model import MAX_OBSTACLES, NU, NX, OBSTACLE_PARAMS, UNUSED_SLOT
from .ocp import build_ocp, shape_name

ACADOS_STATUS = {0: "success", 1: "NaN detected", 2: "max iterations reached",
                 3: "minimum step size", 4: "QP solver failure", 5: "ready"}
MAX_ITER = 2  # acados status: SQP stopped at the iteration limit (iterate may still be usable)
H_TOL = 0.02  # a plan may dip this far into an ellipse (h >= 1 - H_TOL; ~2 cm, soft constraints)


@dataclass
class Plan:
    """One MPC solve."""

    u0: np.ndarray  # first input: the only one applied
    X: np.ndarray  # predicted states (N+1, 4): the dashed plan in the game
    U: np.ndarray  # predicted inputs (N, 2)
    status: int  # acados status (0 = success)
    ok: bool  # solved, finite and within bounds
    message: str
    solve_time: float  # [s], acados time_tot
    iterations: int  # SQP iterations
    cost: float | None  # optimal OCP cost J* of this solve (None if the solve failed)


class MPCController:
    def __init__(self, N: int, dt: float, build_dir: Path, bound_tol: float = 1e-5):
        self.N, self.dt, self.bound_tol = N, dt, bound_tol
        ocp = build_ocp(N, dt, build_dir)
        self.solver = AcadosOcpSolver(ocp, verbose=False)  # code generation + compilation
        self._x_lb = self._x_ub = self._u_lb = self._u_ub = None
        self._gain = 1.0
        self._slots = list(UNUSED_SLOT) * MAX_OBSTACLES
        self.reset()

    # --- runtime configuration (no recompilation) ------------------------------------
    def set_weights(self, Q, R, P) -> None:
        W = np.zeros((NX + NU, NX + NU))
        W[:NX, :NX], W[NX:, NX:] = Q, R
        for k in range(self.N):
            self.solver.cost_set(k, "W", 2.0 * W)
        self.solver.cost_set(self.N, "W", 2.0 * np.asarray(P, dtype=float))

    def set_bounds(self, x_lb, x_ub, u_lb, u_ub) -> None:
        self._x_lb, self._x_ub = np.asarray(x_lb, float), np.asarray(x_ub, float)
        self._u_lb, self._u_ub = np.asarray(u_lb, float), np.asarray(u_ub, float)
        for k in range(self.N):
            self.solver.constraints_set(k, "lbu", self._u_lb)
            self.solver.constraints_set(k, "ubu", self._u_ub)
        for k in range(1, self.N + 1):
            self.solver.constraints_set(k, "lbx", self._x_lb)
            self.solver.constraints_set(k, "ubx", self._x_ub)

    def set_model_gain(self, g: float) -> None:
        self._gain = float(g)
        self._set_params()

    def set_obstacles(self, ellipses) -> None:
        """Obstacle ellipses as (center (2,), E (2, 2)); unused slots are moved off the map."""
        ellipses = list(ellipses)
        if len(ellipses) > MAX_OBSTACLES:
            raise ValueError(f"at most {MAX_OBSTACLES} obstacles, got {len(ellipses)}")
        slots = []
        for c, E in ellipses:
            slots += [float(c[0]), float(c[1]), float(E[0][0]), float(E[0][1]), float(E[1][1])]
        self._slots = slots + list(UNUSED_SLOT) * (MAX_OBSTACLES - len(ellipses))
        self._set_params()

    def set_damping(self, lm: float) -> None:
        """Levenberg-Marquardt term added to the SQP Hessian (0 = plain Gauss-Newton)."""
        self.solver.options_set("levenberg_marquardt", float(lm))

    def _set_params(self) -> None:
        p = np.array([self._gain, *self._slots], dtype=float)
        for k in range(self.N + 1):
            self.solver.set(k, "p", p)

    def set_target(self, x_ref) -> None:
        x_ref = np.asarray(x_ref, dtype=float)
        yref = np.concatenate([x_ref, np.zeros(NU)])
        for k in range(self.N):
            self.solver.set(k, "yref", yref)
        self.solver.set(self.N, "yref", x_ref)

    def reset(self) -> None:
        """Forget the previous solution (call at the start of every run)."""
        self._X_prev = None
        self._U_prev = None

    # --- solving ----------------------------------------------------------------------
    def solve(self, x0) -> Plan:
        x0 = np.asarray(x0, dtype=float)
        N = self.N
        self.solver.set(0, "lbx", x0)
        self.solver.set(0, "ubx", x0)
        self._initial_guess(x0)

        status = self.solver.solve()
        X = np.array([self.solver.get(k, "x") for k in range(N + 1)])
        U = np.array([self.solver.get(k, "u") for k in range(N)])
        # With obstacles SQP sometimes cycles near an ellipse tip and stops at the iteration
        # limit. The last iterate is still used if it is a valid plan (finite, within the
        # bounds, outside every ellipse): suboptimal, but safe. The status stays visible.
        message = (f"acados status {status} ({ACADOS_STATUS.get(status, 'unknown')})"
                   if status not in (0, MAX_ITER) else self._check(x0, X, U))
        if status == MAX_ITER and message:
            message = f"acados status {status} ({ACADOS_STATUS[MAX_ITER]}): {message}"
        ok = message == ""
        cost = float(self.solver.get_cost()) if ok else None
        if ok:
            self._X_prev, self._U_prev = X, U
        else:
            self.reset()
        return Plan(u0=U[0].copy(), X=X, U=U, status=int(status), ok=ok, message=message or "ok",
                    solve_time=float(self.solver.get_stats("time_tot")),
                    iterations=int(self.solver.get_stats("sqp_iter")), cost=cost)

    def _initial_guess(self, x0: np.ndarray) -> None:
        """Warm start: shift the previous plan by one step (or stay at x0 the first time)."""
        if self._X_prev is None:
            X, U = np.tile(x0, (self.N + 1, 1)), np.zeros((self.N, NU))
        else:
            X = np.vstack([self._X_prev[1:], self._X_prev[-1:]])
            U = np.vstack([self._U_prev[1:], self._U_prev[-1:]])
            X[0] = x0
        for k in range(self.N):
            self.solver.set(k, "x", X[k])
            self.solver.set(k, "u", U[k])
        self.solver.set(self.N, "x", X[self.N])

    def _check(self, x0, X, U) -> str:
        """'' if the plan is finite and within bounds, otherwise the reason."""
        tol = self.bound_tol
        if not (np.all(np.isfinite(X)) and np.all(np.isfinite(U))):
            return "plan contains non-finite values"
        if self._x_lb is not None:
            vx = np.maximum(self._x_lb - X[1:], X[1:] - self._x_ub).max()
            vu = np.maximum(self._u_lb - U, U - self._u_ub).max()
            if vx > tol or vu > tol:
                return f"plan violates bounds (state {vx:.1e}, input {vu:.1e})"
        h_min = self._min_obstacle_h(X[1:])
        if h_min < 1.0 - H_TOL:
            return f"plan enters an obstacle ellipse (h = {h_min:.3f} < 1)"
        return ""

    def _min_obstacle_h(self, X) -> float:
        """Smallest (p - c)^T E (p - c) over the plan's positions and the obstacle slots."""
        h_min = np.inf
        for j in range(MAX_OBSTACLES):
            cx, cy, e11, e12, e22 = self._slots[j * OBSTACLE_PARAMS:(j + 1) * OBSTACLE_PARAMS]
            d = X[:, :2] - [cx, cy]
            h = e11 * d[:, 0] ** 2 + 2 * e12 * d[:, 0] * d[:, 1] + e22 * d[:, 1] ** 2
            h_min = min(h_min, float(h.min()))
        return h_min


class SolverCache:
    """One compiled MPCController per problem shape, built on first use."""

    def __init__(self, build_dir: Path):
        self.build_dir = Path(build_dir)
        self._solvers: dict[tuple, MPCController] = {}
        self._lock = threading.Lock()

    def has(self, N: int, dt: float) -> bool:
        """True if the solver for this shape is already compiled (get() is then instant)."""
        return (int(N), float(dt)) in self._solvers

    def get(self, N: int, dt: float) -> MPCController:
        key = (int(N), float(dt))
        with self._lock:
            if key not in self._solvers:
                t0 = time.time()
                print(f"[engine] building solver {shape_name(N)} (dt={dt}) ...", flush=True)
                self._solvers[key] = MPCController(int(N), float(dt), self.build_dir)
                print(f"[engine] solver {shape_name(N)} ready in {time.time() - t0:.1f} s", flush=True)
            return self._solvers[key]
