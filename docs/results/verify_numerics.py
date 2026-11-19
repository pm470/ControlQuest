"""Numerical verification of ControlQuest's MPC solutions (for docs/RESEARCH.md).

Read-only: it wraps MPCController.solve to record every plan of a run and checks it; the game,
the controller and the level rules are not changed. Run inside the course Docker image:

    docker run --rm -v "<repo>:/workspace" -w /workspace/game/engine_server <image> \
        python /workspace/docs/results/verify_numerics.py

Checks:
1. Crosswind: the deviation from the prediction in force (engine metric since 0.14.0: up to and
   including the moment a plan is replaced), its mean at the re-plans, the same over the common
   window t <= 6 s (every run lasts that long and sees the same wind), and the previous
   definition (until 0.13.0) for comparison.
2. Brake Check: every accepted plan: terminal velocity |v_N| with the terminal stop on, dynamics
   residual |x_{k+1} - f(x_k, u_k)|, x_0 = measured state, input and state bounds, acados status
   and KKT residuals.
3. Dead End: solver status, SQP iterations, plan change and KKT residuals while the ball is stuck.
4. Obstacles: smallest ellipse value h of the accepted plans' predicted positions and the largest
   slack (Dead End, Crosswind).

Slack cost in acados (checked in the acados source of the image, acados/ocp_nlp/ocp_nlp_cost_ls.c):
per stage fun = scaling * (0.5 |r|_W^2 + z^T s + 0.5 s^T diag(Z) s), with scaling = cost_scaling
(dt on stages 0..N-1, 1 at N); see the documentation printed first.
"""

import sys

import numpy as np

sys.path.insert(0, ".")
import runner  # noqa: E402
from level_rules import crosswind as CW  # noqa: E402
from mpc import controller as C  # noqa: E402

REC = []
_orig = C.MPCController.solve


def _recording_solve(self, x0):
    plan = _orig(self, x0)
    rec = {"x0": np.asarray(x0, float), "X": np.array(plan.X), "U": np.array(plan.U),
           "status": plan.status, "ok": plan.ok, "it": plan.iterations, "N": self.N, "dt": self.dt,
           "g": self._gain, "xlb": self._x_lb, "xub": self._x_ub, "ulb": self._u_lb, "uub": self._u_ub,
           "hmin": self._min_obstacle_h(np.array(plan.X)[1:])}
    try:
        rec["res"] = np.array(self.solver.get_residuals())  # [stationarity, eq, ineq, complementarity]
    except Exception:  # noqa: BLE001
        rec["res"] = None
    try:
        rec["sl"] = max(float(np.max(self.solver.get(k, "sl"))) for k in range(1, self.N + 1))
    except Exception:  # noqa: BLE001
        rec["sl"] = None
    REC.append(rec)
    return plan


C.MPCController.solve = _recording_solve


def f(x, u, g, dt):
    p, v = x[:2], x[2:]
    return np.concatenate([p + dt * v + 0.5 * dt**2 * g * u, v + dt * g * u])


def run(level, knobs, wps=None, fix=None):
    REC.clear()
    return runner.run_level(level, knobs, wps, fix), list(REC)


def plan_checks(recs, stop=False):
    acc = [r for r in recs if r["ok"]]
    out = {
        "accepted": len(acc), "total": len(recs),
        "status": {s: sum(r["status"] == s for r in recs) for s in sorted({r["status"] for r in recs})},
        "dyn": max(max(np.abs(r["X"][k + 1] - f(r["X"][k], r["U"][k], r["g"], r["dt"])).max()
                       for k in range(r["N"])) for r in acc),
        "x0": max(np.abs(r["X"][0] - r["x0"]).max() for r in acc),
        "u_viol": max(0.0, max(np.maximum(r["ulb"] - r["U"], r["U"] - r["uub"]).max() for r in acc)),
        "x_viol": max(0.0, max(np.maximum(r["xlb"] - r["X"][1:], r["X"][1:] - r["xub"]).max() for r in acc)),
        "vN": max(np.abs(r["X"][-1][2:]).max() for r in acc) if stop else None,
    }
    res = [r["res"] for r in acc if r["res"] is not None]
    out["res"] = np.max(np.array(res), axis=0) if res else None
    return out


def old_drift(traj):
    """The definition used until engine 0.13.0: against the plan being executed at sample k,
    which at a re-plan is the NEW plan (it starts at the measured ball: 0)."""
    x, plans, steps = np.array(traj["x"]), traj["plans"], traj["solve_steps"]
    out, s = np.zeros(len(x)), 0
    for k in range(len(x)):
        while s + 1 < len(steps) and steps[s + 1] <= k:
            s += 1
        m = k - steps[s]
        if 0 <= m < len(plans[s]):
            out[k] = np.linalg.norm(np.array(plans[s][m][:2]) - x[k, :2])
    return out


