# ControlQuest: Product Requirements Document

**Status:** draft v1, the base we build against
**Team:** 2 people · **Time budget:** 2 weeks, part-time
**Last updated:** 2026-10-19

Change this document when we change our minds; it is the single source of truth
for *what* we build. Numbers marked **(calibrate)** are first guesses that must be
tuned with real runs before they are final.

---

## 1. Summary

ControlQuest is a puzzle game about **designing an MPC controller**. In every level
a ball has to get from a start to a target on a 2D map with obstacles. The player
does **not** steer the ball. The player sets parts of the MPC problem (cost weights,
horizon, margins, a model parameter, waypoints, re-planning rate), presses **Run**,
and watches the controller succeed or fail. Each level is built so that the default
controller fails in one specific way, and the fix is one MPC concept from the course.

The core of the game is the **live predicted plan**: at every step the game draws
the trajectory the MPC is currently planning, so the receding horizon is visible.

## 2. Goals and non-goals

### Goals
1. **Teach by failure:** each level shows one MPC property through a failure the
   player can understand and fix.
2. **Make MPC visible:** show the plan, the constraints the solver sees, and why a
   run ended the way it did.
3. **Be finishable:** 4–5 polished levels in 2 weeks by 2 part-time people.
4. **Be honest about the controller:** every number shown (cost, solve time,
   iterations, constraint margins) comes from the real acados solver.

### Non-goals (explicitly out of scope)
- RL / learning-based tuning (a possible stretch goal only, see §13).
- The player steering the ball directly (no keyboard driving mode).
- A level editor (could-have, only if everything else is done).
- Accounts, online leaderboards, multiplayer, sound, mobile layouts, 3D.
- Exact polygon constraints (we keep the ellipse approximation; see §4.3).
- Real-time streaming of the simulation (we compute first, then replay; §9.1).

## 3. Target players

Students who took the MPC course with us. We assume they know:
- receding horizon control, OCPs, cost weights Q / R / P, horizon N;
- terminal cost and terminal constraints, recursive feasibility;
- SQP, local optima, initial guesses, nonconvex constraints;
- model mismatch and disturbances.

Consequences for the design:
- We use course notation (Q, R, P, N, x_k, u_k) in the UI, with a plain-language
  name next to each symbol.
- Explanations can be short and technical. We don't explain what an OCP is.
- The challenge comes from trade-offs, not from hidden information. The player
  should always be able to work out *why* something happened.
- A full playthrough should take **20–40 minutes**.

## 4. The world and its rules (same in every level)

### 4.1 The ball
- Point mass in 2D. State `x = [px, py, vx, vy]`, input `u = [ax, ay]`.
- Model used by the controller: double integrator with exact zero-order hold,
  `p+ = p + dt·v + ½dt²·g·a`, `v+ = v + dt·g·a`. `g` is the *model actuator
  gain* (1 except in Level 4).
- Sampling time `dt = 0.1 s` in every level (fixed, not a knob).
- Box limits `|ax|, |ay| ≤ a_max` and `|vx|, |vy| ≤ v_max`, set per level.

### 4.2 The "real" ball (plant)
The plant is simulated separately from the model, so levels can add:
- **actuator mismatch:** the real gain `g_true` differs from the model's `g` (Level 4);
- **disturbances:** wind acceleration added to the plant (Level 5), generated
  from a **fixed random seed** so every run of a level is reproducible.

### 4.3 Map, obstacles and how the solver sees them
- Workspace: 50 m × 50 m, `0 ≤ px, py ≤ 50`. The walls are hard state bounds.
- **Blocks** are defined by 4 corners (their convex hull). This is what the player
  sees as the obstacle and what crashes are checked against.
- The solver never sees blocks. It sees the **smallest ellipse containing the 4
  corners**, enlarged by the *obstacle margin*, as the smooth constraint
  `(p − c)ᵀE(p − c) ≥ 1` (already implemented in `point-mass-mpc/obstacles.py`).
