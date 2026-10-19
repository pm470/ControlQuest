"""Lightweight checks of model, cost scaling and closed loop.  python verify.py"""

import numpy as np

from config import PointMassConfig
from controller import PointMassMPC
from point_mass_model import casadi_step_function, plant_step
from obstacles import ellipse_from_corners
from simulation import block_intrusion, constraint_violations, run_closed_loop

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
        x = rng.uniform(cfg.x_lb, cfg.x_ub)
        u = rng.uniform(cfg.u_lb, cfg.u_ub)
        err = max(err, np.max(np.abs(np.array(f(x, u)).ravel() - plant_step(x, u, cfg.dt))))
    check("CasADi f_discrete == NumPy plant_step (100 random samples)", err < 1e-12, f"max err {err:.1e}")

    # 2. ellipses: smallest one around a rectangle is known in closed form
    #    (semi-axes = half sides * sqrt(2)); every ellipse contains its corners
    rect = ellipse_from_corners([(25, 20), (32, 20), (25, 32), (32, 32)])
    ax_err = np.max(np.abs(np.sort(rect.semi_axes) - np.sort([3.5, 6.0]) * np.sqrt(2)))
    check("rectangle -> minimum enclosing ellipse (closed form)", ax_err < 1e-6
          and np.allclose(rect.center, [28.5, 26]), f"semi-axes {rect.semi_axes.round(4)}")
    h_max = max(e.h(e.corners).max() for e in cfg.obstacles)
    check("every obstacle ellipse contains its 4 corners", h_max <= 1 + 1e-9, f"max h(corner) {h_max:.4f}")

    # 3. config validation rejects bad input
    for bad in [dict(dt=0.0), dict(N=0), dict(x_start=np.array([-1.0, 1, 0, 0])),
                dict(x_target=np.array([5.0, 51, 0, 0])), dict(x_start=np.array([1.0, 1, 3, 0])),
                dict(x_target=np.array([28.0, 26, 0, 0])),
                dict(obstacle_corners=[np.array([(0, 0), (1, 1), (2, 2), (3, 3)])])]:
        try:
            cfg.with_changes(**bad)
            check(f"reject {bad}", False)
        except ValueError as e:
            check(f"reject {list(bad)[0]}", True, str(e)[:90])

    # Build the solver once; all scenarios below only change runtime data.
    mpc = PointMassMPC(cfg)

    # 4. acados cost matches intended J (0.5 LS convention + dt scaling, no double dt)
    sol = mpc.solve(cfg.x_start)
    J_acados = mpc.solver.get_cost()
    J_ref = objective(cfg, sol.X, sol.U, cfg.x_target)
    check("acados cost == intended J", abs(J_acados - J_ref) < 1e-6 * max(1, J_ref),
          f"acados {J_acados:.6f}, J {J_ref:.6f}")
    pred_err = max(np.max(np.abs(sol.X[k + 1] - plant_step(sol.X[k], sol.U[k], cfg.dt))) for k in range(cfg.N))
    check("acados prediction consistent with NumPy plant", pred_err < 1e-9, f"max err {pred_err:.1e}")

    scenarios = [
        ("default (5,5)->(40,35)", cfg.x_start, cfg.x_target),
        ("start == target, at rest", np.array([20.0, 40, 0, 0]), np.array([20.0, 40, 0, 0])),
        ("negative directions (45,40)->(10,2.5)", np.array([45.0, 40, 0, 0]), np.array([10.0, 2.5, 0, 0])),
        ("target on workspace corner (40,35)->(0,50)", np.array([40.0, 35, 0, 0]), np.array([0.0, 50, 0, 0])),
        ("target hidden behind block (20,24)->(40,28)", np.array([20.0, 24, 0, 0]), np.array([40.0, 28, 0, 0])),
        ("on the block's symmetry axis (15,26)->(42,26)", np.array([15.0, 26, 0, 0]), np.array([42.0, 26, 0, 0])),
    ]
    for name, xs, xt in scenarios:
        res = run_closed_loop(cfg, mpc, x_start=xs, x_target=xt)
        viol = constraint_violations(cfg, res)
        check(f"{name}: converged", res.converged and not res.failed,
              f"{res.message}; {len(res.U)} steps, err {res.pos_err[-1]:.3f} m, speed {res.speed[-1]:.3f} m/s")
        check(f"{name}: bounds + ellipses respected (tol {cfg.bound_tol:g})", not viol, "; ".join(viol))
        intr = block_intrusion(cfg, res)
        check(f"{name}: blocks not entered, also between samples", not intr, "; ".join(intr))
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
