import matplotlib.pyplot as plt
import numpy as np

from config import PointMassConfig
from simulation import ClosedLoopResult


def plot_results(cfg: PointMassConfig, res: ClosedLoopResult, fig_filename=None,
                 show_plot=False, n_predictions=5):
    fig = plt.figure(figsize=(14, 8), layout="constrained")
    gs = fig.add_gridspec(3, 3)
    ax_xy = fig.add_subplot(gs[:, 0])
    ax_p = fig.add_subplot(gs[0, 1])
    ax_v = fig.add_subplot(gs[1, 1], sharex=ax_p)
    ax_a = fig.add_subplot(gs[2, 1], sharex=ax_p)
    ax_t = fig.add_subplot(gs[:, 2])
    xt = res.x_target

    # 1. x-y trajectory with a few MPC predictions
    (x0, y0), (x1, y1) = cfg.p_min, cfg.p_max
    ax_xy.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ls="--", color="k",
                                  alpha=0.4, label="workspace"))
    # obstacles: true block (filled) and the ellipse the solver avoids (dashed)
    for j, ell in enumerate(res.obstacles):
        ax_xy.add_patch(plt.Polygon(ell.polygon(), closed=True, color="0.45", alpha=0.6,
                                    label="obstacle (block)" if j == 0 else None))
        b = ell.boundary()
        ax_xy.plot(b[:, 0], b[:, 1], "--", color="0.3", lw=1,
                   label="ellipse used by the solver" if j == 0 else None)
    ax_xy.plot(res.X[:, 0], res.X[:, 1], "-", color="C0", lw=4, alpha=0.5, label="executed")
    # predictions drawn on top: without model mismatch they lie close to the
    # executed path, but each one reaches T = N*dt ahead (end marker "x")
    n_pred = len(res.predictions)
    for j, i in enumerate(np.unique(np.linspace(0, n_pred - 1, min(n_predictions, n_pred)).astype(int))):
        Xp = res.predictions[i]
        ax_xy.plot(Xp[:, 0], Xp[:, 1], "--", color="C1", lw=1.2,
                   label=f"MPC prediction (T = {cfg.T:g} s)" if j == 0 else None)
        ax_xy.plot(Xp[0, 0], Xp[0, 1], "o", color="C1", ms=4)
        ax_xy.plot(Xp[-1, 0], Xp[-1, 1], "x", color="C1", ms=7)
    ax_xy.plot(*res.X[0, :2], "o", color="C2", ms=9, label="start")
    ax_xy.plot(*xt[:2], "*", color="C3", ms=14, label="target")
    ax_xy.set_aspect("equal")
    ax_xy.set_xlim(x0 - 0.5, x1 + 0.5)
    ax_xy.set_ylim(y0 - 0.5, y1 + 0.5)
    ax_xy.set_xlabel("$p_x$ [m]")
    ax_xy.set_ylabel("$p_y$ [m]")
    ax_xy.set_title("trajectory (x-y)")
    ax_xy.legend(loc="best", fontsize=8)
    ax_xy.grid(alpha=0.3)

    t, tu = res.t, res.t[:-1]
    # 2. positions with target values
    for j, (c, n) in enumerate([("C0", "$p_x$"), ("C1", "$p_y$")]):
        ax_p.plot(t, res.X[:, j], color=c, label=n)
        ax_p.axhline(xt[j], color=c, ls="--", alpha=0.5)
    ax_p.set_ylabel("position [m]")
    ax_p.legend(fontsize=8)

    # 3. velocities with bounds
    for j, (c, n) in enumerate([("C0", "$v_x$"), ("C1", "$v_y$")]):
        ax_v.plot(t, res.X[:, 2 + j], color=c, label=n)
    for b in (-cfg.v_max, cfg.v_max):
        ax_v.axhline(b, color="k", ls="--", alpha=0.4)
    ax_v.set_ylabel("velocity [m/s]")
    ax_v.legend(fontsize=8)

    # 4. applied accelerations (piecewise constant) with bounds
    if len(res.U):
        for j, (c, n) in enumerate([("C0", "$a_x$"), ("C1", "$a_y$")]):
            ax_a.step(np.append(tu, t[-1]), np.append(res.U[:, j], res.U[-1, j]),
                      where="post", color=c, label=n)
    for b in (-cfg.a_max, cfg.a_max):
        ax_a.axhline(b, color="k", ls="--", alpha=0.4)
    ax_a.set_ylabel("acceleration [m/s$^2$]")
    ax_a.set_xlabel("$t$ [s]")
    ax_a.legend(fontsize=8)
    for ax in (ax_p, ax_v, ax_a):
        ax.grid(alpha=0.3)

    # 5. solve time and SQP iterations per MPC iteration
    k = np.arange(len(res.solve_time))
    ax_t.plot(k, res.solve_time * 1e3, ".-", color="C0", label="solve time")
    ax_t.set_xlabel("MPC iteration")
    ax_t.set_ylabel("solve time [ms]", color="C0")
    ax_t.set_title("acados solve time (time_tot) and SQP iterations")
    ax_t.grid(alpha=0.3)
    ax_it = ax_t.twinx()
    ax_it.step(k, res.sqp_iter, where="mid", color="C1", alpha=0.7)
    ax_it.set_ylabel("SQP iterations", color="C1")

    fig.suptitle("2D point-mass MPC: " + res.message)
    if fig_filename is not None:
        fig.savefig(fig_filename, dpi=150)
        print(f"stored figure in {fig_filename}")
    if show_plot:
        plt.show()
    plt.close(fig)
