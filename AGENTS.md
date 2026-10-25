# AGENTS.md: context for AI coding agents working on ControlQuest

Read this first. It tells you what the project is, how to run it, how the code is
organised, **the decisions and remarks the team has already made** (section 8), the
**UI structure and content** (section 10) and **how the team likes to work with an
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
- **Docker Desktop**, running, with the course image. Default name:
  `vsc-mpcrl26-exercises-94d9982245bae36f409cb410a37b514aafe63fa52604de9d9dc9f0c9c94c729a`
  (built from the `Dockerfile` of the course repository `mpcrl26-exercises`; contains
  Python 3.11, acados, CasADi, NumPy). Check with `docker images`. If the image has a
  different name on this machine, set `CONTROLQUEST_IMAGE` to it.
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

## 6. Status (2026-10-25)

- Done: menus (title with animation, level select with stars/locks/free mode, how
  to play, settings), engine server, MPC package, **Level 1 "The Price of Speed"
  fully playable** (calibrated; `calibrate.py price_of_speed` passes), OCP shown as
  typeset math, battery bar, result card, hints, MPC-solve selector, solver info card,
  responsive layout.
- Not yet: levels 2–5 (show "coming soon"), speed/acceleration plots (PRD 5.6),
  saving progress to disk (progress resets on restart, intentionally for now).
- Next planned work: UI changes requested by the team, then the MPC side of levels 2–5
  (horizon N per level, terminal constraint, obstacles, model gain, wind, re-plan interval).

## 7. Rules for agents working in this repo

- **Ask before committing or pushing**; work on a feature branch; never rewrite shared history.
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
- (2026-10-19) Workspace 50 m × 50 m, start/target scaled accordingly.
- (2026-10-22) Level 1 battery (energy budget): **the run stops immediately when the
  budget is used up** (outcome `battery_empty`), it does not just fail at the end.
- (2026-10-22) Level 1 numbers were calibrated with real runs (PRD guesses were not
  feasible): time limit 40 s, battery 5, ★★ ≤ 30 s, ★★★ also energy ≤ 4.75;
  reference q_p = 0.1, q_v = 1, r = 1. Far from the target the MPC always starts at
  full acceleration (~4 energy), so weights mainly change braking/approach.

**MPC**
- (2026-10-19) Obstacles: a block is given by 4 corners; the solver avoids the
  **minimum-area ellipse containing the corners**, `(p−c)ᵀE(p−c) ≥ 1`. No min/max
  in constraints (keeps the NLP smooth). Crashes are checked against the real block.
- (2026-10-19) With obstacles, SQP uses Levenberg–Marquardt damping (1e-2); merit
  backtracking performed much worse.
- (2026-10-22) One OCP "recipe" (`mpc/ocp.py`), several compiled solvers cached per
  problem shape; level differences are runtime numbers or plant-side (wind, model
  mismatch), not separate solvers.

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
- (2026-10-25) **Choose an individual MPC solve**: under the replay bar there is an
  "MPC solve ‹ k › of n" selector (`gameplay/solve_selector.py`). Picking a solve
  pauses the replay at that solve's time so the map shows exactly the plan computed
  in that solve; while playing, the selector follows the replay.
- (2026-10-25) **Solver info card under the OCP card** (`gameplay/run_info_card.py`):
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

## 9. Gotchas already hit (don't repeat them)

- High Windows display scaling (175%) leaves only ~1100×600 logical pixels: the window
  fits itself to the screen; all screens must work at 900×560 (scroll areas, no fixed
  big sizes). Test small sizes.
- Qt: don't name custom widget properties `size` (clashes with QWidget.size); the
  button style property is `scale`. `&` in button text is a mnemonic: write `&&`.
  Some symbols (e.g. ❚❚) are missing from the fonts; use words or painted icons.
- acados: each compiled solver needs a unique name (`cq_N{N}`); solvers are not
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
- Don't override QWidget method names in subclasses (e.g. a `screen()` method on the main
  window broke Qt's `QWidget.screen()`; it is now `get_screen()`).
- Generated code (`engine_server/build/`), `.venv/`, `__pycache__/` are gitignored.

## 10. UI structure and content (what the player sees, as of 2026-10-25)

**Design system** (`controlquest/ui/theme.py`, `painting.py`, `widgets.py`):
- Warm cream background with a soft dot grid (graph-paper feel), white rounded cards with
  soft shadows, coral primary buttons (raised look), muted grey-blue secondary text.
- Mascot: a blue ball with eyes, blush and a smile (`painting.draw_ball`); the target is
  a yellow star; obstacles are beige blocks; MPC plans are a **coral dashed line with a
  dot per stage**; the solver's obstacle ellipse is a dashed outline.
- Fonts: Nunito → Segoe UI → Helvetica Neue → Arial (first one installed). Text roles:
  title, heading, subheading, subtitle, body, quote, caption, tag.
- Outcome colours: success green, crash/battery red, controller failure orange,
  time out grey.
- Window fits the screen (default 1280×800 logical), works down to 900×560; Esc = back.

**Screens** (`controlquest/screens/`, one file each):
1. **Title**: animated scene (the ball rolls over a block, dashed plan ahead of it,
   ellipse around the block, star at the end that sparkles), "ControlQuest" logo with
   "Quest" in coral, subtitle "Design the controller. Let the ball find its way.",
   buttons Play (big, coral) / How to play / Settings / Quit, an "MPC engine
   online/offline/outdated" pill bottom-left, version bottom-right.
2. **Level select**: "Choose a level", Free mode switch, total stars "x / 15", one card
   per level (number badge in the level's accent colour, title, topic tag, 3 stars);
   locked cards are greyed with a lock in the badge and "Finish level N to unlock";
   clicking a locked card explains how to unlock it. Cards reflow with window width.
3. **How to play**: four step cards (You are the engineer · Tune the controller · Run and
   watch the plan · Fix it, earn stars) and "How a run can end" (Success, Crash,
   Controller failure, Time out), then "Let's play".
4. **Settings**: Animations on/off; MPC engine address + "Test connection" + status;
   Reset progress (with confirmation).
5. **Level screen**: header "← Levels · Level N · Title · ★★★". Unplayable levels show a
   card with topic, briefing (quote), "What this level is about", "The playing field is
   still being built" (+ dev buttons with `CONTROLQUEST_DEV=1`).
   **Playable level** (`gameplay/level_play_widget.py`), three columns on wide windows:
   - left: the **map** (50 m field, grid every 5 m, labels every 10 m, start ring, target
     star, ball with trail, current plan, acceleration arrow, HUD "t = … |v| = …");
     under it the level's extras (Level 1: **battery bar**, drains, star mark = ★★★
     limit), the **replay bar** (Play/Pause, scrubber, time, speed 1×/2×/4×/8×,
     default 2×) and the **"MPC solve ‹ k › of n"** selector;
   - middle: **"The OCP your MPC solves"** (typeset math: min over u, stage cost ℓ, Q, P,
     "s.t." constraints; short notes and a symbol legend) and **"Solver info"** (this
     solve: plan cost J*, solve time, SQP iterations, status; whole run: solves, solve
     time avg/max, total solve time, iterations, total cost, engine time);
   - right: **Goal** (one paragraph), **Tune the weights** (one row per knob: symbol +
     name, a typeable value field, a log slider; Reset + Run ▶; a status line), and
     **Stuck?** with hints revealed one at a time (3 per level, the last almost the
     answer).
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

