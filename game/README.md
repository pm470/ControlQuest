# ControlQuest: the game

A PySide6 desktop app (runs on your computer) plus a small **MPC engine** server
(runs acados inside Docker). The design is in [`docs/PRD.md`](../docs/PRD.md).

**Status:** menus done; **Levels 1, 3, 4 and 5** ("The Price of Speed", "Dead End",
"Heavy Ball", "Crosswind") are playable end to end (tune knobs / pick a fix / place
waypoints → Run → MPC computes the run in Docker → replay with the live plan → result
card, stars, unlock). Level 2 shows a "coming soon" card.

## Run it

You need Docker Desktop (for the engine) and Python 3.10+ (for the window).

**1. Start the MPC engine** (from the repository root, Docker Desktop running):

```powershell
.\game\engine_server\start_engine.ps1     # Windows PowerShell
./game/engine_server/start_engine.sh      # macOS / Linux / Git Bash
```

It compiles the acados solver (a few seconds), then prints `listening on ...`.
Leave this terminal open; every run prints one line there.

**2. Start the game** (second terminal):

```powershell
cd game
python -m venv .venv                # first time only
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt     # first time only
python run_game.py
```

The title screen shows "MPC engine online" once the engine is up.
**After changing engine code, stop the engine (Ctrl+C) and start it again**; the
game can stay open.

### Options (environment variables)

| Variable | Effect |
|---|---|
| `CONTROLQUEST_DEV=1` | developer helpers, e.g. "pretend I finished with ★★" on unplayable levels |
| `CONTROLQUEST_ENGINE_URL` | engine address (default `http://127.0.0.1:8000`; also in Settings) |
| `CONTROLQUEST_IMAGE`, `CONTROLQUEST_PORT` | Docker image / host port used by the start scripts |

## How the code is organised

```
game/
├── level_data/                  ONE JSON PER LEVEL, read by BOTH game and engine
│   ├── price_of_speed.json          start, target, limits, time limit, battery, pars, knobs, checks
│   ├── dead_end.json                + blocks (4 corners each), locked weights/margin, waypoint rules
│   ├── heavy_ball.json              + plant (hidden real gain g_true), test drive, margin/g knobs
│   └── crosswind.json               + wind (constant + seeded gusts), solve budget, k/margin knobs
│
├── controlquest/                THE GAME WINDOW (host, no acados)
│   ├── app.py, main_window.py       start-up, screen switching (Esc = back)
│   ├── core/                        config, ScreenId, GameState (stars/unlocks), AppContext
│   ├── ui/                          theme (colours, stylesheet), painting (ball, stars...), widgets,
│   │                                math_render (LaTeX-style formulas via matplotlib mathtext)
│   ├── screens/                     title, level select, how to play, settings, level screen
│   ├── levels/                      one file per level: LevelInfo (+ play_screen when playable)
│   │   ├── level_1_price_of_speed.py    Level 1's goal text, battery bar, result rows
│   │   ├── level_3_dead_end.py          Level 3: fix selector, N / waypoint controls, OCP per fix
│   │   ├── level_4_heavy_ball.py        Level 4: margin + g knobs, test drive, OCP with g
│   │   └── level_5_crosswind.py         Level 5: re-plan interval k + margin, compute-budget bar
│   ├── gameplay/                    reusable parts of a playable level
│   │   ├── level_play_widget.py         layout + the Run → engine → replay → result flow
│   │   ├── map_view.py                  the field in metres: blocks + dashed ellipses, waypoints,
│   │   │                                ball, trail, dashed plan, accel arrow, crash marker
│   │   ├── waypoint_editor.py           click / drag / right-click waypoints on the map (Level 3)
│   │   ├── fix_selector.py              "Choose a fix": one selectable card per fix (Level 3)
│   │   ├── comparison_card.py           "Your experiments": best run per fix (Level 3)
│   │   ├── obstacles.py                 block corners -> the solver's ellipse (drawing, clicks)
│   │   ├── knob_panel.py                log sliders (+ dropdowns for "choices" knobs, e.g. N)
│   │   ├── playback.py                  replay clock + play/pause/scrub/speed bar
│   │   ├── result_panel.py              outcome, stars, metrics, "what happened"
│   │   ├── ocp_card.py                  "The OCP your MPC solves" card (typeset math)
│   │   ├── run_info_card.py             "Solver info": J*, solve time, iterations, run statistics
│   │   ├── solve_selector.py            "MPC solve ‹ k › of n": inspect one solve's plan
│   │   ├── budget_bar.py                battery-style budget bar
│   │   └── level_data.py                reads level_data/<id>.json
│   └── engine/                      talking to the engine
│       ├── protocol.py                  RunRequest / RunResult / Trajectory (the contract)
│       └── client.py                    async HTTP: health polling, request_run -> ticket
│
└── engine_server/               THE MPC ENGINE (runs in Docker, has acados)
    ├── server.py                    HTTP only: GET /health, POST /run, POST /test_drive (L4)
    ├── runner.py                    run_level(id, knobs): level id -> rules; solver cache
    ├── calibrate.py                 check / tune a level from the command line
    ├── level_rules/                 game rules per level (stop rules, stars, explanations)
    │   ├── common.py                    load level file, knobs -> weights, result JSON
    │   ├── price_of_speed.py            Level 1: battery, stars, "what happened"
    │   ├── dead_end.py                  Level 3: the chosen fix (none / horizon N / waypoints),
    │                                    stars, local-optimum explanations
    │   ├── heavy_ball.py                Level 4: plant with g_true, test drive, 1 s-ahead
    │                                    prediction error, stars, mismatch explanations
    │   └── crosswind.py                 Level 5: seeded wind, solve budget, drift, stars
    ├── mpc/                         pure MPC, knows nothing about the game
    │   ├── model.py                     double integrator (CasADi); parameters: model gain g
    │   │                                + 6 obstacle-ellipse slots (cx, cy, E11, E12, E22)
    │   ├── ocp.py                       the acados OCP recipe for one problem shape (N, dt),
    │   │                                incl. soft ellipse constraints (unused slots far away)
    │   ├── obstacles.py                 block corners -> min-area ellipse; block crash check
    │   ├── controller.py                MPCController (runtime weights/bounds/target, solve)
    │   │                                + SolverCache (compile once per shape)
    │   └── closed_loop.py               simulate: real ball (plant) + MPC, step by step;
    │                                    waypoint switching, block crashes, re-plan interval
    │                                    (open-loop between solves), disturbance (wind)
    └── build/                       generated C code (gitignored, created automatically)
```

