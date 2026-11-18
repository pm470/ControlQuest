# AGENTS.md: context for AI coding agents working on ControlQuest

Read this first. It tells you what the project is, how to run it, how the code is
organised, **the decisions and remarks the team has already made** (section 8), the
**UI design rules, structure and content** (section 10: follow the design rules for any
GUI change, so every screen and level looks the same) and **how the team likes to work with an
agent** (section 11). Follow those remarks unless a team member explicitly changes them or gives opposing instructions, in that case point out the different oppinion and let the user confirm it,
and **add new remarks to section 8** (dated) when the user gives them, so every agent
stays in sync.

More detail: [`docs/PRD.md`](docs/PRD.md) (the game design, "product requirements")
and [`game/README.md`](game/README.md) (code map, workflow, how to add a level).

---

## 1. The project in one paragraph

ControlQuest is a puzzle game for students of an MPC (model predictive control)
course. A ball must get from a start to a target on a 50 m × 50 m field. The player
does **not** steer the ball; the player **designs the MPC controller** (cost
weights, horizon, margins, model parameter, waypoints, re-planning rate), presses
**Run**, and watches the controller succeed or fail, with the MPC's predicted plan
drawn live. Each level is built so the default controller fails in one specific
way, and the fix is one MPC concept. The MPC is solved with **acados** (Python
interface `acados_template`) and **CasADi**.

## 2. Team and constraints

- Two students (repo owners on GitHub: `Chris-tiee` and `pm470`), part-time.
  **About 2 weeks** total, starting around 2026-10-19. Keep the scope small.
- Players are classmates from the MPC course: use course notation (Q, R, P, N,
  x_k, u_k); explanations can be short and technical.
- Planned: 5 levels (PRD section 7). Levels 1, 2, 4, 5 must-have; Level 3 should-have.
  Plus Level 0 "Hello, MPC" (added 2026-11-17): an optional tutorial without stars.
- **RL is out of scope for now** (stretch goal only, if time is left at the end).

## 3. Repository map

```
ControlQuest/
├── AGENTS.md            this file (CLAUDE.md just imports it)
├── README.md            short project description + pointers
├── docs/PRD.md          game design: rules, screens, levels, data formats, plan
├── game/                THE GAME (all current work)
│   ├── README.md            detailed code map and workflows
│   ├── requirements.txt     host-side Python deps (PySide6-Essentials, matplotlib)
│   ├── run_game.py          start the game window
│   ├── level_data/          one JSON per level, read by BOTH game and engine
│   ├── controlquest/        the game window (PySide6, runs on the host)
│   └── engine_server/       the MPC engine (runs in Docker, has acados)
└── point-mass-mpc/      earlier learning sandbox (standalone acados example).
                         NOT used by the game; kept as reference. Don't build on it.
```

Branches: as of 2026-10-25 the active work is on branch **`first_setup`** (check
`git log` / `git branch -a` for newer state). Branch `dev` holds an early **pygame**
prototype with a separate, unrelated git history; the team switched to PySide6
(section 8), so `dev` is superseded and should not be merged as-is.

## 4. How to run everything

The game is **two processes**: the MPC engine (in Docker, because acados is only
installed in the course Docker image) and the game window (normal Python on the host).
They talk over HTTP on `http://127.0.0.1:8000`.

### Prerequisites
- **Docker Desktop**, running, with the course image, built from the `Dockerfile` of the
  course repository `mpcrl26-exercises` (Python 3.11, acados, CasADi, NumPy). VS Code
  names it `vsc-mpcrl26-exercises-<hash>`, and **the hash is different on every
  computer**: the start scripts find the image automatically (first local image named
  `vsc-mpcrl26-exercises-*`); `CONTROLQUEST_IMAGE` overrides it. Check with `docker images`.
- **Python 3.10+** on the host (tested with 3.14 on Windows 11).

### Start the engine (terminal 1, from the repository root)
```powershell
.\game\engine_server\start_engine.ps1     # Windows PowerShell
./game/engine_server/start_engine.sh      # macOS / Linux / Git Bash
```
It mounts the repo at `/workspace`, compiles the acados solver (~2 s, generated C
code goes to `game/engine_server/build/`, gitignored) and prints
`listening on 0.0.0.0:8000`. Each run prints one line. Stop with Ctrl+C.
**Restart it after any change to engine code or level JSON files.**

### Start the game (terminal 2)
```powershell
cd game
python -m venv .venv          # first time
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_game.py
```
The title screen shows "MPC engine online" when the engine answers. Menus work
without the engine; pressing Run then shows a clear "engine offline" message.

### Useful commands
- Check/tune a level without the UI (inside the container, e.g. via
  `docker run --rm -v "<repo>:/workspace" -w /workspace/game/engine_server <image> python calibrate.py price_of_speed`):
  `python calibrate.py <level_id>` (checks), `--sweep` (table), `q_p=0.3 r=1` (one run).
- Environment variables: `CONTROLQUEST_DEV=1` (dev buttons), `CONTROLQUEST_ENGINE_URL`,
  `CONTROLQUEST_IMAGE`, `CONTROLQUEST_PORT`.
