"""Receding-horizon MPC controller for the 2D point mass (no plotting here)."""

import os
from dataclasses import dataclass

import numpy as np
from acados_template import AcadosOcpSolver

from config import PointMassConfig
from point_mass_model import plant_step
from setup_ocp import setup_ocp

# acados return codes, see acados/utils/types.h
ACADOS_STATUS = {0: "success", 1: "NaN detected", 2: "max iterations reached",
                 3: "minimum step size", 4: "QP solver failure", 5: "ready"}


@dataclass
class MPCSolution:
    u0: np.ndarray  # first control input -> the only one applied to the plant
    X: np.ndarray  # predicted states (N+1, 4)
    U: np.ndarray  # predicted controls (N, 2)
    status: int  # acados status (0 = success)
    solve_time: float  # [s], acados 'time_tot' (excludes code generation/compilation)
    sqp_iter: int
    ok: bool  # status == 0, finite, and within bounds
    message: str


class PointMassMPC:
    """Builds the acados solver ONCE; then solve(x) can be called repeatedly.

    Changing x0 and the target only updates numerical data inside the existing
    solver. Changing N, dt, or the model requires constructing a new controller
    (i.e. new generated code).
    """

    def __init__(self, cfg: PointMassConfig, verbose: bool = False):
        cfg.validate()
        self.cfg = cfg
        self.N = cfg.N
        self.ocp = setup_ocp(cfg)
        os.makedirs(os.path.dirname(self.ocp.code_gen_opts.json_file), exist_ok=True)
        # --- solver creation: code generation + C compilation (slow, once) ---
        self.solver = AcadosOcpSolver(self.ocp, verbose=verbose)
        self.x_target = cfg.x_target.copy()
        self.set_target(self.x_target)
        self.reset()

    def reset(self) -> None:
        """Forget the warm start (next solve uses the basic initial guess)."""
        self._X_prev = None
        self._U_prev = None

    def set_target(self, x_target) -> None:
        """Set references on every stage 0..N-1 and on the terminal stage N."""
        self.x_target = self.cfg.check_state(x_target, "x_target")
        yref = np.concatenate([self.x_target, np.zeros(2)])  # [x_target; u_ref = 0]
        for k in range(self.N):
            self.solver.set(k, "yref", yref)
        self.solver.set(self.N, "yref", self.x_target)

    def _set_initial_guess(self, x0: np.ndarray) -> None:
        N, dt = self.N, self.cfg.dt
        if self._X_prev is None:
            # basic guess: stay at x0 with zero acceleration
            X = np.tile(x0, (N + 1, 1))
            U = np.zeros((N, 2))
        else:
            # warm start: shift previous solution by one step, repeat the last
            # control and propagate the final state with the model.
            U = np.vstack([self._U_prev[1:], self._U_prev[-1:]])
            X = np.vstack([self._X_prev[1:], self._X_prev[-1:]])
            X[0] = x0
            X[-1] = plant_step(X[-2], U[-1], dt)
        for k in range(N):
            self.solver.set(k, "x", X[k])
            self.solver.set(k, "u", U[k])
        self.solver.set(N, "x", X[N])

    def _check(self, x0, X, U) -> str:
        """Return '' if the solution is finite and within bounds, else a reason."""
        tol = self.cfg.bound_tol
        if not (np.all(np.isfinite(X)) and np.all(np.isfinite(U))):
            return "solution contains non-finite values"
        if np.max(np.abs(X[0] - x0)) > tol:
            return f"x_0 deviates from the measured state by {np.max(np.abs(X[0] - x0)):.2e}"
        vx = np.maximum(self.cfg.x_lb - X, X - self.cfg.x_ub).max()
        vu = np.maximum(self.cfg.u_lb - U, U - self.cfg.u_ub).max()
        if vx > tol or vu > tol:
            return f"bound violation (state {vx:.2e}, control {vu:.2e}) above tol {tol:g}"
        return ""

    def solve(self, x0) -> MPCSolution:
        """Solve the OCP for the current state x0 (does not raise on solver failure)."""
        x0 = self.cfg.check_state(x0, "current state")
        N = self.N

        # Initial-state constraint: fix all 4 components of x_0 to the measurement
        self.solver.set(0, "lbx", x0)
        self.solver.set(0, "ubx", x0)
        self._set_initial_guess(x0)

        status = self.solver.solve()
        solve_time = float(self.solver.get_stats("time_tot"))
        sqp_iter = int(self.solver.get_stats("sqp_iter"))

        X = np.array([self.solver.get(k, "x") for k in range(N + 1)])
        U = np.array([self.solver.get(k, "u") for k in range(N)])

        if status != 0:
            msg = f"acados status {status} ({ACADOS_STATUS.get(status, 'unknown')})"
        else:
            msg = self._check(x0, X, U)
        ok = msg == ""
        if ok:
            self._X_prev, self._U_prev = X, U
        else:
            self.reset()
        return MPCSolution(u0=U[0].copy(), X=X, U=U, status=status, solve_time=solve_time,
                           sqp_iter=sqp_iter, ok=ok, message=msg or "ok")