### What happens when you press Run (Level 1)

1. `gameplay/level_play_widget.py` sends `RunRequest("price_of_speed", {q_p, q_v, r})`
   through `engine/client.py` (HTTP POST to the engine).
2. `engine_server/server.py` → `runner.run_level` → `level_rules/price_of_speed.run`:
   loads `level_data/price_of_speed.json`, turns knobs into Q, R, P
   (`common.weights`), loads them into the cached solver (`common.configured_controller`).
3. `mpc/closed_loop.simulate` runs the loop: solve OCP → apply first input → move the
   real ball → repeat, until success / time out / failure / the level's stop rule
   (battery empty).
4. The rules file computes metrics, stars and explanation sentences; the server
   returns everything as JSON (`RunResult`, with every state and every plan).
5. The game replays it: `playback.py` is the clock, `map_view.py` draws the ball and
   the plan of that moment, `level_1_...py` drains the battery bar; at the end
   `result_panel.py` shows the card and `GameState` saves the stars.

### Rules that keep it tidy
- **Screens never talk to each other**; they call `self.go(ScreenId.X, payload)`.
- **No colours or sizes in screens**: use `ui/theme.py` and the stylesheet roles.
- **UI and engine meet only in `engine/protocol.py`** ↔ `level_rules/common.py` /
  `server.py`. Change both sides together.
- **Level numbers live only in `level_data/*.json`**, never in Python.
- **MPC code (`mpc/`) never knows about levels**; game rules live in `level_rules/`.

## Changing things

| I want to... | Edit | Then |
|---|---|---|
| change Level 1's numbers (time limit, battery, pars, start/target, slider ranges) | `level_data/price_of_speed.json` | restart engine + game; run `calibrate.py` |
| change stars or explanation texts of Level 1 | `engine_server/level_rules/price_of_speed.py` | restart engine |
| change the MPC (cost, constraints, solver options) | `engine_server/mpc/ocp.py`, `controller.py` | restart engine (it recompiles) |
| change the simulated real ball | `engine_server/mpc/closed_loop.py` (`plant_step`) | restart engine |
| change what the player sees in Level 1 | `controlquest/levels/level_1_price_of_speed.py` | restart game |
| change the shared level layout / map / replay | `controlquest/gameplay/*` | restart game |

**Check a level without the game** (inside the engine container, or with
`docker run ... python calibrate.py ...` like the start script):

```bash
python calibrate.py price_of_speed              # default fails? reference passes?
python calibrate.py price_of_speed --sweep      # time/energy table over the weights
python calibrate.py price_of_speed q_p=0.3 r=1  # one run, prints the explanation
python calibrate.py dead_end fix=waypoints wp=35,40   # Level 3: one run with a fix
python calibrate.py dead_end fix=horizon N=100
```

## Adding a playable level (e.g. Level 2)

1. `level_data/<id>.json`: copy Level 1's file and change the numbers/knobs.
2. Engine: `level_rules/<id>.py` with `run(level, knobs, cache)` (copy Level 1's),
   then one line in `runner.py` `RULES`. New MPC features (e.g. horizon N per run,
   terminal constraint, obstacles, model gain, wind) go into `mpc/` as options.
3. Game: in `controlquest/levels/level_2_....py` subclass `LevelPlayWidget`
   (goal text, `ocp_spec()` if the OCP differs from the standard one, extras, result
   rows), add `build()` and set `play_screen=build`.
   Knob ranges: `max ≤ max(50, 3 × reference value)` (team rule, see AGENTS.md).
   Obstacles: add `"blocks"` (4 corners each, at most 6) to the level file; the engine
   and the map pick them up. Fixed values that are not knobs go into `"locked"`.
   Controls other than sliders: override `controls_title()`, `add_controls()`,
   `waypoints()`, `reset_controls()`, `set_controls_enabled()` (see `level_3_dead_end.py`).
4. `python calibrate.py <id>` until the default fails the intended way and the
   reference gets 3 stars; write both into the level file's `checks`.

## Working as a team

- One feature branch per task; merge often, in small pieces.
- Natural split: one person on `engine_server/`, the other on `controlquest/`;
  the contract is `engine/protocol.py` + the level JSON files.
- Shared one-line registries: `screens/registry.py`, `core/navigation.py`,
  `engine_server/runner.py` (`RULES`). Conflicts there are one-line fixes.
- Before pushing: run the game and click through what you changed, also at a
  small window size (900×560), and run `calibrate.py` for levels you touched.
