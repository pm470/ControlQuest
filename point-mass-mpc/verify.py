"""Lightweight checks of model, cost scaling and closed loop.  python verify.py"""

import numpy as np

from config import PointMassConfig
from controller import PointMassMPC
from point_mass_model import casadi_step_function, plant_step
from simulation import constraint_violations, run_closed_loop

results = []


def check(name, cond, info=""):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info else ""))


def objective(cfg, X, U, xt):
    """Intended J, evaluated independently of acados."""
    J = sum(cfg.dt * ((X[k] - xt) @ cfg.Q @ (X[k] - xt) + U[k] @ cfg.R @ U[k]) for k in range(cfg.N))
    return J + (X[-1] - xt) @ cfg.P @ (X[-1] - xt)


def main():
    cfg = PointMassConfig()
    cfg.validate()

    # 1. CasADi dynamics vs. independent NumPy plant
    f = casadi_step_function(cfg.dt)
    rng = np.random.default_rng(0)
    err = 0.0
    for _ in range(100):
        x = rng.uniform([0, 0, -2, -2], [10, 10, 2, 2])
        u = rng.uniform(-2, 2, 2)
        err = max(err, np.max(np.abs(np.array(f(x, u)).ravel() - plant_step(x, u, cfg.dt))))
    check("CasADi f_discrete == NumPy plant_step (100 random samples)", err < 1e-12, f"max err {err:.1e}")

    # 2. config validation rejects bad input
    for bad in [dict(dt=0.0), dict(N=0), dict(x_start=np.array([-1.0, 1, 0, 0])),
                dict(x_target=np.array([5.0, 11, 0, 0])), dict(x_start=np.array([1.0, 1, 3, 0]))]:
        try:
            cfg.with_changes(**bad)
            check(f"reject {bad}", False)
        except ValueError as e:
            check(f"reject {list(bad)[0]}", True, str(e))

    # Build the solver once; all scenarios below only change runtime data.
    mpc = PointMassMPC(cfg)

    # 3. acados cost matches intended J (0.5 LS convention + dt scaling, no double dt)
    sol = mpc.solve(cfg.x_start)
    J_acados = mpc.solver.get_cost()
    J_ref = objective(cfg, sol.X, sol.U, cfg.x_target)
    check("acados cost == intended J", abs(J_acados - J_ref) < 1e-6 * max(1, J_ref),
          f"acados {J_acados:.6f}, J {J_ref:.6f}")
    pred_err = max(np.max(np.abs(sol.X[k + 1] - plant_step(sol.X[k], sol.U[k], cfg.dt))) for k in range(cfg.N))
    check("acados prediction consistent with NumPy plant", pred_err < 1e-9, f"max err {pred_err:.1e}")

    scenarios = [
        ("default (1,1)->(8,7)", cfg.x_start, cfg.x_target),
        ("start == target, at rest", np.array([5.0, 5, 0, 0]), np.array([5.0, 5, 0, 0])),
        ("negative directions (9,8)->(2,0.5)", np.array([9.0, 8, 0, 0]), np.array([2.0, 0.5, 0, 0])),
        ("target on workspace corner (8,7)->(0,10)", np.array([8.0, 7, 0, 0]), np.array([0.0, 10, 0, 0])),
    ]
    for name, xs, xt in scenarios:
        res = run_closed_loop(cfg, mpc, x_start=xs, x_target=xt)
        viol = constraint_violations(cfg, res)
        check(f"{name}: converged", res.converged and not res.failed,
              f"{res.message}; {len(res.U)} steps, err {res.pos_err[-1]:.3f} m, speed {res.speed[-1]:.3f} m/s")
        check(f"{name}: bounds respected (tol {cfg.bound_tol:g})", not viol, "; ".join(viol))
        if name.startswith("start == target"):
            # Convergence is checked before the first solve, so also solve once
            # explicitly and verify the optimal input/prediction is ~zero.
            s = mpc.solve(xs)
            check("start == target: optimal plan stays at rest",
                  s.ok and np.max(np.abs(s.U)) < 1e-6 and np.max(np.abs(s.X - xs)) < 1e-6,
                  f"max|U| {np.max(np.abs(s.U)):.1e}, max|X-x0| {np.max(np.abs(s.X - xs)):.1e}")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