- Git Bash + Docker on Windows: prefix `MSYS_NO_PATHCONV=1` and pass Windows paths
  (`cygpath -w`). The repo path contains spaces (OneDrive): always quote paths.

## 5. Architecture (how a Run works)

1. `controlquest/gameplay/level_play_widget.py` sends `RunRequest(level_id, knobs)`
   via `controlquest/engine/client.py` (async HTTP POST `/run`).
2. `engine_server/server.py` → `runner.run_level` → `level_rules/<level>.run`:
   loads `level_data/<level>.json`, maps knobs to Q, R, P, loads them into a
   **cached, already compiled solver** (`mpc/controller.py`, `SolverCache`; one
   solver per problem shape (N, dt); weights/bounds/target/model gain are runtime
   values, no recompiling).
3. `mpc/closed_loop.simulate`: measure → solve OCP → apply first input → move the
   "real" ball (plant, separate from the model) → repeat, until success / time out /
   controller failure / crash / the level's stop rule (Level 1: battery empty).
4. The level rules compute metrics, stars and "what happened" sentences; the server
   returns a `RunResult` JSON with every state and every predicted plan.
5. The game **replays** it ("compute first, then replay"): `playback.py` is the clock,
   `map_view.py` draws ball/trail/dashed plan, the level file updates its extras
   (battery bar), `result_panel.py` shows the result card, `GameState` saves stars.

Contract between the two sides: `controlquest/engine/protocol.py` ↔
`engine_server/level_rules/common.py` + `server.py`, plus the level JSON files.

## 6. Status (2026-11-17)

- Done: menus (title with animation, level select with stars/locks/free mode, how
  to play, settings), engine server, MPC package, **Level 1 "The Price of Speed"
  fully playable** (calibrated; `calibrate.py price_of_speed` passes), OCP shown as
  typeset math, battery bar, result card, hints, MPC-solve selector, solver info card,
  responsive layout.
- Done (2026-10-26, branch `level3to4`): **obstacles in the engine** (up to 6 blocks per
  level, soft ellipse constraints, block crash check) and **Level 3 "Dead End"**
  playable: click-to-place waypoints, blocks + ellipses + waypoints on the map
  (`calibrate.py dead_end`). Since 2026-10-26 the player **picks a fix** (no fix /
  ① longer horizon N ∈ {30, 60, 100, 150} / ② waypoints) and compares them in
  "Your experiments"; fix ③ is still a TODO (below). Engine v0.5.0.
- Done (2026-11-03): **Level 2 "Brake Check"** playable (horizon dropdown, terminal-stop
  switch, brake-check gauge; `calibrate.py brake_check`). Levels 4 and 5 are built too
  (branch `level3to4`, `calibrate.py heavy_ball` / `crosswind`). Engine v0.9.0.
- Done (2026-11-14, branch `gui`): **UI redesign** on all screens and levels (design rules
  in section 10; borderless tiles with lips, three-tile level screen, knob colours in the
  OCP, new level select). Game-side only: engine unchanged (still v0.9.0).
- Done (2026-11-17, branch `gui`): **level intro** before every level (`gameplay/level_intro.py`,
  `LevelInfo.teaching` + `LevelInfo.intro`; section 10). Game-side only.
- Done (2026-11-17, branch `gui`): **Level 0 "Hello, MPC"**, an optional tutorial (guided tour
  of the MPC loop, no stars; `levels/level_0_hello_mpc.py`, `level_data/hello_mpc.json`,
  `level_rules/hello_mpc.py`, `calibrate.py hello_mpc`). Engine v0.10.0 (new level id).
- Not yet: speed/acceleration plots (PRD 5.6),
  saving progress to disk (progress resets on restart, intentionally for now).
- Next planned work: the MPC side of levels 2, 4, 5 (horizon N per level, terminal
  constraint, model gain, wind, re-plan interval); obstacles are already in place.

