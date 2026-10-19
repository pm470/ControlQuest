"""Closed-loop (receding-horizon) simulation: no plotting here."""

from dataclasses import dataclass, field

import numpy as np

from config import PointMassConfig
from controller import PointMassMPC
from point_mass_model import plant_step


@dataclass
class ClosedLoopResult:
    t: np.ndarray  # (n+1,) time of each logged state
    X: np.ndarray  # (n+1, 4) actual (plant) states
    U: np.ndarray  # (n, 2) applied accelerations
    pos_err: np.ndarray  # (n+1,) ||p - p_target||
    speed: np.ndarray  # (n+1,) ||v||
    status: np.ndarray  # (n,) acados status per MPC step
    solve_time: np.ndarray  # (n,) [s]
    sqp_iter: np.ndarray  # (n,) SQP iterations per MPC step
    predictions: list = field(default_factory=list)  # predicted X (N+1, 4) per step
    converged: bool = False
    failed: bool = False
    message: str = ""
    x_target: np.ndarray = None
    obstacles: list = field(default_factory=list)  # Ellipse objects used by the solver


def run_closed_loop(cfg: PointMassConfig, mpc: PointMassMPC = None,
                    x_start=None, x_target=None) -> ClosedLoopResult:
    """Run the MPC loop until the target is reached at rest, or t_sim_max.

    An existing controller can be passed in to avoid recompiling, and start /
    target can be overridden per run (they are runtime data, not code).
    """
    if mpc is None:
        mpc = PointMassMPC(cfg)
    x = cfg.check_free(cfg.x_start if x_start is None else x_start, "x_start", mpc.obstacles)
    if x_target is not None:
        mpc.set_target(x_target)
    xt = mpc.x_target
    mpc.reset()

    n_max = int(round(cfg.t_sim_max / cfg.dt))
    X, U, status, times, iters, preds = [x], [], [], [], [], []
    converged, failed, message = False, False, ""

    for i in range(n_max + 1):
        # 1. current simulated state; stop if at the target and at rest
        if (np.linalg.norm(x[:2] - xt[:2]) < cfg.pos_tol
                and np.linalg.norm(x[2:]) < cfg.speed_tol):
            converged = True
            message = f"target reached at t = {i * cfg.dt:.2f} s"
            break
        if i == n_max:
            message = f"no convergence within t_sim_max = {cfg.t_sim_max:g} s"
            break

        # 2.-6. fix x_0, (references already set), solve, check, extract
        sol = mpc.solve(x)
        status.append(sol.status)
        times.append(sol.solve_time)
        iters.append(sol.sqp_iter)
        preds.append(sol.X)
        if not sol.ok:
            failed = True
            message = f"MPC solve failed at step {i} (t = {i * cfg.dt:.2f} s): {sol.message}"
            break

        # 7.-8. receding horizon: apply ONLY the first input, advance plant by dt
        u = sol.u0
        x = plant_step(x, u, cfg.dt)

        # 9. log and repeat (re-solve from the new state)
        U.append(u)
        X.append(x)

    X = np.array(X)
    return ClosedLoopResult(
        t=cfg.dt * np.arange(len(X)),
        X=X,
        U=np.array(U).reshape(-1, 2),
        pos_err=np.linalg.norm(X[:, :2] - xt[:2], axis=1),
        speed=np.linalg.norm(X[:, 2:], axis=1),
        status=np.array(status, dtype=int),
        solve_time=np.array(times),
        sqp_iter=np.array(iters, dtype=int),
        predictions=preds,
        converged=converged,
        failed=failed,
        message=message,
        x_target=xt.copy(),
        obstacles=mpc.obstacles,
    )


def constraint_violations(cfg: PointMassConfig, res: ClosedLoopResult) -> list:
    """List logged states/controls outside the bounds by more than bound_tol."""
    out = []
    names = ["px", "py", "vx", "vy"]
    for j in range(4):
        lo = cfg.x_lb[j] - res.X[:, j]
        hi = res.X[:, j] - cfg.x_ub[j]
        v = max(lo.max(), hi.max())
        if v > cfg.bound_tol:
            out.append(f"{names[j]} exceeds bounds by {v:.2e}")
    for j, n in enumerate(["ax", "ay"]):
        if len(res.U):
            v = max((cfg.u_lb[j] - res.U[:, j]).max(), (res.U[:, j] - cfg.u_ub[j]).max())
            if v > cfg.bound_tol:
                out.append(f"{n} exceeds bounds by {v:.2e}")
    for j, ell in enumerate(res.obstacles):
        h_min = ell.h(res.X).min()
        if h_min < 1.0 - cfg.bound_tol:
            out.append(f"obstacle {j} ellipse entered (min h = {h_min:.4f} < 1)")
    return out


def block_intrusion(cfg: PointMassConfig, res: ClosedLoopResult, n_sub=20) -> list:
    """Check the continuous path BETWEEN samples against the true blocks.

    Constraints only hold at the sampling instants; here the exact motion
    p(tau) = p + tau v + 0.5 tau^2 a, tau in [0, dt], is checked on n_sub points
    per interval. Returns one message per block that is entered.
    """
    tau = np.linspace(0.0, cfg.dt, n_sub + 1)[:, None, None]
    P = res.X[None, :-1, :2] + tau * res.X[None, :-1, 2:] + 0.5 * tau**2 * res.U[None]
    out = []
    for j, ell in enumerate(res.obstacles):
        depth = ell.block_depth(P.reshape(-1, 2)).max() if len(res.U) else -np.inf
        if depth > cfg.bound_tol:
            out.append(f"block {j} entered by {depth:.3f} m between samples")
    return out


def summary(cfg: PointMassConfig, res: ClosedLoopResult) -> str:
    viol = constraint_violations(cfg, res)
    intr = block_intrusion(cfg, res)
    st = res.solve_time * 1e3
    lines = [
        f"target reached:      {'YES' if res.converged else 'NO'} ({res.message})",
        f"MPC steps:           {len(res.U)}   simulated duration: {res.t[-1]:.2f} s",
        f"final position error {res.pos_err[-1]:.4f} m   final speed {res.speed[-1]:.4f} m/s",
        (f"solve time [ms]:     mean {st.mean():.3f}   max {st.max():.3f}"
         " (excludes code generation/compilation)") if len(st) else "solve time: no solves",
        (f"SQP iterations:      mean {res.sqp_iter.mean():.1f}   max {res.sqp_iter.max()}")
        if len(res.sqp_iter) else "SQP iterations: no solves",
        f"constraint check:    {'no violations' if not viol else '; '.join(viol)}"
        f" (tol {cfg.bound_tol:g}; bounds + obstacle ellipses at the samples)",
        f"blocks between samples: {'not entered' if not intr else '; '.join(intr)}",
    ]
    return "\n".join(lines)