- The game can show the ellipses (dashed outlines). Showing them is on by
  default, because the gap between "block" and "what the solver avoids" is itself
  something to learn.
- **Level-design warning:** ellipses of long, thin blocks are much bigger than the
  block and stick out past its ends. Ellipses of neighbouring blocks can overlap
  and close a gap that looks open. **Always design and check maps with the
  ellipses visible.**

### 4.4 How a run ends
A run stops as soon as one of these happens. The first one decides the outcome.

| Outcome | Condition | Shown as |
|---|---|---|
| **Success** | `‖p − p_target‖ < 0.05 m` and `‖v‖ < 0.05 m/s` | green, star rating |
| **Crash (block)** | the real ball's path enters a block. Checked on the continuous path between samples, not only at samples. | red, crash marker at the point of contact |
| **Crash (wall)** | the real path leaves the workspace | red |
| **Controller failure** | acados returns a non-zero status or an invalid plan, e.g. no feasible plan exists | orange, with the status and the reason |
| **Time out** | `t > t_limit` of the level | grey |
| **Budget exceeded** | a level budget is exceeded, e.g. energy or number of solves. Checked during the run. | grey, with which budget |

A controller failure **stops** the run. There is no fallback input. "No feasible
plan existed" is one of the lessons (Level 2), so we show it, not hide it.

Entering an **ellipse** but not the block is not a crash. It shows a yellow
"constraint violated" warning on the timeline. In practice the next solve usually
fails, which then ends the run as a controller failure.

## 5. Game structure and screens

### 5.1 Flow
`Title → Level select → Level screen (briefing → tune → run → result) → next level`

- Level 1 is unlocked at the start. Each passed level unlocks the next.
- A "Free mode" toggle in the level select unlocks all levels, for demos and the
  course presentation.
- Best result per level (stars, best time) is saved locally in the browser.

### 5.2 Level screen layout

```
┌──────────────────────────────────────────────┬──────────────────────────┐
│                                              │  LEVEL 2 · Brake Check   │
│                                              │  Goal: stop at ★ < 30 s  │
│                  MAP VIEW                    │──────────────────────────│
│   blocks (filled), ellipses (dashed),        │  KNOBS (unlocked)        │
│   start ●, target ★, waypoints ◆,            │   Horizon N   [ 10 ▾]    │
│   ball, trail, CURRENT PLAN (dashed + dots), │   Terminal stop  [ ]     │
│   wind arrow, crash marker                   │  KNOBS (locked, greyed)  │
│                                              │   Q, R, P, margin        │
│                                              │──────────────────────────│
│                                              │  [ Run ]  [ Reset ]      │
│                                              │  [ Hint ]                │
├──────────────────────────────────────────────┴──────────────────────────┤
│  ◀◀  ▶/❚❚  ▶▶   speed 0.5× 1× 2× 4×   ───────●─────────── t = 7.3 s     │
├─────────────────────────────────────────────────────────────────────────┤
│  PLOTS (cursor follows playback): speed | inputs | level-specific plot  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Map view
Must show:
- workspace border;
- blocks (filled) and solver ellipses (dashed; toggle);
- start, target, and waypoints if any;
- the ball and its trail;
- **the current predicted plan** `x_0 … x_N`: dashed line with a dot per stage.
  Its end is marked so the horizon length is visible.

Should show:
- toggle "plan history": faint copies of every 10th plan;
- in Level 4: **predicted vs actual**, a ghost dot where the previous plan said
  the ball would be now;
- in Level 5: wind direction and strength (arrow), and the plan segment executed
  open-loop between two re-plans;
- the crash or failure point, marked on the map.

### 5.4 Knob panel
- Only the knobs unlocked for the level are editable. Locked knobs are shown
  greyed out with their value, so the player sees the whole controller.
- Every knob shows the **symbol and a plain name**, e.g. `r — input weight R = r·I`.
- Weights use **logarithmic sliders**, because only ratios matter and useful
  values span decades.
- Discrete knobs (N, re-plan interval) use dropdowns of allowed values.
- The panel shows the cost of the current settings where relevant, e.g. the
  horizon length in seconds `T = N·dt` and in metres at v_max.

### 5.5 "Your OCP" panel (should-have)
A small panel shows the optimal control problem with the **current numbers**
filled in, and highlights terms the player changed. For example:

```
min  Σ_{k=0}^{29} 0.1·[ 10‖p_k − p★‖² + 1‖v_k‖² + 0.1‖u_k‖² ] + 100‖p_30 − p★‖² + …
s.t. x_0 = x̄,  x_{k+1} = f(x_k, u_k),  |u| ≤ 2,  |v| ≤ 2,
     (p_k − c_j)ᵀE_j(p_k − c_j) ≥ 1   (2 obstacles, margin 0.1 m)
