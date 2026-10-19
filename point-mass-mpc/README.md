# 2D point-mass MPC (acados)

A basic MPC controller that moves a point mass ("ball") from a start position to
a target position and brings it to rest there. It is the controller foundation
of ControlQuest, an MPC-based game. It is modeled on the acados pendulum example
(`exercise-07-acados-intro`) from the MPC+RL course repository `mpcrl26-exercises`,
which is not part of this repo.

## Environment

acados is not on PyPI and is not installed on Windows. The code runs in the
Docker image of the course repository `mpcrl26-exercises`, built from its
`Dockerfile`. That image contains Python 3.11, acados (`acados_template`),
CasADi 3.8.1, NumPy and Matplotlib. This repo has no Dockerfile of its own.

One-time setup: give the image a short name (Docker Desktop must be running;
look up the full name with `docker images`):

```powershell
docker tag vsc-mpcrl26-exercises-94d9982245bae36f409cb410a37b514aafe63fa52604de9d9dc9f0c9c94c729a mpcrl
```

## Run

The container mounts the repository folder, so scripts read and write your real
files. Run these from the **repository root** (`ControlQuest/`), in PowerShell:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace/point-mass-mpc mpcrl python example_closed_loop.py
docker run --rm -v "${PWD}:/workspace" -w /workspace/point-mass-mpc mpcrl python example_closed_loop.py --target 2 9 --N 40
docker run --rm -v "${PWD}:/workspace" -w /workspace/point-mass-mpc mpcrl python verify.py
```

The quotes are required because the path contains spaces. From Git Bash, turn
off its path conversion and pass a Windows path:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/workspace" -w /workspace/point-mass-mpc mpcrl python verify.py
```

For several runs in a row, open a shell inside the container and type `exit` to leave:

```powershell
docker run --rm -it -v "${PWD}:/workspace" -w /workspace/point-mass-mpc mpcrl bash
# then: python example_closed_loop.py --start 9 8, python verify.py, ...
```

Notes:

- The container has no display, so `--show` cannot open a window. Open
  `output/closed_loop_results.png` instead.
- acados prints a harmless warning: "CasADi version 3.8.1 is not tested with acados yet".

Results go to `output/`: `closed_loop_results.png`, `closed_loop_log.npz` and
`point_mass_2d_ocp.json`. They are tracked by git and overwritten on every run.
The generated C code also goes there, in `output/c_generated_code_point_mass_2d/`.
It is ignored by git (see `.gitignore`).
The solver is generated and compiled **once** per run (the first solve of a run is
slower). Each MPC step then only changes data and solves again (well under 1 ms per solve).

## Files

| File | Content |
|---|---|
| `config.py` | `PointMassConfig`: dt, N, start, target, weights, bounds, obstacle corners, tolerances, plus validation |
| `obstacles.py` | `Ellipse` and `ellipse_from_corners`: smallest ellipse around 4 corners (NumPy only) |
| `point_mass_model.py` | CasADi model (`disc_dyn_expr`) and the independent NumPy plant `plant_step` |
| `setup_ocp.py` | `setup_ocp(cfg)`: acados OCP (cost, constraints, solver options) |
| `controller.py` | `PointMassMPC`: builds the solver once; `solve(x)` returns `u0, X, U, status, solve_time` |
| `simulation.py` | receding-horizon loop, constraint and block-intrusion checks, summary (no plotting) |
| `plots.py`, `example_closed_loop.py` | plots and the entry point |
| `verify.py` | checks of the model, ellipses, cost scaling, scenarios, bounds and obstacles |

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
     |ax|, |ay| ≤ 2,  |vx|, |vy| ≤ 2,  0 ≤ px, py ≤ 50   (componentwise, k = 1..N)
     h_j(x_k) = (p_k − c_j)ᵀ E_j (p_k − c_j) ≥ 1          (obstacle j, k = 1..N)
