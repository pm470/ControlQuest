"""MPC controller around one compiled acados solver, plus a cache of solvers.

    cache = SolverCache(build_dir)
    mpc = cache.get(N=30, dt=0.1)          # compiled once per shape, then reused
    mpc.set_weights(Q, R, P)               # runtime: no recompilation
    mpc.set_bounds(x_lb, x_ub, u_lb, u_ub)
    mpc.set_model_gain(1.0)
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

from .model import NU, NX
from .ocp import build_ocp, shape_name

ACADOS_STATUS = {0: "success", 1: "NaN detected", 2: "max iterations reached",
                 3: "minimum step size", 4: "QP solver failure", 5: "ready"}


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
        for k in range(self.N + 1):
            self.solver.set(k, "p", np.array([g], dtype=float))

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
        message = (f"acados status {status} ({ACADOS_STATUS.get(status, 'unknown')})"
                   if status != 0 else self._check(x0, X, U))
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
        return ""


class SolverCache:
    """One compiled MPCController per problem shape, built on first use."""

    def __init__(self, build_dir: Path):
        self.build_dir = Path(build_dir)
        self._solvers: dict[tuple, MPCController] = {}
        self._lock = threading.Lock()

    def get(self, N: int, dt: float) -> MPCController:
        key = (int(N), float(dt))
        with self._lock:
            if key not in self._solvers:
                t0 = time.time()
                print(f"[engine] building solver {shape_name(N)} (dt={dt}) ...", flush=True)
                self._solvers[key] = MPCController(int(N), float(dt), self.build_dir)
                print(f"[engine] solver {shape_name(N)} ready in {time.time() - t0:.1f} s", flush=True)
            return self._solvers[key]