```

This connects the game to the course material, and it's cheap to build (text only).

### 5.6 Playback and plots
- **Run** computes the whole closed loop (see §9.1), then plays it back. The
  player can pause, scrub, step one sample at a time, and change speed
  (0.5×–4×).
- Plots under the map share the playback cursor:
  - always: speed ‖v‖ with v_max, inputs ax and ay with ±a_max;
  - per level, one extra plot: cumulative energy with budget line (L1), distance to
    wall vs braking distance (L2), distance to the next waypoint (L3), predicted vs
    actual position error (L4), cumulative number of solves with budget line (L5).
- Should-have: solve time and SQP iterations per step, so expensive moments are
  visible (e.g. sliding along an ellipse).

### 5.7 Result panel
After a run:
- outcome (§4.4) and **stars** (§6);
- metrics table with the level's pars: time to target, energy, number of solves,
  minimum clearance to blocks, mean/max solve time, max SQP iterations;
- **"What happened"**: 1–3 sentences generated from rules (§10.1) that explain the
  outcome with numbers from the run;
- buttons: *Retry with these settings*, *Reset to defaults*, *Next level*.

### 5.8 Hints
Each level has 2–3 hints, revealed one at a time by the **Hint** button. The first
hint points at the concept, the last one is almost the answer. Hints don't cost
stars (keep it simple).

## 6. Scoring

Per level:
- **★** pass the level (success outcome);
- **★★** also beat the level's *time par*;
- **★★★** also beat the level's *secondary par* (energy, horizon, margin,
  waypoints or solves, depending on the level).

The secondary par always pulls against the "easy" fix, so 3 stars needs
understanding, not just turning one knob to the maximum.

## 7. Levels

There are five levels. Each table lists the map, the knobs, the default (failing)
settings, why they fail, the intended fixes, and what the level shows.

All coordinates in metres. Maps are first proposals **(calibrate)**.

**Priority:** Levels 1, 2, 4 and 5 are must-have. Level 3 is should-have, because it
needs the most extra work (waypoints and their UI).

---

### Level 1: "The Price of Speed" (cost function trade-off)

**Concept:** the cost function is a trade-off. Q against R decides between fast and
cheap, and only the ratios matter.

**Briefing:** *"The battery is small this time. Get to the target before the timer
runs out, without using more energy than the battery holds."*

| Item | Value |
|---|---|
| Map | open field, no blocks. Start (5, 25), target (45, 25). |
| Limits | a_max = 2, v_max = 2 |
| Time limit | 30 s **(calibrate)** |
| Budget | energy `E = Σ dt·‖u_k‖² ≤ 4` **(calibrate)** |
| Unlocked knobs | `q_p` position weight (Q₁₁ = Q₂₂), `q_v` velocity weight (Q₃₃ = Q₄₄), `r` input weight (R = r·I); all log sliders 1e-3 … 1e3 |
| Locked | N = 30, P = 10·Q, no obstacles |
| Default | q_p = 10, q_v = 1, r = 0.1, close to time-optimal |
| Why the default fails | it accelerates and brakes at full a_max: ≈ 2·a·v = 8 energy units > 4 |
| Intended fixes | raise r (or lower q_p) until the acceleration is gentle; too gentle → time out |
| ★★ time par | ≤ 24 s **(calibrate)** |
| ★★★ secondary par | energy ≤ 3 **(calibrate)** |
| Extra plot | cumulative energy with the budget line |
| Teaching note in the result | if the player scaled all weights by the same factor: "Nothing changed: multiplying Q, R and P by the same number does not change the optimal solution." |

---

### Level 2: "Brake Check" (horizon length, recursive feasibility, terminal constraint)

**Concept:** the horizon has to cover the braking distance, or the controller sees
the problem too late and runs out of feasible plans. A terminal constraint
("be stopped at the end of the horizon") restores safety, but makes the
controller conservative.

**Briefing:** *"New, faster ball, weaker brakes. The target is right in front of
the wall. Stop on it."*

| Item | Value |
|---|---|
| Map | open field. Start (4, 25), target (46, 25), so the wall at x = 50 is 4 m behind the target. |
| Limits | a_max = 1, v_max = 4 → braking from full speed: 4 s, 8 m |
| Time limit | 30 s **(calibrate)** |
| Unlocked knobs | horizon N ∈ {5, 10, 20, 30, 40, 60}; toggle **terminal stop** (`v_N = 0`) |
| Locked | Q, R, P at defaults |
| Default | N = 10 (1 s), terminal stop off |
| Why the default fails | the plan only reaches ~4 m ahead at full speed, but stopping needs 8 m. When the controller "sees" it must brake, no feasible plan exists any more → **controller failure** (or a wall crash) |
| Intended fix A | long horizon (N ≥ 40) → fast and safe, but expensive |
| Intended fix B | short horizon + terminal stop → always feasible, but the ball only drives as fast as it can stop within the horizon → slow. With N = 10 that is too slow (time out); N = 20 + terminal stop should pass **(calibrate)** |
| ★★ time par | ≤ 16 s **(calibrate)** |
| ★★★ secondary par | N ≤ 20 (compute is cheap), i.e. needs fix B and a good N |
| Extra plot | distance to the wall ahead vs braking distance `v²/(2·a_max)` and vs horizon reach |
| Teaching note | failure text names both numbers: "At t = 9.4 s the ball was 6.1 m from the wall at 4 m/s; braking needs 8 m. Your horizon covered 1.0 s (≈ 4 m)." |

Dropdown values for N are **precompiled solvers** (see §9.3), so switching N is instant.

---

### Level 3: "Dead End" (nonconvexity and local optima)

**Concept:** with obstacles the OCP is nonconvex. The MPC is a *local* planner with
a short horizon, so it can get trapped in a local optimum. A higher-level plan
(waypoints) fixes it; this is how MPC is used in practice.

**Briefing:** *"The direct route looks open… it isn't. Help the controller with up
to 3 waypoints."*

| Item | Value |
|---|---|
| Map | U-shaped trap that opens towards the start: back wall x ∈ [30, 33], y ∈ [15, 35]; arms y ∈ [32, 35] and y ∈ [15, 18], x ∈ [20, 33]. Start (5, 25), target (45, 25). **(calibrate: check the ellipse sizes)** |
| Limits | a_max = 2, v_max = 2 |
| Time limit | 45 s **(calibrate)** |
| Unlocked knobs | place up to **3 waypoints** by clicking on the map (drag to move, right-click to delete) |
| Locked | Q, R, P, N = 30, margin |
| Default | no waypoints |
| Why the default fails | the ball drives into the U and stops at the back wall: the cost gradient points straight into the obstacle, the 3 s horizon sees no way around → **time out** |
| Intended fix | 1–2 waypoints outside the U (e.g. above the top arm), then the target |
| Waypoint rule | the MPC reference is the next waypoint (position only, velocity reference = 0). Within the *switch radius* of 2 m **(calibrate)**, the reference jumps to the next waypoint, so the ball doesn't brake at each waypoint. Waypoints inside an ellipse are rejected when placed. |
| ★★ time par | ≤ 32 s **(calibrate)** |
| ★★★ secondary par | ≤ 1 waypoint |
| Extra plot | distance to the current reference (shows switching) |
| Teaching note | on time out near an obstacle: "The ball stopped 0.4 m from obstacle 1 with the target behind it: a local optimum. The horizon (3 s) cannot see around the obstacle." |

**Cheaper fallback if we are short on time:** replace click-to-place with 2–3
predefined waypoint candidates the player toggles on and off.

**Alternative mechanic (not planned):** the player sketches a path that becomes
the solver's initial guess. More "MPC-pure", but riskier: the warm start only
affects the first solves, so the effect may vanish. Only try this if waypoints
are done early.

---

### Level 4: "Heavy Ball" (model mismatch, constraint tightening vs a better model)

**Concept:** the controller plans with a model. If the real system is different,
plans that are safe on paper crash in reality. There are two fixes: a **safety
margin** (robust, costs performance) or a **better model** (identify the real
parameter).

**Briefing:** *"Someone swapped the ball. It looks the same but responds less to
the motors. Park it in the bay without touching the walls."*

| Item | Value |
|---|---|
| Map | a "parking bay": target (40, 25) with a block just behind it, x ∈ [42, 47], y ∈ [20, 30], and a block on each side of the approach, e.g. y ∈ [28, 33] and y ∈ [17, 22], x ∈ [30, 40] **(calibrate the gap with the ellipses)**. Start (5, 25). |
| Plant | real actuator gain **g_true = 0.6** (hidden from the player). The model uses the knob value `g`. |
| Limits | a_max = 2 (commanded), v_max = 2 |
| Time limit | 40 s **(calibrate)** |
| Unlocked knobs | obstacle margin 0 … 3 m; model actuator gain `g` 0.3 … 1.0 |
| Extra action | **Test drive** button: applies a constant `ax = 1` for 2 s from rest on an empty map and shows predicted vs measured distance, e.g. "predicted 2.0 m, measured 1.2 m". The player can infer g_true ≈ 0.6 from this. |
| Locked | Q, R, P, N = 30 |
| Default | margin = 0.1 m, g = 1.0 |
| Why the default fails | the plan assumes 2 m/s² of braking but only 1.2 m/s² happens. The ball brakes too late and turns too wide → **crash** into the block behind the target (or it enters the ellipse → controller failure) |
| Intended fix A | larger margin (robust; slower, uses more space; too large closes the bay) |
| Intended fix B | set g ≈ 0.6 using the test drive (accurate model; near-perfect run) |
| ★★ time par | ≤ 26 s **(calibrate)** |
| ★★★ secondary par | margin ≤ 0.3 m, which effectively requires fix B |
| Extra plot | prediction error: distance between where the previous plan said the ball would be and where it is |
| Map extra | ghost dot of the one-step-ahead prediction |
| Teaching note | "The plan predicted the ball at (39.2, 25.0); it actually was at (40.1, 25.0). The model assumes more braking than the real ball has." |

---

### Level 5: "Crosswind" (feedback: why we re-plan)

**Concept:** MPC is feedback because it re-plans from the measured state. If you
re-plan rarely, the controller is effectively open-loop between solves and
disturbances push the ball off its plan. Re-planning costs computation, so it's a
trade-off.

**Briefing:** *"It's windy. You have a limited compute budget: every re-plan uses
one solve. Get through the gap."*

| Item | Value |
|---|---|
| Map | two square blocks with a gap: (22, 14)–(28, 20) and (22, 30)–(28, 36); the ellipses leave a gap of ≈ 7 m **(calibrate)**. Start (5, 25), target (45, 25). |
| Plant | wind acceleration in +y: constant 0.3 m/s² plus gusts, piecewise constant for 1 s each, uniform in [−0.6, 0.6] m/s², **fixed seed** **(calibrate)** |
| Limits | a_max = 2, v_max = 2 |
| Time limit | 35 s **(calibrate)** |
| Budget | max **60 solves** for the run **(calibrate)**; a run of ~20 s has ~200 steps, so re-planning every step is not allowed |
| Unlocked knobs | re-plan interval `k` ∈ {1, 2, 3, 5, 10, 20} (between re-plans the controller applies the next inputs of the last plan, open-loop); obstacle margin 0 … 3 m |
| Locked | Q, R, P, N = 30 |
| Default | k = 1 (always re-plan) |
| Why the default fails | it is perfect but uses ~200 solves → **budget exceeded** |
| What the player discovers | k = 20 → the wind drifts the ball into a block → crash; k = 3–5 → passes within budget; a larger margin allows a larger k |
| ★★ time par | ≤ 24 s **(calibrate)** |
| ★★★ secondary par | ≤ 40 solves **(calibrate)** |
| Extra plot | cumulative solves with the budget line; drift = distance between plan and actual position |
| Map extra | wind arrow; the open-loop segment of the plan being executed is drawn solid, the rest dashed |
| Teaching note | "Between re-plans the ball ran open-loop for 2.0 s and the wind pushed it 1.8 m off the plan." |

## 8. Knob reference (all levels)

| Knob | Symbol / meaning | Range | Type | Levels | Needs a new solver? |
|---|---|---|---|---|---|
| Position weight | `q_p`: Q₁₁ = Q₂₂ | 1e-3 … 1e3 | log slider | 1 | no (runtime) |
| Velocity weight | `q_v`: Q₃₃ = Q₄₄ | 1e-3 … 1e3 | log slider | 1 | no |
| Input weight | `r`: R = r·I | 1e-3 … 1e3 | log slider | 1 | no |
| Horizon | `N`, T = N·dt | {5, 10, 20, 30, 40, 60} | dropdown | 2 | precompiled per value |
| Terminal stop | `v_N = 0` | on/off | toggle | 2 | no (terminal bounds) |
| Waypoints | intermediate references | 0–3 | map clicks | 3 | no |
| Obstacle margin | added to each semi-axis | 0 … 3 m | slider | 4, 5 | no (parameters) |
| Model actuator gain | `g` in the model | 0.3 … 1.0 | slider | 4 | no (parameter) |
| Re-plan interval | `k` steps between solves | {1, 2, 3, 5, 10, 20} | dropdown | 5 | no |

Fixed in every level: `dt = 0.1 s`, terminal weight `P = 10·Q` (not a knob, to keep
the knob count small), solver settings.

## 9. Technical requirements (only what the design depends on)

### 9.1 Compute first, then replay
A run is computed completely by the backend, typically 100–400 steps at ~1 ms per
solve, so well under a second. The result is then sent to the UI and played back.
This avoids real-time streaming and makes pause, scrub and replay trivial. The
"compute budget" in Level 5 counts solves; it does not use wall-clock time.

### 9.2 Where it runs
acados only runs in our Docker image (Linux). So:
- the game backend (Python, the existing `point-mass-mpc` code) runs **in the container**;
- the UI runs in the **browser on the host** and talks to the backend over a
  mapped port;
- starting it must be **one command** (documented in the README).

**Decision needed on day 1:** the UI technology. Options:
- (a) a small Python web server plus a hand-written HTML/JS canvas page. This
  gives the most control over the map animation, but needs some JS.
- (b) a Python UI framework (e.g. Dash/Plotly), which is Python-only. Custom map
  interaction (clicking waypoints, smooth playback) is clunkier there.

Pick the one that matches what we already know; the rest of this document doesn't
depend on it.

### 9.3 Solver must not recompile during play
- Code generation and compilation take seconds, so it must not happen on Run.
- **Weights (Q, R), obstacle centres and shapes, margin, model gain `g`, terminal
  velocity bounds and references** must be runtime-changeable without recompiling.
  acados supports this through stage parameters `p` and cost/constraint setters.
- Obstacles: compile for a fixed maximum number of obstacle slots, e.g. 6. Unused
  slots get a tiny ellipse far outside the map.
- **N** changes the problem size. Precompile one solver per allowed N at startup
  and cache them.

### 9.4 Data formats (the contract between the two of us)
Agree on these two formats first. Then backend and UI can be built in parallel.

**Level file** (one JSON per level), with fields:
- `id`, `name`, `concept`, `briefing`, `hints[]`;
- `map`: workspace, blocks (4 corners each), start, target;
- `limits`: `a_max`, `v_max`;
- `plant`: `g_true`, `wind`: constant, gust amplitude, gust period, seed;
- `t_limit` and `budgets`: energy, max solves;
- `knobs[]`: name, unlocked, default, range or allowed values;
- `locked_values`;
- `pars`: time, secondary;
- `allow_waypoints`, `max_waypoints`;
- `checks`: the expected default outcome and a reference solution (§11).

**Run request:** level id, knob values, waypoints.

**Run result** (JSON):
- per step: `t, x, u`, plan `X (N+1 × 4)`, solver status, solve time, SQP
  iterations, whether a solve happened this step (Level 5), current reference;
- events: waypoint reached, ellipse entered, crash with its position, failure;
- metrics, outcome, stars, explanation strings.

The existing `ClosedLoopResult` already holds most of this.

### 9.5 Non-functional
- One Run, including the response, takes < 2 s for every level.
- Startup with all precompiled solvers takes < 1 min (measure).
- Runs are **deterministic**: same knobs → same result (fixed seeds).
- Works in a current Chrome/Firefox at 1366×768 and up.

## 10. Changes needed in the existing code (`point-mass-mpc/`)

The current code is a solid base: model, OCP, obstacles as ellipses, the closed
loop, block-intrusion checks, metrics. To support the game we need:

1. runtime parameters for Q, R, obstacle ellipses, margin and model gain `g` (§9.3);
2. a solver cache for the allowed N values;
3. terminal velocity bounds on/off (Level 2);
4. a plant that differs from the model: gain `g_true` and a seeded wind (Levels 4, 5);
5. a re-plan interval `k`: apply stored plan inputs between solves (Level 5);
6. waypoint switching (Level 3);
7. the outcome logic of §4.4 (crash on block or wall checked between samples,
   budgets, time limit) and the metrics of §5.7;
8. the explanation rules of §10.1 (below), level JSON loading, run result JSON output;
9. a level-check script (§11).

### 10.1 Explanation rules ("What happened")
These are generated from run data. A first set:

| Trigger | Message template |
|---|---|
| controller failure near a wall/obstacle and `v²/(2a) > distance` | "At t = {t} s the ball was {d} m from {wall/obstacle} at {v} m/s; braking needs {b} m. Your horizon covered {T} s (≈ {T·v} m)." |
| controller failure, other | "The solver found no valid plan at t = {t} s (acados status {s}: {reason})." |
| time out with ball at rest near an obstacle | "The ball stopped {d} m from obstacle {j} with the target behind it: a local optimum. The horizon cannot see around it." |
| time out, ball moving slowly the whole time | "The ball never went faster than {v} m/s: your settings make moving expensive / the horizon too short to go faster safely." |
| crash, with prediction error > 0.2 m | "The plan predicted the ball at {p_pred}, it was at {p_real}: the model does not match the real ball." |
| crash in Level 5 with k > 1 | "Between re-plans the ball ran open-loop for {k·dt} s and the wind pushed it {drift} m off the plan." |
| energy budget exceeded | "Peak acceleration {a} m/s²: the input weight is low compared with the position weight, so the controller accelerates as hard as it can." |
| success with all weights scaled equally vs default | "Same result as the default: scaling Q, R, P together does not change the optimum." |

## 11. Acceptance criteria

The game is done when:
1. Levels 1, 2, 4 and 5 are playable end to end (briefing, tune, run, replay,
   result, stars), plus Level 3 if time allows.
2. For **every level**, an automated level check (like `verify.py`) confirms:
   - the default settings fail **with the intended outcome type**;
   - the stored reference solution passes, and reaches ★★★;
   - the run is deterministic (two runs give identical results).
3. The predicted plan is shown at every step of every replay.
4. Every failure shows a "What happened" message with numbers from the run.
5. The game starts with one documented command, and a classmate who has never
   seen it can finish Level 1 without help.
6. **Playtest:** at least 2 classmates play all levels. We record where they got
   stuck and fix the worst problem.

## 12. Plan (2 weeks, 2 people)

Split by layer so we rarely block each other: **A = backend / MPC**, **B = UI**.
Both of us design and calibrate levels.

| Days | A (backend) | B (UI) | Together |
|---|---|---|---|
| 1 | | | read this doc, decide the UI tech (§9.2), freeze the JSON formats (§9.4) |
| 2–4 | runtime parameters, solver cache for N, outcome logic, run-result JSON; serve a run for a level file | map view + playback from a **saved** run-result JSON (no backend needed), knob panel from the level file | |
| 5–6 | plant mismatch, wind, re-plan interval, terminal stop | result panel, plots with cursor, level select | first integration: Level 1 end to end |
| 7–8 | level-check script; calibrate Levels 1, 2, 4, 5 | test drive (L4), wind arrow and open-loop segment (L5), hints | Levels 1, 2, 4, 5 playable |
| 9–10 | explanation rules; waypoints (L3) | waypoint placing (L3), OCP panel | Level 3 or polish |
| 11 | | | **feature freeze**; playtest with 2 classmates |
| 12–13 | fixes | fixes | recalibrate pars, README / demo prep |
| 14 | | | buffer, presentation |

**If we fall behind, cut in this order:** OCP panel → Level 3 (or its
fallback mechanic) → plan history → solve-time plots → free mode. Never cut the
live plan display or the "What happened" messages: they are the point of the game.

## 13. Stretch goals (only if everything above is done)

- Level editor / sandbox (place blocks from 4 corners, start, target).
- "Real-time" level: a deadline per solve, where too-long solves are missed;
  RTI vs full SQP as a knob.
- Moving obstacle or moving target.
- RL / black-box tuning of the MPC parameters, compared with the player's
  hand-tuned score.

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A level's default doesn't fail the intended way, or no setting passes | level is meaningless | calibrate with headless scripts **before** building UI for it; the level check (§11) catches regressions |
| Solver behaves unexpectedly (non-convexity; we already saw SQP cycling, fixed with Levenberg–Marquardt damping) | random failures | failures end the run gracefully with a message; level checks run every level |
| Ellipse approximations close gaps or look wrong | confusing maps | design with ellipses visible (§4.3); split long walls into several blocks |
| Docker + browser setup trouble on a teammate's machine | lost days | test the one-command start on both laptops on day 2 |
| Runtime parameters in acados take longer than expected | blocks Levels 1, 4, 5 | fallback: recompile per *Run* for weights (slower, but works) while fixing it |
| Scope creep | not finishing | non-goals (§2) and the cut order (§12) |

## 15. Open questions

1. UI technology (§9.2): decide on day 1.
2. Do hints cost stars? Current answer: no.
3. Should entering an ellipse (not the block) count as a fail? Current answer: no,
   warning only (§4.4).
4. Level 3 mechanic: click-to-place waypoints or the toggle fallback?
5. Is the terminal weight P a knob anywhere? Current answer: no, fixed at 10·Q.
