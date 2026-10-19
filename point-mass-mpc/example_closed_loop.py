"""Run the 2D point-mass MPC in closed loop, print a summary and save plots.

    python example_closed_loop.py                          # default scenario
    python example_closed_loop.py --target 2 9 --N 40      # other target/horizon
    python example_closed_loop.py --show                   # also open a window
"""

import argparse
import os

import numpy as np

from config import PointMassConfig
from controller import PointMassMPC
from simulation import run_closed_loop, summary

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--start", type=float, nargs=2, metavar=("PX", "PY"), help="start position (at rest)")
    parser.add_argument("--target", type=float, nargs=2, metavar=("PX", "PY"), help="target position (at rest)")
    parser.add_argument("--N", type=int, help="prediction horizon (dt stays fixed)")
    parser.add_argument("--show", action="store_true", help="show plots in a window (default: save only)")
    args = parser.parse_args()

    if not args.show:
        import matplotlib
        matplotlib.use("Agg")  # headless: works without a display
    from plots import plot_results  # import after choosing the backend

    changes = {}
    if args.start is not None:
        changes["x_start"] = np.array([*args.start, 0.0, 0.0])
    if args.target is not None:
        changes["x_target"] = np.array([*args.target, 0.0, 0.0])
    if args.N is not None:
        changes["N"] = args.N
    cfg = PointMassConfig().with_changes(**changes)  # validates

    print(f"dt = {cfg.dt} s, N = {cfg.N}, T = {cfg.T:.2f} s, "
          f"start = {cfg.x_start}, target = {cfg.x_target}")

    # solver creation (code generation + compilation) happens once, here
    mpc = PointMassMPC(cfg)
    res = run_closed_loop(cfg, mpc)

    print("\n" + summary(cfg, res))

    out = os.path.join(HERE, cfg.output_dir)
    os.makedirs(out, exist_ok=True)
    plot_results(cfg, res, fig_filename=os.path.join(out, "closed_loop_results.png"), show_plot=args.show)
    np.savez(os.path.join(out, "closed_loop_log.npz"), t=res.t, X=res.X, U=res.U,
             pos_err=res.pos_err, speed=res.speed, status=res.status,
             solve_time=res.solve_time, sqp_iter=res.sqp_iter,
             predictions=np.array(res.predictions), x_target=res.x_target,
             obstacle_corners=np.array([e.corners for e in res.obstacles]).reshape(-1, 4, 2),
             obstacle_centers=np.array([e.center for e in res.obstacles]).reshape(-1, 2),
             obstacle_E=np.array([e.E for e in res.obstacles]).reshape(-1, 2, 2))
    print(f"stored log in {os.path.join(out, 'closed_loop_log.npz')}")
    return 0 if res.converged else 1


if __name__ == "__main__":
    raise SystemExit(main())
