# ControlQuest: Product Requirements Document

**Last updated:** 2026-11-19 (reduced scope: Level 4 "Heavy Ball" removed, Crosswind is Level 4)

Numbers marked **(calibrate)** are first guesses that must be
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

## 2. Goals 

1. **Teach by failure:** each level shows one MPC property through a failure the
   player can understand and fix.
2. **Make MPC visible:** show the plan, the constraints the solver sees, and why a
   run ended the way it did.
3. **Be finishable:** 4–5 polished levels in 2 weeks by 2 part-time people.
4. **Be honest about the controller:** every number shown (cost, solve time,
   iterations, constraint margins) comes from the real acados solver.

<!-- ### Non-goals (explicitly out of scope)
- RL / learning-based tuning (a possible stretch goal only, see §13).
- The player steering the ball directly (no keyboard driving mode).
- A level editor (could-have, only if everything else is done).
- Accounts, online leaderboards, multiplayer, sound, mobile layouts, 3D.
- Exact polygon constraints (we keep the ellipse approximation; see §4.3).
- Real-time streaming of the simulation (we compute first, then replay; §9.1). -->

## 3. Target players

Students who took the MPC course with us. We assume they know:
- receding horizon control, OCPs, cost weights Q / R / P, horizon N;
- terminal cost and terminal constraints, recursive feasibility;
- SQP, local optima, initial guesses, nonconvex constraints;
- model mismatch and disturbances.

Consequences for the design:
- We use course notation (Q, R, P, N, x_k, u_k) in the UI
- Explanations can be short and technical. We don't explain what an OCP is.
<!-- - The challenge comes from trade-offs, not from hidden information. The player
  should always be able to work out *why* something happened. -->
<!-- - A full playthrough should take **20–40 minutes**. -->

## 4. The world and its rules (same in every level)

### 4.1 The ball
- Point mass in 2D. State `x = [px, py, vx, vy]`, input `u = [ax, ay]`.
- <span style="color: red">Model used by the controller: double integrator with exact zero-order hold,
  `p+ = p + dt·v + ½dt²·g·a`, `v+ = v + dt·g·a`. `g` is the *model actuator
  gain* (1 in every level since the model-mismatch level was removed on 2026-11-19).</span>
- Sampling time `dt = 0.1 s` in every level (fixed, not a knob).
- Box limits `|ax|, |ay| ≤ a_max` and `|vx|, |vy| ≤ v_max`, set per level.

### 4.2 The "real" ball (plant)
The plant is simulated separately from the model, so levels can add:
- **actuator mismatch:** the real gain `g_true` could differ from the model's `g` (supported
  by the engine, used by no level since "Heavy Ball" was removed on 2026-11-19);
- **disturbances:** wind acceleration added to the plant (Level 4, Crosswind), generated
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
| **Budget exceeded** | a level budget is used up, e.g. the battery in Level 1 ("battery empty") or the solves in Level 4 (Crosswind). Checked after every step; **the run stops immediately**. | red, with which budget |

A controller failure **stops** the run. There is no fallback input. "No feasible
plan existed" is one of the lessons (Level 2), so we show it, not hide it.

Entering an **ellipse** but not the block is not a crash. It shows a yellow
"constraint violated" warning on the timeline. In practice the next solve usually
fails, which then ends the run as a controller failure.
*(2026-10-26: the ellipse constraints are soft with a large L1 penalty, so the solver
keeps returning plans; a plan that enters an ellipse by more than ~2 cm is treated as
invalid → controller failure. The timeline warning is not built yet.)*

## 5. Game structure and screens

### 5.1 Flow
`Title → Level select → Level intro → Level screen (tune → run → result) → (optional) Research
debrief → next level's intro`

- **Research debrief** (added 2026-11-19, reduced scope): one page per level with the research
  question, the scientific problem, why it matters, what the level showed (with the latest
  run's numbers and one of the level's existing visuals), two recent papers (checked
  references; links open only on click) and the limits of the level. Opened by "Insights" on
  the result card after any outcome, or by "Research background" on the intro (no run yet).
  It never blocks progress: stars and unlocking do not depend on it.

