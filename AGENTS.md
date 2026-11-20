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
- Levels (since 2026-11-19, reduced scope): the tutorial Level 0 "Hello, MPC" (no stars) and
  **four rated levels**: 1 "The Price of Speed", 2 "Brake Check", 3 "Dead End", 4 "Crosswind".
  The former Level 4 "Heavy Ball" (model mismatch) was **removed**; Crosswind moved from 5 to 4.
  The goal now is a polished, scientifically grounded version of these levels (section 8).
- **RL is out of scope for now** (stretch goal only, if time is left at the end).

## 3. Repository map

```
ControlQuest/
├── AGENTS.md            this file (CLAUDE.md just imports it)
├── README.md            short project description + pointers
├── docs/PRD.md          game design: rules, screens, levels, data formats, plan
├── docs/RESEARCH.md     scientific motivation, formal OCP, measured results, references
│                        (data: docs/results/, docs/figures/; the research brief:
│                        docs/SCIENTIFIC_UPGRADE_BRIEF.md, a proposal, superseded where they differ)
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
  Level 1's sweep as CSV: `--sweep --csv /workspace/docs/figures/price_of_speed_sweep.csv`; its
  figure (on the host): `python docs/figures/make_price_of_speed_pareto.py`.
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

## 6. Status (2026-11-19)

- Done: menus (title with animation, level select with stars/locks/free mode, how
  to play, settings), engine server, MPC package, **Level 1 "The Price of Speed"
  fully playable** (calibrated; `calibrate.py price_of_speed` passes), OCP shown as
  typeset math, battery bar, result card, hints, MPC-solve selector, solver info card,
  responsive layout.
- Done (2026-10-26, branch `level3to4`): **obstacles in the engine** (up to 6 blocks per
  level, soft ellipse constraints, block crash check) and **Level 3 "Dead End"**
  playable: click-to-place waypoints, blocks + ellipses + waypoints on the map
  (`calibrate.py dead_end`). Since 2026-10-26 the player **picks a fix** (no fix /
  ① longer horizon: any whole N from 5 to 300, typed or slider, a new N builds its solver
  once / ② waypoints) and compares them in "Your experiments"; fix ③ was dropped
  (below). Engine v0.5.0.
- Done (2026-11-03): **Level 2 "Brake Check"** playable (horizon dropdown, terminal-stop
  switch, brake-check gauge; `calibrate.py brake_check`). Levels 4 and 5 were built too
  (branch `level3to4`); Level 4 "Heavy Ball" was removed on 2026-11-19. Engine v0.9.0.
- Done (2026-11-14, branch `gui`): **UI redesign** on all screens and levels (design rules
  in section 10; borderless tiles with lips, three-tile level screen, knob colours in the
  OCP, new level select). Game-side only: engine unchanged (still v0.9.0).
- Done (2026-11-17, branch `gui`): **level intro** before every level (`gameplay/level_intro.py`,
  `LevelInfo.teaching` + `LevelInfo.intro`; section 10). Game-side only.
- Done (2026-11-17, branch `gui`): **Level 0 "Hello, MPC"**, an optional tutorial (guided tour
  of the MPC loop, no stars; `levels/level_0_hello_mpc.py`, `level_data/hello_mpc.json`,
  `level_rules/hello_mpc.py`, `calibrate.py hello_mpc`). Engine v0.10.0 (new level id).
- Done (2026-11-19): **all symbols in the LaTeX font** (`ui/math_text.py`, `$...$` in every
  text incl. the engine sentences; section 8). Engine v0.11.0.
- Done (2026-11-19, reduced scope, phase 1): **Level 4 "Heavy Ball" removed** (level file, level
  JSON, level rules, the `/test_drive` endpoint, the ghost ball and the `prediction_error` /
  `prediction_lookahead` trajectory fields, the "weight" icon). **Crosswind is Level 4**
  (`levels/level_4_crosswind.py`). The model gain `g` stays in `mpc/` (all levels use g = 1;
  kept so the OCP recipe and the compiled solvers are unchanged). Bug fixed: a run that
  finishes while the play screen is hidden (the player went back to the intro during
  "Computing...") is now replayed when the play screen is shown again, not unseen. Engine v0.12.0.
- Done (2026-11-19, phase 2): **scientific wording** of the level texts and the engine's
  "what happened" sentences fixed (rules in section 8); Crosswind's and Dead End's OCP cards say
  the ellipse constraints are soft. Texts only, no parameters changed. Engine v0.13.0.
  Bug fixed on the way: the result card squeezed its rows and sentences on top of each other
  when it was taller than the map (900×560 in Brake Check, Dead End, Crosswind; already before
  the new texts). Its text part now scrolls inside the card; the buttons stay visible.
- Done (2026-11-19, phase 3): **Research debrief** (`gameplay/research_debrief.py`, content in
  `controlquest/research/<level_id>.py`, 10 papers checked against Crossref / arXiv / RSS):
  "Insights" on the result card, "Research background" on the intro (not Level 0's),
  `LevelScreen` has explicit views (intro / play / debrief / other). Game-side only.
- Done (2026-11-20, branch `gui`): **Analysis tab** (optional, visualisation only): the map
  tile has two tabs, Simulation (default) and Analysis, with two time-series plots per level
  of the latest run and a cursor at the replay time (`gameplay/analysis_panel.py`, the levels'
  `analysis_plots` hook, `widgets.SegmentedControl`); unit tests in `game/tests/`. Game-side
  only: engine, metrics, scoring and calibration unchanged (calibrations re-run, identical).
- Not yet: saving progress to disk (progress resets on restart, intentionally for now).
- Done (2026-11-19, phase 4): **`docs/RESEARCH.md`** (motivation, formal OCP incl. soft
  constraints and the external budgets, research question, measured results, interpretation,
  limits and the 10 checked references per level), the raw log
  `docs/results/calibrate_2026-11-19.txt`, Level 1's static Pareto figure
  (`docs/figures/`), `calibrate.py` prints solves / mean solve time / drift / clearance and
  writes the sweep as CSV; the brief renamed to `docs/SCIENTIFIC_UPGRADE_BRIEF.md`; PRD and
  this file brought up to date. In the debrief, "Your latest run" moved under the takeaway.
- All four reduced-scope phases are done. Open: nothing planned; ask the team before new scope.
- Done (2026-11-19, final validation before the report): **Crosswind's drift redefined** as the
  deviation from the prediction in force (up to and including the moment a plan is replaced),
  new metric `mean_replan_deviation`, result row "max vs the plan in force"; **numerical
  verification** `docs/results/verify_numerics.py` (+ log): Brake Check $|v_N| \le 10^{-11}$,
  dynamics residuals $\le 4\cdot 10^{-11}$, bounds exact; Dead End stationary point (status 0,
  KKT $\le 10^{-4}$), no local-minimum claim; obstacle penalty not claimed exact (measured
  slacks instead). Dead End and obstacle wording corrected in game, engine and docs; all
  calibrations re-run (pass; only the Crosswind deviation values changed). Engine v0.14.0.

**Dropped (2026-11-19, reduced scope): fix ③ of Level 3 (a better terminal cost / cost-to-go).**
Do not build it, nor the Dijkstra reference. Level 3 keeps fixes ① and ②. The spike results
below stay as background (they may be mentioned in the research texts):
- ① **Longer horizon N**: none of the tested horizons escaped (an observation on this map, not a
  proof). N = 30/60/100/150 all time out at (29.8, 25);
  mean solve time 0.95 → 2.67 ms (max 84 ms), run 1.0 → 2.9 s (2026-11-19 on another
  machine: 1.3 → 3.0 ms; solve times are machine-specific). Interpretation (not proven):
  the warm-started SQP stays near its previous plan, a stationary point in front of the wall.
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
- Code from the spike still in the repo: `engine_server/mpc/value_function.py` (Dijkstra
  grid cost-to-go + RBF fit; **not used**).

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
- (2026-11-19) **Reduced scope (time constraints); this overrides earlier plans, including the
  "must-have Levels 1, 2, 4, 5" of 2026-10-19 and the scientific-upgrade brief's implementation
  ideas** (the brief, `docs/SCIENTIFIC_UPGRADE_BRIEF.md`, stays as research reference).
  Goal: a polished, scientifically grounded version of the existing game, no extra complexity.
  - **Level 4 "Heavy Ball" removed** (the user: "I do not want it anymore"); the tutorial + four
    rated levels remain, **Crosswind renumbered 5 → 4**, total stars "x / 12". All of Heavy
    Ball's code goes (incl. test drive endpoint and ghost ball); the generic model gain `g` stays
    in `mpc/` (unchanged OCP recipe).
  - Hello, MPC: keep the existing tutorial. Price of Speed: keep the weight tuning; **no
    interactive Pareto front** (a static Pareto plot made offline with the calibration tools is
    allowed, docs only). Brake Check: keep horizon, terminal stop and brake gauge, nothing new.
    Dead End: only fixes ① horizon and ② waypoints; **no fix ③, no Dijkstra, no terminal cost**.
    Crosswind: keep fixed-interval re-planning; **no event-/self-triggered MPC** (only mentioned in
    the research texts).
  - Research: keep the brief's **two papers per remaining level** (0A/0B, 1A/1B, 2A/2B, 3A/3B,
    5A/5B, Crosswind's pair keeps the brief's name); **one reusable Research debrief screen** with level-specific content: the scientific
    problem, why it matters, how the level shows it, how the papers address it. Reuse existing
    metrics and visualisations. **No** experiment-history system, complex interactive plots,
    new optimisation algorithms or controller features. No change of controller parameters
    without the user's approval.
  - Priorities: 1 fix bugs and verify calibration; 2 scientific accuracy; 3 research debrief;
    4 visual consistency; 5 document the scientific motivation and the measured results.
- (2026-11-19) **Research debrief decisions** (the user approved the agent's recommendations):
  - content in a new package `controlquest/research/` (typed dataclasses `ResearchInfo`,
    `PaperRef`; one file per level, keyed by level id; static, offline, not in the level JSON);
  - reached from an **"Insights" button on the result card after any outcome** (Replay · Retry ·
    Insights · Next) and from a **"Research background" link on the level intro** (debrief in a
    "No run yet" state); Level 0: only from its result card (tutorial otherwise unchanged);
  - the result card's "Next level" rule stays **as it is** (only after a success, none on the
    last level); the debrief's buttons follow the same rule: tonal "‹ Back to the level" + coral
    "Next level ›" only when the result card shows Next; opened from the intro: "Start level ▶";
  - layout: **two tiles like the level intro**, the main button pinned at the bottom; sections
    The problem · Why it matters · What this level showed (the run's real numbers) · What research
    does (2 paper cards, links open only on click) · **Limits of this level** (1–2 sentences);
  - visuals: the run's numbers plus **existing widgets frozen at the run's end** (Level 1 battery
    bar, Level 2 brake gauge at the point of no return, Level 3 "Your experiments", Level 4
    compute-budget bar); no new chart widget;
  - failed runs show "stopped after t s, d m left", never a time to target; no run yet: "No run
    yet";
  - Level 1 keeps "battery / energy" in play; tooltip and debrief say $\sum \Delta t\,\|u\|^2$ is an
    effort measure, not physical energy;
  - the research question is the debrief's headline only (not added to the level intro);
  - scientific wording fixes in game texts **and** in the engine's "what happened" sentences
    (engine version bump); the 10 references are checked against their public DOI/arXiv pages;
  - measured results for `docs/RESEARCH.md` come from the existing `calibrate.py` (commands
    listed, no new benchmark script); Level 1's static Pareto plot: `calibrate.py --sweep` writes
    a CSV, a small offline script draws the PNG (docs only, labelled "best trade-offs among the
    tested settings"); the brief is renamed to `docs/SCIENTIFIC_UPGRADE_BRIEF.md`.
- (2026-11-19) **References checked** (phase 3) against Crossref (DOI metadata), arXiv and the
  RSS 2024 programme page; abstracts from Crossref, arXiv or Semantic Scholar. All 10 exist with
  the brief's titles, years and venues. Corrected: [1A] has **five** authors (F. Krabbes was
  missing in the brief); [3B]'s arXiv preprint has a shorter title than the published letter;
  [0B] (RSS 2024) has no DOI listed, the link is the programme page. Not used: the brief's
  claims that are not in the abstracts (e.g. "constraint tightening" for [5A], section/figure
  pointers), and the author-hosted mirrors (not checked). Summaries in the game paraphrase
  the abstracts; each `PaperRef.checked` says what was verified.
- (2026-11-19) The result card has **four buttons** (Replay · Retry · Insights · Next level ›);
  to fit 460 px they use the new button scale **"compact"** (`theme.py`: same height, 14 px
  sides). Use it only where several buttons share a narrow row.
- (2026-11-19) **"Your latest run" first in the debrief**: the agent asked whether to keep the
  spec's order (problem → why it matters → what the level showed) or show the player's run
  first; the user told it to take its recommendation: the well "Your latest run" sits right
  under the takeaway, visible without scrolling at 1280×800.
- (2026-11-19) Level 1's debrief: the second paper ([1B], Abtahi et al.) shows **only "Open the
  paper ›"**, no "Free version (arXiv) ›" link (the user asked for it; `free_url` left empty in
  `research/price_of_speed.py`). Other papers keep their arXiv links; docs/RESEARCH.md still cites
  the preprint.
- (2026-11-20) **Analysis tab** (the user's request; the agent's recommendations 1A-9A approved,
  "stay consistent with what is implemented and scientifically correct"):
  - purely visual and optional: no change to the controller, dynamics, constraints, metrics,
    scoring, calibration or level completion; no history, overlays, export or new experiments;
  - drawing (1A): matplotlib Agg renders each plot once per new run (and on resize / display
    scaling) into an image painted snapped to device pixels, like the formulas; the time cursor
    is a QPainter line on top, so playback never re-renders; nothing renders while the tab is
    hidden or inside paintEvent; axis labels in the LaTeX font (mathtext "cm"), ticks in the game
    font with a per-glyph fallback to DejaVu Sans (for "★");
  - the tab switch (2A) is a small segmented switch above the map (`SegmentedControl`, QSS
    variant "segment"); only the map area switches (3A): level extras and the replay well stay
    under both tabs; the result card belongs to the Simulation tab (4A), so the plots stay
    readable when a replay ends on Analysis; Level 0: Analysis disabled during the guided tour,
    available after the tour's replay (5A, like the solver numbers); the plots always show the
    same run as the map: replaced by a new run, kept on Reset or knob changes, empty on a fresh
    level visit (6A); the chosen tab is kept during a level visit (7A);
  - plots and data (all from RunResult.trajectory + the level file, with their own timestamps:
    states/effort/drift at t_k, per-solve data at steps·dt): L0 speed |v| and distance to the
    target; L1 speed and cumulative control effort E (m²/s³, not energy) with the budget and ★★★
    lines; L2 v_x with v_max (per axis) and d_wall = x_wall - p_x vs d_stop = max(v_x,0)²/(2 a_max),
    shaded where d_stop > d_wall ("a physical argument, not a solver certificate"); L3 distance to
    the FINAL target and speed, with a line at each reference switch (waypoints); L4 the engine's
    prediction error (`drift`, prediction in force incl. the outgoing plan at a re-plan, t = 0 left
    out) in one segment per plan with the bound ½ w_max τ² (w_max = |(|c_x|+a_x, |c_y|+a_y)| = 0.9
    m/s² from the wind settings; τ = time since the plan in force was solved), re-plan ticks, and
    the solves staircase with the budget and ★★★ lines. No v_max line on |v| plots (8A: limits are
    per axis, |v| may exceed v_max). Plot colours: `theme.PLOT_*` (BALL_DARK / PRIMARY_PRESSED for
    data: they pass the dataviz palette checks incl. 3:1 contrast on white);
  - tests (9A): `game/tests/test_analysis.py` (stdlib unittest, offscreen, no engine).
- (2026-11-19) **Final validation** (the user approved the agent's recommendations A1, B, C, not
  D): (A1) Crosswind's deviation is measured against the prediction in force, also at the
  re-planning instant (the outgoing plan), so every $k$ is measured the same way; comparisons
  between $k$ use the common window $t \le 6$ s (all runs last that long and see the same wind);
  (B) `docs/results/verify_numerics.py` + its log are kept in the repo as the reproducible check;
  (C) Dead End and obstacle statements corrected (stationary point, not a local minimum; "none of
  the tested horizons", not "never"; slack penalty described as built, not as exact); (D) no
  extra $v_N$ check in the controller (verified numerically instead).
- (2026-11-19) **Phase 4 docs**: `docs/RESEARCH.md` uses only numbers from
  `calibrate.py` runs (raw log in `docs/results/`, with environment and commands) and labels
  them as our simulation data, separate from the papers (paraphrased abstracts). Times of
  failed runs are "until the run stopped"; solve times are acados `time_tot`, machine-specific.
  Level 1's figure shows the "best trade-offs among the tested settings", not a true Pareto front.
- (2026-11-19) **Scientific wording rules** (phase 2; keep them in every new text): limits are
  per axis ($|a_x|, |a_y| \leq a_{\max}$, so the speed $\|v\|$ can exceed $v_{\max}$); $k = 1$ is "the
  most feedback", never "perfect"; re-planning "lets the controller react to" model errors, it
  does not "correct anything"; Level 1's default is "aggressive", not "time-optimal", and its
  "energy" is an effort measure $\sum \Delta t\,\|u\|^2$; the terminal stop keeps the OCP feasible
  **with an exact model and no disturbances**; a controller failure is "the solver found no
  valid plan (acados status ...)", the physics (braking distance vs room) is the evidence, not
  the solver; Dead End's trap is "stuck: every solve returns (status 0) practically the same
  plan, a stationary point", never a proven local minimum, and "none of the tested horizons
  escaped", never "a longer horizon cannot help"; obstacle ellipse constraints are **soft** (say
  so wherever the OCP shows them) with an L1 + small quadratic slack penalty that is **not**
  claimed to be exact; Crosswind's "off the plan" is the deviation from the prediction in force,
  measured up to and including the moment a plan is replaced (since engine 0.14.0).

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
  since 2026-11-14 shortened to four numbers + one "Whole run" line, see below; since
  2026-11-18 only whole-run numbers, see there):
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
    under it (until 2026-11-18, now whole-run numbers only, see there) "This solve" as four
    big numbers (plan cost J*, solve time, SQP iterations,
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
    the total "x / 15", now "x / 12"), always open, Level 1 is open from the start; the tile shows a
    **"Tutorial" tag** (no done state); the lifted "next level" is **never** Level 0;
  - title "Hello, MPC", accent **rose** (`ACCENTS["rose"]`), icon "loop"; open field;
    everything locked (q_p = q_v = r = 1, N = 30). **(2026-11-18) No knobs at all**: the
    user removed the N knob of the first version ("Your turn"): Level 0 is only an intro to
    MPC, and changing N is Level 2's topic (no redundancy). After the tour the controls
    tile says "Tour complete" (+ "Replay the tour"); no Run, Reset or Retry;
  - **exception to the 50 m field**: Level 0 uses a **20 m × 20 m** field, so the plans are big
    enough to read (on 50 m from rest they were a 6 m blob next to the ball, with the arrow on
    top). Run ≈ 10 s. (2026-11-18) **The ball starts at rest** (`"start_velocity": [0, 0]`;
    the user replaced the first version's moving start, v₀ = (0, 2)). On the 20 m field the
    tour stays readable: straight fan, slightly curved plan, arrow above the plan;
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
  - (2026-11-18) **Level 0's OCP is written as simply as possible**: weights equal to 1 are
    left out (ℓ = ‖p − p★‖² + ‖v‖² + ‖u‖²), the terminal cost is written as its number
    (10‖x_N − x★‖², since Q = I there), and the line "P = 10 Q, horizon N = 30" is gone (N is
    visible in the sum and the note). Only valid while q_p = q_v; otherwise `ocp()` falls back
    to ‖·‖²_P with "P = 10 diag(...)". Other levels are unchanged.
  - (2026-11-19) **"Tour complete" has two buttons** (not the "Replay the tour" link): a tonal
    "Replay tour" on the left and the coral "Next level ›" (→ Level 1's intro) on the right,
    laid out like the tour's ‹ Back / Next.
  - (2026-11-19) **The tour's ‹ Back / Next buttons never move**: the step title + text sit in
    an area as tall as the longest tour text at the current width (re-measured when the width
    changes), so the buttons stay at one height on every step instead of jumping with the text.
  - (2026-11-18) **The solver section stays empty during the tour**: the run is computed before
    the tour, but all its numbers show "–" until the replay has been watched to the end
    (`RunInfoCard.set_hidden`; other levels show them as soon as the run is computed).
- (2026-11-18) **Solver section = whole run, in every level** (replaces the per-solve "This
  solve" numbers of 2026-10-25 / 2026-11-14; the user confirmed the change): title **"Whole
  run"** with **"n solves · t = run time"** next to it, then four big numbers: **total cost**
  (closed loop), **avg solve time**, **avg SQP iterations** (max in the tooltip) and **solved
  count** "ok / n" with the caption "solved · acados status" (green if all solved, red
  otherwise; failing solves listed in the tooltip). The separate one-line "Whole run" summary
  is gone. The "‹ k /n ›" stepper only moves the map; no per-solve numbers are shown. The user
  first wanted to drop the iterations ("always 1?"): measured, they are 1 in Levels 0–2 (no
  obstacles: the OCP is a QP) but 2–6 per solve with obstacles (Levels 3–5 then; Dead End and Crosswind now), so they stay.
- (2026-11-19) **Every symbol in the LaTeX font, everywhere** (the user disliked the game font's
  "★" next to the OCP's \star and asked for "everything in the same font as LaTeX"; chose
  "all math-like text", all at once). Design rule 7 (section 10) says how. Built:
  `ui/math_text.py` (inline LaTeX in wrapping rich text, sharp at 175 %, aligned on the text
  baseline, DPR-safe); OCP legends one symbol per line in Computer Modern (`STATE_LEGEND` in
  `ocp_card.py`); `$...$` in all level texts (intro, goals, stars, "Fixed:", notes, hints,
  captions, tour, result rows), the knob help / fix texts in the level JSON files, the engine's
  "what happened" sentences (engine v0.11.0), the map pills (|v|, x̂, u₀, x_N) and the loop
  diagram (Δt). Rule used: anything with a symbol is math; pure number comparisons next to
  rating stars ("★★ ≤ 30 s") stay plain. Tooltips use plain Unicode (`to_plain`).

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
- (2026-11-19) Inline math (`ui/math_text.py`): a `QImage` with a device pixel ratio drawn with
  QPainter into another image is drawn at its *logical* size; give the target image the same
  ratio first (`setDevicePixelRatio`), or the formula shrinks by 1/1.75 and floats up. The
  text widget is a QTextBrowser: it must ignore wheel events (else the scroll area around it
  stops scrolling) and must not get `setContentsMargins` (eats its fixed height).
- (2026-11-19) LaTeX in Python strings: `$\Delta t$` inside a plain `f"..."` is an invalid
  escape (SyntaxWarning, breaks later): use `rf"..."` and double the TeX braces (`{{...}}`).
  In the level JSON files a backslash is written `\\`.
- (2026-11-19) A widget placed over another with an alignment flag (the result card over the
  map, `addWidget(w, 0, 0, AlignCenter)`) gets at most the cell's size even when its content is
  taller: Qt then squeezes fixed-height children on top of each other (no error). Give such a
  widget a scrolling part with a small minimum height (`result_panel._FitScroll`), and test the
  longest texts at 900×560.
- (2026-11-19) Qt rich text ignores `white-space: nowrap` on a `<span>` (it only works for a whole
  block). To keep "m/s" from breaking after the slash, put a word joiner after it: `m/\u2060s` (`WJ` in `level_0_hello_mpc.py`).
- A QSpinBox in a narrow fixed width clips its number to nothing (the hidden arrow buttons
  still take room): the solve stepper uses a QLineEdit + QIntValidator instead.
- Don't override QWidget method names in subclasses (e.g. a `screen()` method on the main
  window broke Qt's `QWidget.screen()`; it is now `get_screen()`).
- Never hard-code the course image name (`vsc-mpcrl26-exercises-<hash>`) in scripts or
  docs: the hash is machine-specific (2026-11-03: a commit with one teammate's hash broke
  the engine start for the other). `start_engine.ps1/.sh` detect it; use `<image>` in docs.
- (2026-11-20) matplotlib warns "Glyph ... missing from font" (e.g. "★" in Segoe UI) and draws a
  box: give `font.family` a fallback list (`[game font, "DejaVu Sans"]`, matplotlib >= 3.6 falls
  back per glyph). Run the plot tests with `-W error::UserWarning` to catch it.
- Generated code (`engine_server/build/`), `.venv/`, `__pycache__/` are gitignored.
- Obstacles in acados (2026-10-26, Level 3 calibration): with **hard** ellipse constraints
  HPIPM failed (MINSTEP) whenever an ellipse and the input bounds were active together
  (braking at full a_max to stop at an ellipse). What made it robust: ellipse constraints
  **soft** with an L1 penalty (`ocp.py`, `SLACK_L1`; acados multiplies it by the cost scaling
  dt, and it is exact only if larger than the multipliers), `qp_tol` 1e-6 (not 1e-8),
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
   **Every symbol a player reads is in that font too** (2026-11-19): write math-like parts of
   any text as `$...$` (`$N = 30$`, `$\hat{x}$`, `$q_p$`, `$u_0$`) and show it with
   `ui/math_text.py` (`math_text(text, role)`, a label-like widget with inline LaTeX; words
   stay in the game font). OCP legends are `(symbol tex, words)` tuples, typeset fully in the
   LaTeX font. Tooltips stay plain: pass texts through `to_plain()`. Painted widgets (map pills,
   loop diagram) prepare their formula images with `inline_image()` outside `paintEvent`.
8. **One header everywhere** (`ScreenHeader`): the lip back button (`IconButton`), on level
   screens the round level badge (`LevelBadge`, accent colour) + title, stars on the right.
9. **Characters**: the flat blue ball mascot (`painting.draw_ball`; not on the level
   select), yellow star target, beige
   blocks, coral dashed plan with a dot per stage, dashed ellipses, lilac waypoints.
10. **Text roles** (QSS): title, heading, subheading, subtitle, body, goal, quote, caption,
    eyebrow, stat, tag. **Button variants**: default (tonal + lip), primary (coral + lip),
    ghost, link (coral text), chip (small white, in wells), danger, segment (a segmented
    switch, `widgets.SegmentedControl`); scale large / tall / compact.
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
   total stars pill "x / 12" (Level 0 has no stars), one chunky tile per level (Level 0:
   rose, loop icon, a "Tutorial" tag instead of stars, always open, never the lifted one): top block in the level's accent
   colour with the big number and the level icon (`LevelInfo.icon`: bolt, wall, trap,
   wind; `painting.draw_level_icon`), then title, topic, 3 stars. The next level
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
   **Research debrief** (`gameplay/research_debrief.py`, phase 3): opened by "Insights" on the
   result card (with that run) or "Research background" left of "Start level" on the intro
   (no run yet; not on Level 0's intro). Two tiles like the intro: left: research question
   (quote), takeaway, then a well "Your latest run" (outcome dot, stars (not Level 0), "Reached
   the target in t s" or "<outcome>: stopped after t s, d m from the target", the result card's
   rows, and an existing visual frozen at the run's end: Level 0 loop diagram, Level 1 battery
   bar, Level 2 brake gauge at the point of no return (or the least room to spare), Level 3
   "Your experiments", Level 4 compute budget; "No run yet" without a run), then The problem,
   Why it matters, What this level showed, Limits of this level; right: What research does (two paper wells: title,
   authors · year, venue, Problem / Approach / Link to this level, "Open the paper ›" and
   "Free version (arXiv) ›" links, opened only on click), then pinned "‹ Back to the level" +
   "Next level ›" (only when the result card offers it) or "Start level ▶" (from the intro).
   Back / Esc returns to where it was opened from; the play view keeps everything and its
   replay is paused.
   **Level 0 (tutorial)**: no stars anywhere (header, intro, result card); the intro adds the
   loop diagram; on the play screen the controls tile is the **guided tour** (computed
   automatically; Step k of 7 · title · text · ‹ Back / Next ›, map + OCP highlights per step),
   after the replay **"Tour complete"** (a short summary, "Replay tour" and "Next level ›"). No knobs, no
   Run/Reset: the player only watches.
   **Playable level** (`gameplay/level_play_widget.py`), three tiles on wide windows:
   - left, **map tile**: on top a **Simulation | Analysis** switch (Simulation by default;
     Analysis = two time-series plots of the latest run with a cursor at the replay time,
     "The plots of this run appear here after you run the simulation" before a run; Level 0:
     only after the tour's replay); the Simulation tab is the **map** (soft 50 m board without outline, grid every 5 m,
     numbers every 10 m with one shared 0 at the origin, start ring, target star, ball
     with trail, current plan, acceleration arrow, a "|v| = … m/s" pill; with obstacles:
     beige blocks, the solver's ellipses dashed, a red × where the ball crashed; Level 3:
     lilac numbered waypoint diamonds with a dotted route, the active one highlighted
     during the replay, reached ones grey); under it the level's extras (Level 1:
     **battery bar** "Battery ▬▬ 4.0 / 5", fills as energy is used, yellow tick = ★★★ par;
     Level 2: **brake check**: wall ahead / braking needs / plan looks ahead, red after the
     point of no return; Level 4 (Crosswind): compute budget), then
     ONE **replay well**: ▶/❚❚ · scrubber · time · speed chip (1×/2×/4×/8×, default 2×) ·
     "‹ k /n ›" MPC solve stepper (number typeable);
   - middle, **OCP tile**: **"The OCP your MPC solves"** (typeset math: min over u, stage
     cost ℓ, P, "s.t." constraints; knob parts in the knobs' colours; short notes and a
     symbol legend), then **"Whole run"** ("n solves · t = run time"; four big numbers:
     total cost, avg solve time, avg SQP iterations, solved count "ok / n" · acados status);
   - right, **controls tile**: **Goal** (eyebrow + text), **Tune the weights** (eyebrow;
     one row per knob: coloured symbol chip + name, a typeable value field, a slider in
     the knob's colour; discrete knobs as a dropdown, toggles as a switch); Reset + wide
     Run ▶; a status line; Level 3: **Choose a fix** instead: selectable cards "No fix",
     "1. Longer horizon" (N as a typed value + slider, 5–300, + "N steps = … s ahead" note), "2. Waypoints"
     (map editing only then; instructions, "n / 3 waypoints", Clear, the list of
     waypoints), then **Your experiments** (best run per fix: result with colour dot,
     ms per solve, stars; this visit only; a section of the tile, not a card); the OCP
     follows the chosen fix; at the bottom **Stuck?** with a "Show hint k/3" link, hints
     revealed one at a time (3 per level, the last almost the answer).
   - Narrow windows (< 1150 px): the OCP tile moves into the right column, under the
     controls tile; both columns scroll.
   - At the end of a replay a **result card** appears over the map: outcome title with
     colour dot, stars, metric rows (e.g. time vs limit and ★★ par, energy vs battery and
     ★★★ par, peak acceleration), 1–3 "what happened" sentences from the engine (the text
     part scrolls inside the card when it does not fit over the map), buttons Replay / Retry /
     Insights / Next level › (compact; Next only after a success with the next level
     unlocked; Level 0: no Retry). Changing a knob hides the card.

## 11. Working with the user (how the team likes it)

- When the user only asks a question, **answer it; don't change code** unless asked.
- After building something: explain **what was built, how to run it, how to continue**,
  and (for MPC changes) how a change would affect the results, in plain language.
- Say clearly what was tested and how, and what could not be tested and why.
- Prefer finished, small slices over big plans; the deadline is short.
- Keep the PRD, `game/README.md` and this file current; log every new remark in section 8.

