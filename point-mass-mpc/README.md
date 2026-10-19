# 2D point-mass MPC (acados)

A basic MPC controller that moves a point mass ("ball") from a start position to
a target position and brings it to rest there. This is the controller part of a
future educational MPC playground. It is built on the acados example in
[`exercise-07-acados-intro`](../exercise-07-acados-intro/).

## Environment

The same environment as the course exercises (see the [root README](../README.md)).
acados is not on PyPI. The **Dev Container / root `Dockerfile`** builds acados
(the commit pinned by leap-c) and installs `acados_template`, CasADi, NumPy and
Matplotlib. On native Windows without acados, use the Dev Container.

## Run

From this folder, inside the Dev Container:

```bash
python example_closed_loop.py                       # default scenario, headless
python example_closed_loop.py --target 2 9 --N 40   # other target / horizon
python example_closed_loop.py --start 9 8 --show    # also open a plot window
python verify.py                                    # lightweight checks
```

Without opening the container in VS Code, from the repository root (Docker image built from the root `Dockerfile`):

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace/point-mass-mpc <image> python example_closed_loop.py
```

Results go to `output/` (ignored by git): `closed_loop_results.png` and
`closed_loop_log.npz`. The generated C code also goes there, in
`output/c_generated_code_point_mass_2d/`, so it does not overwrite the pendulum's files.
The solver is generated and compiled **once**. Each MPC step then only changes
data and solves again (well under 1 ms per solve).

## Files

| File | Content |
|---|---|
| `config.py` | `PointMassConfig`: dt, N, start, target, weights, bounds, tolerances, plus validation |
| `point_mass_model.py` | CasADi model (`disc_dyn_expr`) and the independent NumPy plant `plant_step` |
| `setup_ocp.py` | `setup_ocp(cfg)`: acados OCP (cost, constraints, solver options) |
| `controller.py` | `PointMassMPC`: builds the solver once; `solve(x)` returns `u0, X, U, status, solve_time` |
| `simulation.py` | receding-horizon loop, constraint check and summary (no plotting) |
| `plots.py`, `example_closed_loop.py` | plots and the entry point |
| `verify.py` | checks of the model, cost scaling, scenarios and bounds |

## Model

State `x = [px, py, vx, vy]` (m, m/s), control `u = [ax, ay]` (m/s²), and
continuous dynamics `p' = v`, `v' = a`. The input is held constant over each
interval `dt`, so the exact discrete model is

```
p+ = p + dt v + 0.5 dt² a        v+ = v + dt a
```

acados uses this map directly (`integrator_type = "DISCRETE"`). The OCP prediction
is therefore identical to the NumPy plant; `verify.py` checks this.

## Optimal control problem

```
min  Σ_{k=0}^{N-1} dt [ (x_k - x_t)ᵀ Q (x_k - x_t) + u_kᵀ R u_k ] + (x_N - x_t)ᵀ P (x_N - x_t)
s.t. x_0 = x̄ (measured state),  x_{k+1} = f(x_k, u_k)
     |ax|, |ay| ≤ 2,  |vx|, |vy| ≤ 2,  0 ≤ px, py ≤ 10   (componentwise, k = 1..N)
```

The defaults are dt = 0.1 s, N = 30 (T = 3 s), Q = diag(10, 10, 1, 1),
R = diag(0.1, 0.1), and P = 10 Q. The terminal state is only penalized, not
constrained, so a target that is farther away than one horizon can reach stays feasible.

**acados scaling.** `LINEAR_LS` computes `c_k · ½ ‖[x;u] − yref‖²_W`, where
`cost_scaling` gives `c_k = dt` for the stages and `1` for the terminal stage.
This example sets `W = 2·blkdiag(Q, R)` and `W_e = 2P`, so dt is applied exactly
once. `verify.py` checks that the cost acados reports equals J.

**Why acados for a linear problem?** The dynamics are linear and the cost and
constraints are convex, so the problem is a convex QP. SQP with Gauss–Newton then
converges in the first QP step, which HPIPM solves. acados is usually used for
nonlinear MPC, but it handles this simpler case just as well. The same code will
keep working when nonlinear dynamics or obstacle constraints are added later.

## Changing settings

All settings are in `config.py`. To change them without editing code, use
`PointMassConfig().with_changes(x_target=np.array([2., 9., 0., 0.]), N=40, a_max=1.0)`,
or pass `--start`, `--target` and `--N` on the command line. dt stays fixed, so a
larger N gives a longer prediction. With an existing controller,
`mpc.set_target(...)` and new start states take effect without recompiling. Changing
N, dt or the model requires a new `PointMassMPC`, which generates new code.

## Relation to the pendulum example (exercise 07)

- `setup_ocp_sol.py` → `point_mass_model.py` and `setup_ocp.py`: the same
  `export_*_model()` / `setup_ocp()` structure, the least-squares output
  `y = [x; u]` with `W` and `yref`, `idxbu` input bounds, `constraints.x0`,
  Gauss–Newton and the tolerances. Two things change: `NONLINEAR_LS` becomes
  `LINEAR_LS`, and ERK on `f_expl_expr` becomes `DISCRETE` with `disc_dyn_expr`.
  State bounds (`idxbx`, `idxbx_e`) are added.
- `example_closed_loop.py`: same idea. The solver is created once before the
  loop, then each step solves from the current state, applies only the first
  input, and steps the plant. Here the plant is NumPy, not `AcadosSimSolver`.
  A failed solve stops the loop with a diagnostic; the pendulum example instead
  uses `fail_on_nonzero_status=False` and clipping.

## Known limitations

- No obstacles. The plant is the model itself (no model mismatch, noise or delay).
- The plain terminal penalty gives **no formal stability or recursive-feasibility
  guarantee**. The default horizon (3 s) is much longer than the braking time
  (1 s at 2 m/s and 2 m/s²), and in practice that is enough.
- Bounds are enforced at the sampling instants only. Between samples, the position can
  move slightly past a wall while the ball brakes towards it.
- A solve that fails or violates bounds stops the simulation. There is no
  fallback input; zero acceleration would not be a guaranteed safe fallback.