- **Level 0 "Hello, MPC"** (added 2026-11-17) is an optional tutorial before Level 1: a
  guided tour of the MPC loop, without stars (section 7).

- **Level intro** (added 2026-11-17), shown every time a level opens: the briefing
  (story), what the level teaches (the concept), how it teaches it (how the default
  controller fails and the ideas to fix it), what the player controls (each knob with its
  explanation, what stays fixed), the goal and the three star conditions, and the level's
  OCP at the default values with the parts that are new in this level highlighted. "Start
  level" opens the level screen; Back there returns to the intro (settings and the last
  run are kept while the player stays in the level).
- By default you start at Level 1. Each passed level unlocks the next.
- A "Free mode" toggle in the level select unlocks all levels, for demos and the
  course presentation.
<!-- - Best result per level (stars, best time) is saved locally in the browser. -->

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
- in Level 4 (Crosswind): wind direction and strength (arrow), and the plan segment executed
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
- **(2026-11-20) Built as the optional "Analysis" tab of the map tile**: two time-series plots
  per level of the latest run, sharing the replay's time cursor (AGENTS.md section 8 lists the
  plots and their data). The list below was the original plan and is only partly what was
  built (e.g. no separate input plots).
- Plots under the map share the playback cursor:
  - always: speed ‖v‖ with v_max, inputs ax and ay with ±a_max;
  - per level, one extra plot: cumulative energy with budget line (L1), distance to
    wall vs braking distance (L2), distance to the next waypoint (L3), cumulative number of solves with budget line
    (L4, Crosswind).
- Should-have: solve time and SQP iterations per step, so expensive moments are
  visible (e.g. sliding along an ellipse).

### 5.7 Result panel
After a run:
- outcome (§4.4) and **stars** (§6);
- metrics table with the level's pars: time to target, energy, number of solves,
  minimum clearance to blocks, mean/max solve time, max SQP iterations;
- **"What happened"**: 1–3 sentences generated from rules (§10.1) that explain the
  outcome with numbers from the run;
- buttons (as built): *Replay*, *Retry*, *Insights* (the Research debrief), *Next level* (only
  after a success, when the next level is unlocked).

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

There are four rated levels plus the tutorial Level 0 (2026-11-19: Level 4 "Heavy Ball" was
removed for time reasons and Crosswind moved from 5 to 4). Each table lists the map, the knobs, the default (failing)
settings, why they fail, the intended fixes, and what the level shows.

All coordinates in metres. Maps are first proposals **(calibrate)**.

**Priority (2026-11-19, reduced scope):** finish and polish these levels; no new gameplay
features (AGENTS.md section 8).

---

### Level 0: "Hello, MPC" (tutorial: the MPC loop) (added 2026-11-17)

**Concept:** model predictive control in one sentence: predict, optimise, apply the first
move, repeat. Measure the state → predict with a model → pick the lowest-cost input
sequence within the limits → apply only its first input → start again from the new
measurement.

**Briefing:** *"Meet your new co-pilot. Before you design controllers yourself, watch one at
work: step by step, the way it thinks."*

