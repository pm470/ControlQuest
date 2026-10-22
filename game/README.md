# ControlQuest: the game

A PySide6 desktop app (runs on your computer) plus a small **MPC engine** server
(runs acados inside Docker). The design is in [`docs/PRD.md`](../docs/PRD.md).

**Status:** the menus are done: title screen, level select (stars, locks,
Free mode), how to play, settings, and a level screen with a "coming soon" card.
The engine server answers health checks; running levels is not implemented yet.

## Run it

You need Python 3.10+ on your computer.

```powershell
cd game
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_game.py
```

The menus work without the engine; the title screen shows "MPC engine offline".

### Start the MPC engine (Docker)

Docker Desktop must be running. From the repository root:

```powershell
.\game\engine_server\start_engine.ps1     # Windows PowerShell
./game/engine_server/start_engine.sh      # macOS / Linux / Git Bash
```

The scripts start the course image (override with `CONTROLQUEST_IMAGE`), mount
the repository at `/workspace` and map the engine to `http://127.0.0.1:8000`.
The title screen then shows "MPC engine online". If you run `server.py` with
normal Python (no Docker), the game shows "online (acados missing)": fine for UI
work, but levels will need the real engine.

### Options (environment variables)

| Variable | Effect |
|---|---|
| `CONTROLQUEST_DEV=1` | developer helpers, e.g. "pretend I finished with ★★" buttons on the level screen (to test unlocking) |
| `CONTROLQUEST_ENGINE_URL` | engine address (default `http://127.0.0.1:8000`; can also be changed in Settings) |
| `CONTROLQUEST_IMAGE`, `CONTROLQUEST_PORT` | Docker image / host port used by the start scripts |

PowerShell: `$env:CONTROLQUEST_DEV = "1"; python run_game.py`

## How the code is organised

Every concern has its own file, so two people rarely edit the same file.

```
game/
├── run_game.py                  entry point
├── requirements.txt
├── controlquest/
│   ├── app.py                   creates QApplication, services, main window
│   ├── main_window.py           stack of screens + navigation (Esc = back)
│   ├── core/                    no visuals
│   │   ├── config.py            constants (window size, engine URL, timings)
│   │   ├── navigation.py        ScreenId: the names of all screens
│   │   ├── game_state.py        stars per level, unlocking, free mode, settings
│   │   └── context.py           AppContext = state + engine + levels, given to every screen
│   ├── ui/                      look and feel
│   │   ├── theme.py             colours, fonts, the global stylesheet
│   │   ├── painting.py          drawings: ball mascot, stars, blocks, plan line, lock
│   │   ├── widgets.py           shared widgets: Button, Card, ToggleSwitch, StarRow, ...
│   │   ├── level_card.py        the card of one level in the level select
│   │   └── title_scene.py       the animation on the title screen
│   ├── screens/                 one file per full-window screen
│   │   ├── base_screen.py       BaseScreen: on_enter/on_leave, go(...), go_back()
│   │   ├── registry.py          ScreenId -> screen class (one line per screen)
│   │   ├── title_screen.py
│   │   ├── level_select_screen.py
│   │   ├── how_to_play_screen.py
│   │   ├── settings_screen.py
│   │   └── level_screen.py      hosts a level (briefing / later: the gameplay)
│   ├── levels/                  one file per level, found automatically
│   │   ├── base.py              LevelInfo: what a level file provides
│   │   ├── level_1_price_of_speed.py
│   │   ├── level_2_brake_check.py
│   │   ├── level_3_dead_end.py
│   │   ├── level_4_heavy_ball.py
│   │   └── level_5_crosswind.py
│   └── engine/                  talking to the MPC engine
│       ├── protocol.py          the messages (PRD 9.4): EngineStatus, RunRequest, RunResult
│       └── client.py            EngineClient: async HTTP (health polling, request_run)
└── engine_server/               runs INSIDE Docker
    ├── server.py                HTTP server: GET /health, POST /run (501 for now)
    ├── start_engine.ps1
    └── start_engine.sh
```

Rules that keep it tidy:
- **Screens never talk to each other.** They call `self.go(ScreenId.X, payload)`;
  `main_window.py` does the switching. Shared data lives in `ctx.state`.
- **No colours or sizes inside screens.** Use `ui/theme.py` constants and the
  stylesheet roles: `label(text, "heading")`, `Button(text, variant="primary")`.
- **UI and engine meet only in `engine/protocol.py`** (and `engine_server/server.py`
  on the other side). Change both together, and keep the PRD 9.4 formats in sync.
- **Numerical / MPC code goes into the engine**, never into the UI.

## Adding things

**A new level:** copy a `levels/level_*.py` file, change `number`, `id`, texts.
It shows up in the level select automatically; no other file changes.

**Making a level playable:** in the level's file, write a function
`build(ctx, level) -> QWidget` (or import it from a gameplay module) and set
`play_screen=build` in its `LevelInfo`. The level screen then shows that widget
instead of the "coming soon" card. Shared gameplay parts (map view, knob panel,
playback, result panel) should become their own modules, e.g.
`controlquest/gameplay/map_view.py`, `knob_panel.py`, `playback.py`, `result_panel.py`.

**A new screen:** add an id in `core/navigation.py`, write
`screens/<name>_screen.py` (subclass `BaseScreen`, set `back_target`), and add
one line to `screens/registry.py`.

**A new engine endpoint:** add the handler in `engine_server/server.py`, the
message dataclass in `engine/protocol.py`, and a method in `engine/client.py`.

## Working as a team

- One feature branch per task (`git checkout -b feature/map-view`); merge into
  the shared branch often, in small pieces.
- Natural split (PRD 12): one person on `engine_server/` (+ the MPC code it will
  import), the other on `controlquest/` (screens, gameplay widgets). The contract
  between you is `engine/protocol.py`.
- The only files both of you may need to touch are `screens/registry.py`,
  `core/navigation.py` and `engine/protocol.py`; they are short on purpose, so
  merge conflicts there are one-line fixes.
- Before pushing: run the game once and click through the screens you changed,
  at a small window size too (the window can be as small as 900×560 on laptops
  with high display scaling).