**TODO (on hold since 2026-10-26): fix ③ of Level 3 (a better terminal cost / cost-to-go).**
The pick-a-fix mechanic is built with fixes ① and ② (fix selector, N dropdown, comparison
table); ③ is missing. Adding it: one entry in `level_data/dead_end.json` "fixes", a branch
in `level_rules/dead_end.py`, its controls in `levels/level_3_dead_end.py` (`_on_fix`).
Plan: `~/.claude/plans/now-i-had-imagined-wondrous-spring.md` (on pm470's machine).
Feasibility spike results (engine only, default map):
- ① **Longer horizon N**: never escapes. N = 30/60/100/150 all time out at (29.8, 25);
  mean solve time 0.95 → 2.67 ms (max 84 ms), run 1.0 → 2.9 s. Lesson: foresight
  doesn't fix a local optimum; SQP with a warm start stays in its homotopy class.
  Built as fix ① (it is the "doesn't work" lesson).
- ② **Waypoints**: built as fix ②, 23.6–34 s with one good waypoint.
- ③ **Better terminal cost**, as first planned (smooth RBF fit of the cost-to-go as a
  NONLINEAR_LS terminal cost, runtime weights): **not viable**. 1 of ~40 settings
  escaped (q_p = 1, no straight-line terminal pull, w_V = 1: 23.4 s), but 20–200 ms
  per solve, QP failures, 5–90 s runs. Every smooth fit (11×11/σ4, 16×16/σ3,
  21×21/σ2.5, also with "ridge" data inside the walls) has a false minimum at the trap:
  the true cost-to-go jumps ~30 m across the 3 m wall (the RL-critic problem).
- ③ **Alternative that works** (tested, not built): exact cost-to-go D(p) by Dijkstra
  around the ellipses (0.03 s), MPC reference = point L metres ahead on the descent
  path of D (no solver change). L = 1 m: time out (creeps); **L = 2–8 m: success,
  23.3 s, 1.5 ms/solve**; L ≥ 12 m: time out (reference past the corner, trapped
  at (30, 14)). Open decision: build ③ this way, or keep the terminal-cost version.
- Code already in the repo for it: `engine_server/mpc/value_function.py` (Dijkstra
  grid cost-to-go + RBF fit; **not used yet**).

## 7. Rules for agents working in this repo

- **Never commit or push** (not even after asking): the team members commit themselves.
  When a change is done, **suggest a commit message** instead. Work on a feature branch;
  never rewrite shared history.
- **Never claim something works unless you ran it.** acados only runs in Docker: test
  engine code there (see section 4). If Docker is not available, say so.
- Keep the split: one file per concern (two people work in parallel; avoid merge
  conflicts). Screens never import each other; they navigate with `self.go(ScreenId...)`.
- **No colours/sizes in screens**: use `controlquest/ui/theme.py` and stylesheet roles
  (`label(text, "heading")`, `Button(text, variant="primary", scale="large")`).
- **Level numbers live only in `game/level_data/*.json`.** MPC code in
  `engine_server/mpc/` must not know about levels; game rules go in `level_rules/`.
- Change both sides of the contract together (`protocol.py` ↔ `level_rules/common.py`),
  and **bump the engine version** (`VERSION` in `engine_server/server.py` and
  `ENGINE_VERSION` in `controlquest/engine/protocol.py`) so the game can warn
  "MPC engine outdated: restart it" when someone runs an old engine.
- After changing a level: run `calibrate.py <level>` (default must fail as intended,
  reference must reach 3 stars, knob ranges must follow the rule in section 8).
- UI must stay usable down to **900×560** window size (see gotchas).
- Update `game/README.md`, `docs/PRD.md` and **this file** when you change behaviour.

## 8. Team decisions and remarks (append new ones, with date)

**Game and scope**
- (2026-10-19) `docs/PRD.md` is the base document the game is built against. Numbers
  marked "(calibrate)" are guesses until checked with real runs. Parts of the PRD the
  user has **commented out** (`<!-- ... -->`) are dropped (e.g. saving progress locally).
- (2026-10-19) Player = control engineer, not the driver. 4–5 levels, each teaching
  one MPC concept by failure. RL only as a late stretch goal.
- (2026-10-21) Progress (stars, unlocks) is kept **in memory only** for now; it resets
  when the game closes (`core/game_state.py` is the only place to change for saving).
- (2026-10-21) Stars per level (PRD 6): ★ reach the target; ★★ also within the time par;
  ★★★ also the level's second par. Level N unlocks when level N−1 has at least ★.
  "Free mode" (switch in the level select) unlocks all levels for demos.
- (2026-10-19) Workspace 50 m × 50 m, start/target scaled accordingly. (2026-11-17: the
  tutorial Level 0 is the one agreed exception, 20 m × 20 m; see below.)
- (2026-10-22) Level 1 battery (energy budget): **the run stops immediately when the
  budget is used up** (outcome `battery_empty`), it does not just fail at the end.
- (2026-10-22) Level 1 numbers were calibrated with real runs (PRD guesses were not
  feasible): time limit 40 s, battery 5, ★★ ≤ 30 s, ★★★ also energy ≤ 4.75;
  reference q_p = 0.1, q_v = 1, r = 1. Far from the target the MPC always starts at
  full acceleration (~4 energy), so weights mainly change braking/approach.

- (2026-10-25) Level 3 is built now, before the must-have Levels 2, 4, 5 (its obstacle
  support is reused by Levels 4 and 5). Waypoints are **placed by clicking on the map**
  (drag to move, right-click to delete), not the PRD's toggle fallback.
- (2026-10-26) Level 3 presents the trap with **fixes the player picks one at a time
  and compares** in a table ("Your experiments"); stars + the comparison show "which
  works better". Built now: ① longer horizon, ② waypoints. ③ (better terminal cost /
  cost-to-go) is **on hold** (TODO in section 6); it must use runtime parameters only
  (one OCP recipe, see below). ★★★ stays "≤ 1 waypoint" (only fix ② can succeed).
- (2026-11-03) Level 2 calibrated (PRD 7): target **2 m in front of the wall** (x = 48), weights
  locked at Level 1's defaults, t_limit 60 s, ★★ ≤ 27 s, ★★★ also **N ≤ 20**. The user rejected an
  artificial "≥ 3 m from the wall" star rule: the terminal stop must be *needed*, so the map makes
  N = 20 without it fail (controller failure); only N = 20 + stop gets ★★★ (25.1 s). Default
  N = 10 without stop fails; N = 10 + stop succeeds slowly (★, "safe but slow"); N ≥ 30 gets ★★.