| Item | Value |
|---|---|
| Type | **tutorial**: optional, **no stars** (not counted in the total), always open, does not lock Level 1, never the suggested level in the level select ("Tutorial" tag on its tile). Rose accent, loop icon |
| Map | **small open field 20 m × 20 m** (agreed exception to the 50 m field, so the plans are easy to see), start (3, 8) **at rest** (2026-11-18; first version: moving up at 2 m/s, `start_velocity`), target (17, 10), a_max = v_max = 2, time limit 20 s |
| Locked | everything: q_p = q_v = r = 1, P = 10·Q, N = 30 (run ≈ 10 s, 100 solves; calibrated) |
| Knobs | **none** (2026-11-18): Level 0 only introduces MPC; changing N is Level 2's topic |
| Intro | as every level, plus a drawn **loop diagram** (1 Measure → 2 Predict → 3 Optimise → 4 Apply, "repeat every Δt") |
| Play screen | the run is computed automatically; the controls tile is a **guided tour** of 7 steps (You are not steering · ① Measure · ② Predict · ③ Optimise · ④ Apply the first input · ⑤ Repeat · Watch it run), ‹ Back / Next ›. The map highlights the step (ring on the measured ball; a faint fan of example predictions; the plan with its end x_N; the first input u₀; 1 s later, the first plan in grey behind the current one) and the OCP highlights the matching line (x₀ = x̂; the dynamics; the cost + limits). Then the replay plays to the end; the result card has no stars and "Replay tour" / "Next level ›"; the tile becomes **"Tour complete"** (a short summary, a tonal "Replay tour" and a coral "Next level ›"); no Run, Reset or Retry |
| Check | `engine_server/calibrate.py hello_mpc` (the run succeeds) |

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
| Time limit | 40 s (calibrated) |
| Budget | battery: energy `E = Σ dt·‖u_k‖² ≤ 5`; the run stops when it is empty (calibrated) |
| Unlocked knobs | `q_p` position weight (Q₁₁ = Q₂₂), `q_v` velocity weight (Q₃₃ = Q₄₄), `r` input weight (R = r·I); all log sliders 0.001 … 50 (team rule: max ≤ max(50, 3 × reference)) |
| Locked | N = 30, P = 10·Q, no obstacles |
| Default | q_p = 10, q_v = 1, r = 0.1: an aggressive controller (full acceleration and braking) |
| Why the default fails | it accelerates and brakes at full a_max (≈ 7.4 energy for the whole trip): the battery is empty at t ≈ 20.3 s, 0.5 m before the target |
| Intended fixes | lower q_p/r (and/or raise q_v) until braking is gentle; too gentle → time out (it creeps into the target too slowly). Calibration: far from the target the MPC always starts at full a_max, so ≈ 4 energy is spent on the first acceleration whatever the weights; the energy differences come from the braking/approach |
| ★★ time par | ≤ 30 s (calibrated) |
| ★★★ secondary par | energy ≤ 4.75 (calibrated). Reference: q_p = 0.1, q_v = 1, r = 1 → 26.8 s, 4.69. Check with `engine_server/calibrate.py price_of_speed` |
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
| Map | open field. Start (4, 25), target (48, 25), so the wall at x = 50 is 2 m behind the target (calibrated: at 4 m, N = 20 without the terminal stop still succeeded by overshooting towards the wall) |
| Limits | a_max = 1, v_max = 4 → braking from full speed: 4 s, 8 m |
| Time limit | 60 s (calibrated: long enough that "short horizon + terminal stop" can succeed slowly) |
| Unlocked knobs | horizon N ∈ {5, 10, 20, 30, 40, 60}; toggle **terminal stop** (`v_N = 0`) |
| Locked | q_p = 10, q_v = 1, r = 0.1 (Level 1's defaults), P = 10·Q (calibrated: gentler weights do not fail at N = 10) |
| Default | N = 10 (1 s), terminal stop off |
| Why the default fails | (calibrated) at t = 11.6 s the ball is 7.6 m from the wall at 4 m/s, braking needs 8 m, the plan sees ≈ 4 m: point of no return; at 13.0 s the OCP is infeasible → **controller failure** |
| Intended fix A | long horizon (N ≥ 40) → fast and safe, but expensive |
| Intended fix B | short horizon + terminal stop → always feasible, but slow: N = 10 + stop arrives after 49.9 s (★), N = 20 + stop after 25.1 s (★★★). Without the stop N ≤ 20 fails (N = 20 sees the wall exactly at the braking distance: no margin). Fix A (N ≥ 30, with or without stop): 16.6–19.3 s (★★) |
| ★★ time par | ≤ 27 s (calibrated) |
| ★★★ secondary par | N ≤ 20 (cheaper solves). Only N = 20 + terminal stop reaches it. Check: `calibrate.py brake_check` |
| Extra plot | "Brake check" under the map: wall ahead vs braking distance `v²/(2·a_max)` vs plan reach `N·Δt·v`, live during the replay; red after the point of no return |
| Teaching note | failure text names both numbers: "At t = 9.4 s the ball was 6.1 m from the wall at 4 m/s; braking needs 8 m. Your horizon covered 1.0 s (≈ 4 m)." |

Dropdown values for N are **precompiled solvers** (see §9.3), so switching N is instant.

---

### Level 3: "Dead End" (nonconvexity and local optima)

**Concept:** with obstacles the OCP is nonconvex. The MPC is a *local* planner with
a short horizon, so it can get stuck in front of an obstacle (at a stationary plan of the
nonconvex OCP). On this map, more foresight (horizons up to N = 150 were tested) did not get it
out; a higher-level plan (waypoints) does; this is how MPC is used in practice.

**Briefing:** *"The direct route looks open… it isn't. Two ideas to get the controller
out: let it look further ahead, or give it a route. Find out which one works."*

| Item | Value |
|---|---|
| Map | U-shaped trap that opens towards the start: back wall x ∈ [30, 33], y ∈ [15, 35]; arms y ∈ [32, 35] and y ∈ [15, 18], x ∈ [20, 33]. Start (5, 25), target (45, 25). Calibrated: **each wall is split into 2 blocks (6 blocks)**; with 3 long blocks the overlapping ellipses formed notches where even good routes got stuck |
| Limits | a_max = 2, v_max = 2 |
| Time limit | 45 s (calibrated) |
| Mechanic (2026-10-26) | the player **picks one fix** and tunes only its control; "Your experiments" keeps the best run per fix (outcome, time, ms per solve, stars). Fixes: **no fix** (default); **① longer horizon**: any whole N from 5 to 300 (typed or slider; a new N builds its solver once, a few seconds); **② waypoints**: up to **3 waypoints** by clicking on the map (drag to move, right-click to delete); ③ (better terminal cost / cost-to-go) was dropped on 2026-11-19 (reduced scope) |
| Locked | q_p = 1, q_v = 1, r = 0.1, P = 10·Q, margin 0.2 m; N = 30 except with fix ① |
| Default | no fix (N = 30, no waypoints) |
| Why the default fails | the ball drives into the U and stops 0.2 m before the back wall: the cost gradient points straight into the obstacle, the 3 s horizon sees no way around → **time out** (calibrated) |
| Fix ① result (calibrated) | **none of the tested horizons escaped** (an observation, not a proof): N = 30/60/100/150 all time out at (29.8, 25); mean solve time 1.3 → 3.0 ms (2026-11-19, machine-specific; docs/RESEARCH.md). SQP warm-started from the previous plan stayed on the same side of the wall |
| Intended fix | ② 1 waypoint above/right of the U (x ≥ 30, y ≥ 36), then the target; waypoints left of x ≈ 25 lead back into the top of the U (time out again) |
| Waypoint rule | the MPC reference is the next waypoint (position only, velocity reference = 0). Within the *switch radius* of 2 m, the reference jumps to the next waypoint, so the ball doesn't brake at each waypoint. Waypoints inside an ellipse are rejected when placed (game and engine). |
| ★★ time par | ≤ 28 s (calibrated: single good waypoints take 23.6–34 s) |
| ★★★ secondary par | ≤ 1 waypoint (so only fix ② reaches ★★★). Reference: fix ②, one waypoint at (35, 40) → 25.2 s. Check with `engine_server/calibrate.py dead_end` (also checks that fix ① with N = 150 times out) |
| Extra plot | distance to the current reference (shows switching) |
| Teaching note | on time out near an obstacle: "The ball stopped 0.2 m from the block at (32, 20) with the target behind it: stuck. Every solve returned (status 0) practically the same plan, a stationary point of the nonconvex OCP, so the ball no longer moves. The horizon (3 s) cannot see around the obstacle…" |
| Solver note | obstacle constraints are **soft** (L1 + small quadratic slack penalty, scaled by dt like the stage cost; not proven exact, measured in docs/RESEARCH.md) since 2026-10-26: hard ellipse constraints made the QP solver fail whenever braking at a_max to stop at an ellipse. Crashes are still checked against the real blocks. |

**Cheaper fallback if we are short on time:** replace click-to-place with 2–3
predefined waypoint candidates the player toggles on and off.

**Alternative mechanic (not planned):** the player sketches a path that becomes
the solver's initial guess. More "MPC-pure", but riskier: the warm start only
affects the first solves, so the effect may vanish. Only try this if waypoints
are done early.

---

### (removed) Level 4: "Heavy Ball"

Removed on 2026-11-19 (reduced scope). It taught model mismatch (a hidden actuator gain
`g_true = 0.6`, a test drive to identify it, an obstacle margin). Its last calibration
(`a7ab364`): with the wrong model (`g = 1`) every margin from 0 to 3 m failed, so only the
model fix worked. The code is in the git history.

---

### Level 4: "Crosswind" (feedback: why we re-plan) (Level 5 until 2026-11-19)

**Concept:** MPC is feedback because it re-plans from the measured state. If you
re-plan rarely, the controller is effectively open-loop between solves and
disturbances push the ball off its plan. Re-planning costs computation, so it's a
trade-off.

**Briefing:** *"It's windy. You have a limited compute budget: every re-plan uses
one solve. Get through the gap."*

| Item | Value |
|---|---|
| Map | two square blocks with a gap: (22, 11)–(28, 17) and (22, 23)–(28, 29) (calibrated); the straight line y = 25 runs into the upper block, so the ball must pass through the gap (y ≈ 17–23) while the wind (+y) pushes it towards the upper block. Start (5, 25), target (45, 25). |
| Plant | wind acceleration in +y: constant 0.3 m/s² plus gusts, piecewise constant for 1 s each, uniform in [−0.6, 0.6] m/s², fixed seed 7 (calibrated) |
| Limits | a_max = 2, v_max = 2 |
| Time limit | 35 s (calibrated) |
| Budget | max **60 solves** for the run (calibrated); the run stops when they are used up. Re-planning every step uses them up after 6 s |
| Unlocked knobs | re-plan interval `k` ∈ {1, 2, 3, 5, 10, 20} (between re-plans the controller applies the next inputs of the last plan, open-loop); obstacle margin 0 … 3 m |
| Locked | q_p = 2, q_v = 0.5, r = 0.05, P = 10·Q, N = 30 |
| Default | k = 1 (re-plan every sample), margin 0.1 m |
| Why the default fails | the most feedback, but the 60 solves are used up after 6 s → **budget exceeded** |
| What the player discovers (measured 2026-11-19, docs/RESEARCH.md) | k = 1, 2, 3 → budget used up; with margin 0.1 m, k = 5, 10, 20 crash into a block (deviation from the prediction up to 1.5 m between re-plans); with margin 0.3 m, k = 5 → ★★ (57 solves), **k = 10 → ★★★ (28.2 s, 29 solves; the reference)**, k = 20 still crashes |
| ★★ time par | ≤ 30 s (calibrated) |
| ★★★ secondary par | ≤ 35 solves (calibrated) |
| Extra plot | built as a compute-budget bar under the map; the deviation from the prediction in force (measured up to and including the moment a plan is replaced; engine 0.14.0) is a result row |
| Map extra | wind arrow; the open-loop segment of the plan being executed is drawn solid, the rest dashed |
| Teaching note | "Between re-plans the ball ran open-loop for 2.0 s and the wind pushed it 1.8 m off the plan." |

## 8. Knob reference (all levels)

| Knob | Symbol / meaning | Range | Type | Levels | Needs a new solver? |
|---|---|---|---|---|---|
| Position weight | `q_p`: Q₁₁ = Q₂₂ | 0.001 … 50 | log slider | 1 | no (runtime) |
| Velocity weight | `q_v`: Q₃₃ = Q₄₄ | 0.001 … 50 | log slider | 1 | no |
| Input weight | `r`: R = r·I | 0.001 … 50 | log slider | 1 | no |
| Horizon | `N`, T = N·dt | {5, 10, 20, 30, 40, 60} | dropdown | 2 | precompiled per value |
| Horizon (fix ①) | `N`, T = N·dt | 5 … 300, whole numbers | typed / slider | 3 | built once per new N (a few seconds) |
| Terminal stop | `v_N = 0` | on/off | toggle | 2 | no (terminal bounds) |
| Waypoints | intermediate references | 0–3 | map clicks | 3 | no |
| Obstacle margin | added to each semi-axis | 0 … 3 m | slider | 4 | no (parameters) |
| Re-plan interval | `k` steps between solves | {1, 2, 3, 5, 10, 20} | dropdown | 4 | no |

Fixed in every level: `dt = 0.1 s`, terminal weight `P = 10·Q` (not a knob, to keep
the knob count small), solver settings.

## 9. Technical requirements (only what the design depends on)

### 9.1 Compute first, then replay
A run is computed completely by the backend, typically 100–400 steps at ~1 ms per
solve, so well under a second. The result is then sent to the UI and played back.
This avoids real-time streaming and makes pause, scrub and replay trivial. The
"compute budget" in Level 4 (Crosswind) counts solves; it does not use wall-clock time.

### 9.2 Where it runs
acados only runs in our Docker image (Linux), and a GUI window cannot easily be
shown from inside that container. So the game is split in two processes:

```
 Host (Windows / macOS / Linux)                Docker container
┌──────────────────────────────┐   HTTP on    ┌──────────────────────────────┐
│ UI: map, knobs, playback,    │  localhost   │ small Python server          │
│ plots, result screen         │ ───────────▶ │  + point-mass-mpc (acados)   │
│ (browser page or desktop app)│  run request │  computes the whole run      │
│                              │ ◀─────────── │                              │
│                              │  run result  │                              │
└──────────────────────────────┘    (JSON)    └──────────────────────────────┘
```

- The **backend** (Python, the existing `point-mass-mpc` code plus a small HTTP
  server) runs **in the container**, with its port mapped to the host (e.g.
  `-p 8000:8000`).
- The **UI** runs **natively on the host** and talks to the backend only through
  the run request / run result formats of §9.4. Because of "compute first, then
  replay" (§9.1), one Run is one request and one response; all animation is local.
- The UI can be developed and tested **without Docker**, against saved run-result
  JSON files.
- Starting the game must be **one command or script** that starts the container
  and the UI (documented in the README).

**Decision needed on day 1:** the UI technology. Options:

| Option | What it is | Good at | Weak at | Player setup |
|---|---|---|---|---|
| (a) Web page | small HTTP server + hand-written HTML/JS canvas page, opened in the browser | full control over map drawing and animation; nothing to install for players | needs JavaScript; plots and widgets via JS libraries | Docker + a browser |
| (b) Dash / Plotly | Python-only web UI framework, opened in the browser | Python only; plots and standard widgets built in | custom map interaction (placing/dragging waypoints, smooth playback) is clunky | Docker + a browser |
| (c) **PySide6** (+ `pyqtgraph`) | Qt desktop app in Python | Python only; sliders, dropdowns, toggles, text and layout built in; fast plots with a moving cursor (`pyqtgraph`); map with clickable/draggable items (`QGraphicsView`); smooth playback (`QTimer`) | "game feel" (effects, juice) is not natural; one more program to start | Docker + Python with `pip install PySide6 pyqtgraph` |
| (d) **pygame** (`pygame-ce`) | game library in Python, drawing everything by hand | game loop, animation and drawing are simple and feel like a game; a first prototype already exists on branch `dev` (grid, click-to-place target, sliders) | no widgets or plots: sliders, dropdowns, toggles, text panels, result tables and plots must be written by hand (or with `pygame_gui`, which is more limited) | Docker + Python with `pip install pygame-ce` |

Notes for the decision:
- About 80% of the UI in this document is application UI (knob panel, plots,
  result panel, hints, level select). Only the map is "game" graphics. This
  favours (c). With (d), budget extra days for hand-made widgets and plots, or
  cut plots to one simple hand-drawn speed plot.
- Prefer the maintained community edition `pygame-ce` over the original `pygame`
  if we choose (d). Check that it installs on both laptops' Python versions first.
- The `dev` prototype is small (~250 lines). Switching it to (c) costs about half
  a day, so the existing code shouldn't be the deciding factor.
- Whatever we choose, the UI must use **world coordinates** (continuous, metres,
  y pointing up) and convert to pixels with the **same scale in x and y**, so
  ellipses and plans look right.

Pick the option that matches what we already know; the rest of this document
doesn't depend on it, as long as the UI talks to the backend only through §9.4.

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
  iterations, whether a solve happened this step (Crosswind), current reference;
- events: waypoint reached, ellipse entered, crash with its position, failure;
- metrics, outcome, stars, explanation strings.

The existing `ClosedLoopResult` already holds most of this.

### 9.5 Non-functional
- One Run, including the response, takes < 2 s for every level.
- Startup with all precompiled solvers takes < 1 min (measure).
- Runs are **deterministic**: same knobs → same result (fixed seeds).
- Works at a window size of 1366×768 and up (in a current Chrome/Firefox for
  options (a)/(b); on Windows and macOS for options (c)/(d)).

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
| time out with ball at rest near an obstacle | "The ball stopped {d} m from obstacle {j} with the target behind it: stuck (a stationary plan). The horizon cannot see around it." |
| time out, ball moving slowly the whole time | "The ball never went faster than {v} m/s: your settings make moving expensive / the horizon too short to go faster safely." |
| crash, with prediction error > 0.2 m | "The plan predicted the ball at {p_pred}, it was at {p_real}: the model does not match the real ball." |
| crash in Crosswind with k > 1 | "Between re-plans the ball ran open-loop for {k·dt} s and the wind pushed it {drift} m off the plan." |
| energy budget exceeded | "Peak acceleration {a} m/s²: the input weight is low compared with the position weight, so the controller accelerates as hard as it can." |
| success with all weights scaled equally vs default | "Same result as the default: scaling Q, R, P together does not change the optimum." |

## 11. Acceptance criteria

The game is done when:
1. Levels 1–4 are playable end to end (briefing, tune, run, replay, result, stars), plus
   the tutorial Level 0.
2. For **every level**, an automated level check (like `verify.py`) confirms:
   - the default settings fail **with the intended outcome type**;
   - the stored reference solution passes, and reaches ★★★;
   - the run is deterministic (two runs give identical results). *(Not part of `calibrate.py`;
     checked by hand on 2026-11-19, docs/RESEARCH.md.)*
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
| Docker + UI setup trouble on a teammate's machine (container port, Python/UI library install) | lost days | test the one-command start on both laptops on day 2 |
| Runtime parameters in acados take longer than expected | blocks Levels 1, 4, 5 | fallback: recompile per *Run* for weights (slower, but works) while fixing it |
| Scope creep | not finishing | non-goals (§2) and the cut order (§12) |

## 15. Open questions

1. UI technology (§9.2): decide on day 1.
2. Do hints cost stars? Current answer: no.
3. Should entering an ellipse (not the block) count as a fail? Current answer: no,
   warning only (§4.4).
4. Level 3 mechanic: click-to-place waypoints or the toggle fallback?
5. Is the terminal weight P a knob anywhere? Current answer: no, fixed at 10·Q.
6. ~~Level 3 with three fixes~~: decided 2026-11-19 (reduced scope): two fixes (longer
   horizon, waypoints); fix ③ is dropped. Spike results stay in AGENTS.md section 6.