np.set_printoptions(precision=2)
print("# acados documentation of the slack cost and the cost scaling")
from acados_template import AcadosOcpCost, AcadosOcpOptions  # noqa: E402
for name in ("zl", "Zl"):
    print(f"cost.{name}:", " ".join((getattr(AcadosOcpCost, name).__doc__ or "").split())[:160])
print("opts.cost_scaling:", " ".join((AcadosOcpOptions.cost_scaling.__doc__ or "").split())[:200])

print("\n# 1. Crosswind: deviation from the prediction in force [m]")
print("k    m    outcome        t_end solves | max (run)  mean at re-plans | window t<=6 s: max  mean"
      " | previous definition: max | plans: min h  max slack")
for margin in (0.1, 0.3):
    for k in (1, 2, 3, 5, 10, 20):
        r, recs = run("crosswind", {"k": k, "margin": margin})
        tr, m = r["trajectory"], r["metrics"]
        d, t = np.array(tr["drift"]), np.array(tr["t"])
        w = (t <= 6.0 + 1e-9) & (t > 0)
        acc = [q for q in recs if q["ok"]]
        print(f"{k:<4} {margin:<4} {r['outcome']:<14} {tr['t'][-1]:>5.1f} {len(tr['plans']):>6} | "
              f"{m['max_drift']:>9.3f}  {m['mean_replan_deviation']:>16.3f} | {d[w].max():>18.3f} "
              f"{d[w].mean():>5.3f} | {old_drift(tr).max():>24.3f} | {min(q['hmin'] for q in acc):>12.3f}"
              f"  {max((q['sl'] or 0.0) for q in acc):>9.1e}")

print("\n# 2. Brake Check: accepted plans (max over all accepted solves of the run)")
print("N   stop outcome            accepted/total status       |v_N|      dyn res    x0 err     "
      "u viol     x viol     KKT residuals [stat, eq, ineq, comp]")
for N in (5, 10, 20, 30, 40, 60):
    for stop in (0, 1):
        r, recs = run("brake_check", {"N": N, "stop": stop})
        c = plan_checks(recs, stop=bool(stop))
        vN = f"{c['vN']:.1e}" if c["vN"] is not None else "-"
        print(f"{N:<3} {stop:<4} {r['outcome']:<18} {c['accepted']:>4}/{c['total']:<9} {str(c['status']):<12} "
              f"{vN:<10} {c['dyn']:<10.1e} {c['x0']:<10.1e} {c['u_viol']:<10.1e} {c['x_viol']:<10.1e} {c['res']}")
        if not recs[-1]["ok"]:
            print(f"    last solve rejected: acados status {recs[-1]['status']}")

print("\n# 3. Dead End: solver behaviour while the ball is stuck (last 10 s = 100 solves)")
for label, knobs, wps, fix in (("no fix", {}, None, "none"), ("N = 60", {"N": 60}, None, "horizon"),
                               ("N = 100", {"N": 100}, None, "horizon"), ("N = 150", {"N": 150}, None, "horizon"),
                               ("waypoint (35, 40)", {}, [[35.0, 40.0]], "waypoints")):
    r, recs = run("dead_end", knobs, wps, fix)
    c = plan_checks(recs)
    tail = recs[-100:]
    its = np.array([q["it"] for q in tail])
    change = max(np.abs(tail[i + 1]["X"][:, :2] - tail[i]["X"][:, :2]).max() for i in range(len(tail) - 1))
    xs = np.array(r["trajectory"]["x"])
    moved = float(np.linalg.norm(xs[-1, :2] - xs[-101, :2]))
    res_tail = np.max(np.array([q["res"] for q in tail if q["res"] is not None]), axis=0)
    acc = [q for q in recs if q["ok"]]
    print(f"{label:<18} {r['outcome']:<9} status {c['status']}; last 10 s: SQP iterations "
          f"{ {int(a): int(b) for a, b in zip(*np.unique(its, return_counts=True))} }, plan change <= {change:.1e} m, "
          f"ball moved {moved:.1e} m, KKT residuals <= {res_tail}; whole run: dyn res {c['dyn']:.1e}, "
          f"min h {min(q['hmin'] for q in acc):.4f}, max slack {max((q['sl'] or 0.0) for q in acc):.1e}")