- (2026-11-03) New knob type `"scale": "toggle"` (on/off switch, value 1/0, `"choices": [0, 1]`)
  in `knob_panel.py`; the controller's `set_terminal_stop(on)` sets v_N = 0 at runtime
  (`set_bounds` resets it, so no other level inherits it). `calibrate.py` supports
  `checks.cases` (more expected outcomes/stars per level).
- (2026-10-26) The knob-range rule (max ≤ max(50, 3 × reference)) is for weights only;
  discrete knobs with `"choices"` (e.g. horizon N) are exempt (`calibrate.py`).

**MPC**
- (2026-10-19) Obstacles: a block is given by 4 corners; the solver avoids the
  **minimum-area ellipse containing the corners**, `(p−c)ᵀE(p−c) ≥ 1`. No min/max
  in constraints (keeps the NLP smooth). Crashes are checked against the real block.
- (2026-10-19) With obstacles, SQP uses Levenberg–Marquardt damping (1e-2); merit
  backtracking performed much worse.
- (2026-10-22) One OCP "recipe" (`mpc/ocp.py`), several compiled solvers cached per
  problem shape; level differences are runtime numbers or plant-side (wind, model
  mismatch), not separate solvers.

**Working with agents**
- (2026-11-17) **Agents never commit or push**; the user always commits themselves. After a
  change, agents only recommend a commit message (section 7).

**Architecture / tooling**
- (2026-10-21) UI in **PySide6** (not pygame, not web). Game window on the host,
  MPC engine in Docker, connected by HTTP. Running PySide inside Docker was
  considered and rejected (display forwarding, fonts, macOS issues).
- (2026-10-21) Code divided into many small files by concern so both teammates can
  work without merge conflicts; registries are one line per entry.
- (2026-10-22) The engine prints one line per run and does **not** log the game's
  5-second health checks (they flooded the terminal).

**UI and content**
- (2026-10-21) Look: cute, simple, user-friendly (warm cream background, rounded
  cards, coral primary colour, the blue ball mascot, stars). Keep it simple for the user.
- (2026-10-25) **Knob (slider) ranges**: weights should not go above **50** in Level 1.
  General rule for all levels: a knob's max is **at most 3 × the weight of the
  reference ("perfect") MPC solution, but the range always reaches at least 50**,
  i.e. `max ≤ max(50, 3 × reference)`. `calibrate.py` checks this automatically.
- (2026-10-25) **The OCP must be shown clearly, as typeset math** (not plain text):
  a dedicated "The OCP your MPC solves" card rendered with matplotlib mathtext
  (`controlquest/ui/math_render.py`, `gameplay/ocp_card.py`), placed prominently
  next to the knobs (own column on wide windows). Use p★ / x★ (subscript star) for
  the target, matching the star on the map. Each level provides its OCP via the
  `ocp_spec()` hook of `LevelPlayWidget`.
- (2026-10-25) **Choose an individual MPC solve** (since 2026-11-14: "‹ k /n ›" inside the
  replay well, number typeable): under the replay bar there is an
  "MPC solve ‹ k › of n" selector (`gameplay/solve_selector.py`). Picking a solve
  pauses the replay at that solve's time so the map shows exactly the plan computed
  in that solve; while playing, the selector follows the replay.
- (2026-10-25) **Solver info card under the OCP card** (`gameplay/run_info_card.py`;
  since 2026-11-14 shortened to four numbers + one "Whole run" line, see below):
  for the selected solve: optimal cost J*, solve time, SQP iterations, acados status;
  for the whole run: number of solves, solve time (avg/max/total), iterations,
  closed-loop cost, engine compute time. The engine sends per-solve `costs` and
  `status` in the trajectory and these statistics in `metrics`.
- (2026-10-25) Solver info labels: **"Plan cost J*"** = optimal value of the selected
  solve's OCP (predicted cost over its horizon + terminal cost), **"Total cost (closed
  loop)"** (shown as "Total cost", tooltip explains) = cost of what actually happened over the whole run. Missing values are shown
  as "–" (never as fake zeros), with a hint to restart an outdated engine.
- (2026-10-25) **Knob values can be typed**, not only set with the slider
  (`gameplay/knob_panel.py`): each knob has a value field; Enter/leaving the field applies
  the exact typed value (clamped to the knob's range, invalid text rejected, comma or
  scientific notation accepted) and moves the slider. The slider itself gives round
  values (2 significant digits). Applies to all knobs of all levels.
- (2026-10-25) Level layout (wide window): map + level extras (e.g. battery) + replay
  bar + solve selector on the left; OCP card + solver info in the middle; goal, knobs,
  Run, hints on the right. Everything important must be visible without scrolling at
  ~1280×800 logical pixels; on narrow windows the middle column moves under the knobs.