```

**Obstacles.** Each obstacle is a block given by 4 corners in `config.py`
(`obstacle_corners`, any order; the block is their convex hull). The solver does not
use the block itself, because "outside a polygon" needs `max`/`min` of the edge
distances, which is non-smooth. Instead, `obstacles.py` computes the
**minimum-area ellipse that contains the 4 corners** (Khachiyan's algorithm) and
enlarges each semi-axis by `obstacle_margin` (0.1 m). The ellipse contains the
whole block, so `h_j ≥ 1` keeps the ball out of the block. The constraint is a
smooth quadratic (`con_h_expr` on stages 1..N−1, `con_h_expr_e` on N, with
`1 ≤ h ≤ ACADOS_INFTY`). For a rectangle with sides w × h the ellipse is
axis-aligned, with semi-axes w/√2 and h/√2. The defaults are the quadrilateral
(12,10) (17,10) (10,12) (10,17) and the rectangle (25,20) (32,20) (25,32) (32,32),
both on the straight path from start to target. The plot shows each block
(filled) and its ellipse (dashed).

The default scenario goes from (5, 5) to (40, 35) in a 50 m × 50 m workspace,
with t_sim_max = 60 s. The defaults are dt = 0.1 s, N = 30 (T = 3 s), Q = diag(10, 10, 1, 1),
R = diag(0.1, 0.1), and P = 10 Q. The terminal state is only penalized, not
constrained, so a target that is farther away than one horizon can reach stays feasible.

**acados scaling.** `LINEAR_LS` computes `c_k · ½ ‖[x;u] − yref‖²_W`, where
`cost_scaling` gives `c_k = dt` for the stages and `1` for the terminal stage.
This example sets `W = 2·blkdiag(Q, R)` and `W_e = 2P`, so dt is applied exactly
once. `verify.py` checks that the cost acados reports equals J.

**Problem class.** Without obstacles the problem is a convex QP. The obstacle
constraints make it a **nonconvex NLP**: the feasible set (outside an ellipse) is not
convex. SQP linearizes `h_j` at each iteration, i.e. replaces the ellipse by its
tangent half-plane, and HPIPM solves the resulting QP. Gauss–Newton uses only the
cost Hessian (exact for this LS cost) and ignores the constraint curvature, so each
QP stays convex. Plain full-step SQP can **cycle** near an obstacle (it failed
for a target straight behind the rectangle, on its symmetry axis), so a small
Levenberg–Marquardt term `levenberg_marquardt = 1e-2` (`lm·I` added to the QP
Hessian) damps the steps; it changes the steps, not the converged solution.
Merit backtracking was tried and was much worse. Typical runs need 1–4 SQP
iterations per step and about 1 ms per solve (max a few ms; one hard solve in
the symmetric case needs ~85 iterations, ~40 ms; `nlp_solver_max_iter = 200`).

## Changing settings

All settings are in `config.py`. To change them without editing code, use
`PointMassConfig().with_changes(x_target=np.array([2., 9., 0., 0.]), N=40, a_max=1.0)`,
or pass `--start`, `--target` and `--N` on the command line. dt stays fixed, so a
larger N gives a longer prediction. With an existing controller,
`mpc.set_target(...)` and new start states take effect without recompiling. Changing
N, dt or the model requires a new `PointMassMPC`, which generates new code.

## Relation to the pendulum example (course exercise 07)

The reference is `exercise-07-acados-intro/` in `mpcrl26-exercises`.

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

- The plant is the model itself (no model mismatch, noise or delay).
- The ellipse is larger than the block, so the ball keeps more distance than
  necessary, mostly near the long sides of elongated blocks and away from the corners.
- The NLP is nonconvex, so SQP finds a **local** optimum. Which side of an obstacle
  the ball takes depends on the initial guess (warm start), and the 3 s horizon
  does not see around large obstacles. The tested cases (including a target
  straight behind a block on its symmetry axis) all reach the target, but there is
  no guarantee: obstacle layouts with dead ends (e.g. a U-shape) can trap the ball,
  which would need a global planner or a longer horizon.
- While the ball slides along an ellipse, the input can chatter slightly
  (visible in a_y in the default run): the constraint is active at alternating
  stages of the discrete prediction.
- Obstacle constraints, like the bounds, hold at the sampling instants only.
  `block_intrusion` checks the exact path between samples against the true blocks;
  the ellipse margin keeps the ball out in all `verify.py` scenarios.
- The plain terminal penalty gives **no formal stability or recursive-feasibility
  guarantee**. The default horizon (3 s) is much longer than the braking time
  (1 s at 2 m/s and 2 m/s²), and in practice that is enough.
- Bounds are enforced at the sampling instants only. Between samples, the position can
  move slightly past a wall while the ball brakes towards it.
- A solve that fails or violates bounds stops the simulation. There is no
  fallback input; zero acceleration would not be a guaranteed safe fallback.