- (2026-11-14) **UI redesign: "feel like a real game, no AI slop".** The user compared
  three sketches (A Paper Route, B Night Lab, C Tabletop; canvas "ControlQuest UI
  directions" on claude.ai) and picked a mix. The result is the **design rules in section 10**:
  follow them on every screen and in every level. In short:
  - **Colours and background stay as they were** (warm cream + dot grid, coral, blue ball,
    yellow star); the user rejected the sage green of sketch C.
  - **Rounded, borderless tiles that stand on a soft lip** (no outlines anywhere, only
    soft fills); inside a tile, tonal **wells** and spacing, never a card in a card.
    Few elements; no extra boxes.
  - **Level screen = three tiles** (sketch C): map tile | OCP + solver tile | controls tile.
  - **Map tile** (exactly like the user's screenshot of sketch C): a soft board without
    outline, grid every 5 m, **axis numbers every 10 m with ONE shared "0" at the
    origin**, a "|v| = … m/s" pill on the map (the time is in the replay bar); under the
    map the level extras (battery etc.), then ONE replay well: ▶ · scrubber · time ·
    speed chip (click cycles 1×/2×/4×/8×) · "‹ k /n ›" MPC solve stepper.
  - **OCP + solver tile**: the OCP keeps the current matplotlib/Computer Modern font;
    under it "This solve" as four big numbers (plan cost J*, solve time, SQP iterations,
    acados status) and ONE "Whole run" line (solves · avg ms · total cost; max time,
    iterations and engine time in its tooltip). The user said this is enough: this
    replaces the longer Solver info list of 2026-10-25.
  - **Knob colours** (from sketch A): every knob has a colour (`theme.KNOB_COLORS`, by its
    order in the level file); its symbol chip, its slider AND its part of the OCP
    (`\knob{name}{...}` in `ocp_spec()`) use it, so the player sees which part of the
    math a knob changes. Every new level must mark its knobs in its OCP this way.
  - **Controls tile** (sketch C): "Goal" (coral eyebrow) + goal text, the controls title
    (eyebrow) + knobs (chip, name, typed value, coloured slider), Reset + a wide Run ▶,
    the status line, level sections (e.g. "Your experiments"), and at the bottom
    "Stuck?" with a "Show hint k/3" link.
  - **Level select = sketch C** in the current colours: chunky tiles with the accent-colour
    top (big number + level icon), title, topic, stars; the next level to play is lifted,
    ringed and has a Play pill; locked tiles are muted with a lock. The header has the
    same back button as every screen.
- (2026-11-14) **The ball mascot is the flat ball of sketch C** (flat blue disc, soft
  highlight, dark dot eyes with a shine, pink blush, small smile; no gradient, no white
  eyeballs), drawn by `painting.draw_ball` everywhere (map, title, how to play, icon).
  **No ball on the level select** (the user does not want it above any level tile).
- (2026-11-17) **Level intro before every level.** Picking a level (level select or "Next
  level ›") opens its intro, **every time**; "Start level ▶" opens the play screen. Back on
  the play screen → the intro; Back on the intro → the level select. The play screen keeps
  its state (knobs, last run, Level 3's experiments) while the player stays in the level;
  leaving the level or opening another starts fresh. Layout: **two tiles, one page**:
  - left ("learn"): story quote, "What you learn" (`concept`), "How this level teaches it"
    (`teaching`), "What you control" (one line per knob: chip + name + the knob's `help`
    text from the level JSON; Level 3's fix notes; "Fixed: …"). The user moved the knob
    lines here so that nothing scrolls at 1280×800;
  - right ("play"): Goal, the three star conditions (numbers from the JSON pars), "What
    changes in the OCP" = the **full OCP at the default knob values**, knob parts in the knob
    colours, parts **new in this level on a soft yellow highlight** (+ the key "new in this
    level"), and "Start level ▶" pinned at the bottom (each tile scrolls its own content).
  - Spoilers allowed: the texts say the concept, how the default fails and the fix ideas
    (Level 3 keeps "find out which one works"). No map preview. Level 1 marks nothing new.
    Level 3 shows the no-fix OCP plus one note per fix. Level 2 shows the terminal stop as
    "(terminal stop, optional)". The texts were drafted by the agent and approved by the user.
- (2026-11-17) **Level 0 "Hello, MPC": an introduction to MPC itself** (the user found Level 1
  starts with a finished MPC, too much for a first-time player). Decisions:
  - concept **A: guided tour** (no puzzle, nothing can fail); **optional, no stars** (not in
    the total "x / 15"), always open, Level 1 is open from the start; the tile shows a
    **"Tutorial" tag** (no done state); the lifted "next level" is **never** Level 0;
  - title "Hello, MPC", accent **rose** (`ACCENTS["rose"]`), icon "loop"; open field;
    everything locked (q_p = q_v = r = 1, N = 30). **(2026-11-18) No knobs at all**: the
    user removed the N knob of the first version ("Your turn"): Level 0 is only an intro to
    MPC, and changing N is Level 2's topic (no redundancy). After the tour the controls
    tile says "Tour complete" (+ "Replay the tour"); no Run, Reset or Retry;
  - **exception to the 50 m field**: Level 0 uses a **20 m × 20 m** field and the ball starts
    **already moving** (`"start_velocity": [0, 2]` in its JSON, used by its engine rules), so
    the plans curve and are big enough to read (on 50 m from rest they were a 6 m blob next to
    the ball, with the arrow on top). Run ≈ 10 s;
  - the intro has a drawn **loop diagram** (`gameplay/loop_diagram.py`) under "What you learn";
    no star rows; OCP titled "The OCP your MPC solves" (nothing marked new);
  - play screen: the run **starts automatically**; the **controls tile is the tour panel**
    (Step k of 7, title, text, ‹ Back / Next ›); the **map highlights** each step
    (`MapView.set_tour`, incl. a faint **fan of example predictions** in "Predict", and in
    "Repeat" the run **1 s (10 rounds) later with the first plan in grey**) and the
    **OCP highlights the matching line** (same soft yellow as "new" parts); then the replay
    plays, the result card has no stars and "Replay tour" (no Retry); then "Tour complete".
    Texts drafted by the agent, approved by the user;
  - the intro shows no "What you control" section (nothing to control), no star rows.
  - (2026-11-18) **The solver tile follows the story**: the run is computed before the tour,
    but "This solve" shows "–" until step ③ Optimise (no OCP is solved before that) and then
    follows the shown solve; the "Whole run" line shows "–" until the replay has been watched
    to the end (`RunInfoCard.show_parts(solve, run)`; other levels always show both).

## 9. Gotchas already hit (don't repeat them)

- High Windows display scaling (175%) leaves only ~1100×600 logical pixels: the window
  fits itself to the screen; all screens must work at 900×560 (scroll areas, no fixed
  big sizes). Test small sizes.
- Qt: don't name custom widget properties `size` (clashes with QWidget.size); the
  button style property is `scale`. `&` in button text is a mnemonic: write `&&`.
  Some symbols (e.g. ❚❚) are missing from the fonts; use words or painted icons.
- acados: each compiled solver needs a unique name (`cq_N{N}_o{MAX_OBSTACLES}`); solvers are not
  thread-safe (the server serialises runs with a lock).
- The engine does not reload code: restart it after changes. The game warns when the
  engine version does not match (bump both version numbers when the messages change).
- Fixed-width columns (middle/right panels): a QLabel without word wrap can't get narrower
  than its text, which makes the content wider than the column and clips the cards' right
  edge. Let long values wrap (`label(..., wrap=True)`) or split them into rows, and check
  that no scroll area's content is wider than its viewport at several window sizes.
- Math rendering: matplotlib's `math_to_image` crops exactly at the glyphs, which cut off
  the tops of digits at high display scaling. `ui/math_render.py` renders via a Figure
  with `bbox_inches="tight"` and a small padding instead; keep it that way.
- Sharp images at fractional scaling (175%): never show rendered images in a QLabel or
  scale them: QLabel draws into a rect of *rounded logical* size, so the image gets
  resampled and looks blurry (7 of 9 formulas were). `MathLabel` paints the pixmap at its
  exact size (snapped to device pixels) and re-renders at a smaller font when too wide.
- Coloured math (2026-11-14): a `\knob{...}` line is rendered as several mathtext texts
  side by side in ONE matplotlib Figure. Position them in figure fractions (the default
  `transFigure`): with `IdentityTransform` or `dpi_scale_trans` the `bbox_inches="tight"`
  crop does not follow and the descenders get cut off. The splitter keeps a trailing
  escaped space (`\ `); stripping it leaves a lone `\` and the line fails to render (the
  failure only prints `[math] could not render ...`: watch the console).
- Two monitors with different Windows scaling (2026-11-17: laptop 175%, BenQ 125%): the
  game **crashed** (Windows access violation, no Python error) on every level screen
  shown on the other monitor, because `MathLabel`/`MathChip` re-rendered their formula
  image inside `paintEvent` when the device pixel ratio changed. Never render, resize or
  change layout inside `paintEvent`. They now re-render in `event()` on
  DevicePixelRatioChange / ScreenChangeInternal / Show (`_check_dpr`), and a paint that
  still sees a stale ratio only schedules `QTimer.singleShot(0, self, ...)`. Test with
  the window moved between the two monitors (title, and inside a level).
- (2026-11-17) Don't centre a widget that contains word-wrapped labels with an alignment flag
  (`addWidget(w, 1, AlignHCenter)`) inside a scroll area: the layout reserves the height for
  one width and lays out at another, so rows get squeezed and formulas overlap. Centre with
  stretches on both sides instead (the level intro does).
- (2026-11-17) The `bbox_inches="tight"` crop of a formula only sees the glyphs, not text
  bbox patches (chips, the "new" highlight): `render_tex` adds the highlight's padding to
  `pad_inches`, otherwise the highlight is cut flat at the top and bottom.
- A QSpinBox in a narrow fixed width clips its number to nothing (the hidden arrow buttons
  still take room): the solve stepper uses a QLineEdit + QIntValidator instead.
- Don't override QWidget method names in subclasses (e.g. a `screen()` method on the main
  window broke Qt's `QWidget.screen()`; it is now `get_screen()`).
- Never hard-code the course image name (`vsc-mpcrl26-exercises-<hash>`) in scripts or
  docs: the hash is machine-specific (2026-11-03: a commit with one teammate's hash broke
  the engine start for the other). `start_engine.ps1/.sh` detect it; use `<image>` in docs.
- Generated code (`engine_server/build/`), `.venv/`, `__pycache__/` are gitignored.
- Obstacles in acados (2026-10-26, Level 3 calibration): with **hard** ellipse constraints
  HPIPM failed (MINSTEP) whenever an ellipse and the input bounds were active together
  (braking at full a_max to stop at an ellipse). What made it robust: ellipse constraints
  **soft** with an exact L1 penalty (`ocp.py`, `SLACK_L1`), `qp_tol` 1e-6 (not 1e-8),
  NLP `tol` 1e-4, `hpipm_mode` ROBUST, a small upper bound on h (1e4, not 1e9), unused
  obstacle slots as a small circle far away (well scaled), and LM 1e-2 only when the
  level has obstacles. SQP can still cycle near ellipse tips: a solve that stops at the
  iteration limit (status 2) is used if its plan is valid (finite, within bounds,
  outside all ellipses), else it is a controller failure (`controller.solve`).
- Long thin blocks: their ellipses stick out far and overlapping ellipses form notches
  where the MPC gets stuck. Split walls into shorter blocks (Level 3 uses 6).

## 10. UI structure and content (what the player sees, as of 2026-11-17)

**Design rules: read these before any GUI work** (agreed 2026-11-14, section 8). The goal
is a real game, not a generic "vibe-coded" app. Every screen and every level follows them;
when a new widget needs a look, reuse a token/role below instead of inventing one.

1. **Colours** (`ui/theme.py`, never hard-coded in screens): warm cream BACKGROUND with
   the soft dot grid; white SURFACE tiles; tonal WELL (= SURFACE_ALT) for insets, inputs
   and secondary buttons; coral PRIMARY for the one main action (Run, Play, Next level);
   level accents (`ACCENTS`, lips in `ACCENT_LIPS`); INK / INK_SOFT / MUTED text.
2. **No outlines.** Nothing has a border line. A tile or button "stands" on a **lip**: a
   thicker bottom edge in a darker tone (`LIP`, `PRIMARY_PRESSED`, `ACCENT_LIPS`).
   Inputs and wells are tonal fills; a soft blue `FOCUS` ring appears only for keyboard
   focus (painted widgets: `widgets.is_keyboard_focus`). Empty stars are a soft fill.
3. **Rounded everything**: tiles `RADIUS_CARD` (26), buttons 16-20, wells 16, chips 8-12.
4. **Tiles, not boxes in boxes.** A screen has a few tiles (`Card`, QSS role "card").
   Inside a tile, group with spacing, a coral **eyebrow** label ("Goal"), a subheading,
   or a **well** (`widgets.well()`); never put a card inside a card. Level hooks
   (`add_extras`, `add_controls`, `add_side_cards`) add plain widgets/sections.
5. **Few elements.** Show what the player needs now; put details in tooltips (e.g. the
   whole-run statistics). Prefer one strong line over a table.
6. **Knob colours connect the controls to the math**: knob i gets `KNOB_COLORS[i]` (order
   in the level file): `MathChip` symbol in the knob row, slider fill, and the
   `\knob{name}{tex}` parts of the OCP (top level of a math line only, not inside {...}).
   **New parts** (level intro only): `\new{tex}` on the soft yellow `NEW_GLOW` highlight,
   `\newknob{name}{tex}` for a knob part that is also new (knob chip on the highlight).
7. **Math keeps the textbook font** (matplotlib mathtext, Computer Modern) via
   `MathLabel`/`MathChip` (pixel-snapped, see gotchas). Never draw formulas as text.
8. **One header everywhere** (`ScreenHeader`): the lip back button (`IconButton`), on level
   screens the round level badge (`LevelBadge`, accent colour) + title, stars on the right.
9. **Characters**: the flat blue ball mascot (`painting.draw_ball`; not on the level
   select), yellow star target, beige
   blocks, coral dashed plan with a dot per stage, dashed ellipses, lilac waypoints.
10. **Text roles** (QSS): title, heading, subheading, subtitle, body, goal, quote, caption,
    eyebrow, stat, tag. **Button variants**: default (tonal + lip), primary (coral + lip),
    ghost, link (coral text), chip (small white, in wells), danger; scale large / tall.
11. Fonts: Nunito → Segoe UI → Helvetica Neue → Arial. Outcome colours: success green,
    crash/battery red, controller failure orange, time out grey.
12. Window fits the screen (default 1280×800 logical), works down to 900×560; Esc = back.
    Check new UI at both sizes (no scroll area content wider than its viewport).

**Screens** (`controlquest/screens/`, one file each):
1. **Title**: animated scene (the ball rolls over a block, dashed plan ahead of it,
   ellipse around the block, star at the end that sparkles), "ControlQuest" logo with
   "Quest" in coral, subtitle "Design the controller. Let the ball find its way.",
   buttons Play (big, coral) / How to play / Settings / Quit, an "MPC engine
   online/offline/outdated" pill bottom-left, version bottom-right.
2. **Level select** (`ui/level_card.py`): "Choose a level" + subtitle, Free mode switch,
   total stars pill "x / 15" (Level 0 has no stars), one chunky tile per level (Level 0:
   rose, loop icon, a "Tutorial" tag instead of stars, always open, never the lifted one): top block in the level's accent
   colour with the big number and the level icon (`LevelInfo.icon`: bolt, wall, trap,
   weight, wind; `painting.draw_level_icon`), then title, topic, 3 stars. The next level
   to play (first unlocked one without stars) is lifted, ringed in its colour and shows a
   Play pill (no mascot on this screen). Locked tiles are muted with a lock and
   "Finish level N to unlock"; clicking one explains how to unlock it. Tiles reflow.
3. **How to play**: four step cards (You are the engineer · Tune the controller · Run and
   watch the plan · Fix it, earn stars) and "How a run can end" (Success, Crash,
   Controller failure, Time out), then "Let's play".
4. **Settings**: Animations on/off; MPC engine address + "Test connection" + status;
   Reset progress (with confirmation).
5. **Level screen**: header: back button · level badge (number in the accent colour) ·
   title · ★★★. Unplayable levels show a card with topic, briefing (quote), "What this
   level is about", "The playing field is still being built" (+ dev buttons with
   `CONTROLQUEST_DEV=1`).
   **Level intro** (`gameplay/level_intro.py`), shown first every time a level opens; two
   tiles side by side, each scrolling its own content (nothing scrolls at 1280×800):
   - left: the story (quote), **What you learn**, **How this level teaches it**, **What you
     control** (per knob: coloured chip + name + help text; notes; "Fixed: …");
   - right: **Goal**, ★ / ★★ / ★★★ conditions, **What changes in the OCP** (full OCP at the
     default values, knob colours, new parts highlighted, "new in this level" key next to
     the heading), and the coral **Start level ▶** pinned at the bottom.
   A level provides it with `LevelInfo.concept`, `LevelInfo.teaching` and
   `LevelInfo.intro(data) -> LevelIntro` (goal, stars, OCP, fixed, notes); each level file
   builds its OCP in a module function `ocp(..., intro=False)` used by both screens.
   Back (button or Esc) on the play screen returns to the intro (play state kept).
   **Level 0 (tutorial)**: no stars anywhere (header, intro, result card); the intro adds the
   loop diagram; on the play screen the controls tile is the **guided tour** (computed
   automatically; Step k of 7 · title · text · ‹ Back / Next ›, map + OCP highlights per step),
   after the replay **"Tour complete"** (a short summary + "Replay the tour"). No knobs, no
   Run/Reset: the player only watches.
   **Playable level** (`gameplay/level_play_widget.py`), three tiles on wide windows:
   - left, **map tile**: the **map** (soft 50 m board without outline, grid every 5 m,
     numbers every 10 m with one shared 0 at the origin, start ring, target star, ball
     with trail, current plan, acceleration arrow, a "|v| = … m/s" pill; with obstacles:
     beige blocks, the solver's ellipses dashed, a red × where the ball crashed; Level 3:
     lilac numbered waypoint diamonds with a dotted route, the active one highlighted
     during the replay, reached ones grey); under it the level's extras (Level 1:
     **battery bar** "Battery ▬▬ 4.0 / 5", fills as energy is used, yellow tick = ★★★ par;
     Level 2: **brake check**: wall ahead / braking needs / plan looks ahead, red after the
     point of no return; Level 4: the ghost-ball caption; Level 5: compute budget), then
     ONE **replay well**: ▶/❚❚ · scrubber · time · speed chip (1×/2×/4×/8×, default 2×) ·
     "‹ k /n ›" MPC solve stepper (number typeable);
   - middle, **OCP tile**: **"The OCP your MPC solves"** (typeset math: min over u, stage
     cost ℓ, P, "s.t." constraints; knob parts in the knobs' colours; short notes and a
     symbol legend), then **"This solve"** (k of n · t; four big numbers: plan cost J*,
     solve time, SQP iterations, acados status) and one **"Whole run"** line;
   - right, **controls tile**: **Goal** (eyebrow + text), **Tune the weights** (eyebrow;
     one row per knob: coloured symbol chip + name, a typeable value field, a slider in
     the knob's colour; discrete knobs as a dropdown, toggles as a switch); Reset + wide
     Run ▶; a status line; Level 3: **Choose a fix** instead: selectable cards "No fix",
     "1. Longer horizon" (N dropdown + "N steps = … s ahead" note), "2. Waypoints"
     (map editing only then; instructions, "n / 3 waypoints", Clear, the list of
     waypoints), then **Your experiments** (best run per fix: result with colour dot,
     ms per solve, stars; this visit only; a section of the tile, not a card); the OCP
     follows the chosen fix; at the bottom **Stuck?** with a "Show hint k/3" link, hints
     revealed one at a time (3 per level, the last almost the answer).
   - Narrow windows (< 1150 px): the OCP tile moves into the right column, under the
     controls tile; both columns scroll.
   - At the end of a replay a **result card** appears over the map: outcome title with
     colour dot, stars, metric rows (e.g. time vs limit and ★★ par, energy vs battery and
     ★★★ par, peak acceleration), 1–3 "what happened" sentences from the engine, buttons
     Replay / Retry / Next level ›. Changing a knob hides the card.

## 11. Working with the user (how the team likes it)

- When the user only asks a question, **answer it; don't change code** unless asked.
- After building something: explain **what was built, how to run it, how to continue**,
  and (for MPC changes) how a change would affect the results, in plain language.
- Say clearly what was tested and how, and what could not be tested and why.
- Prefer finished, small slices over big plans; the deadline is short.
- Keep the PRD, `game/README.md` and this file current; log every new remark in section 8.

