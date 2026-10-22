"""App-wide constants. No Qt here, so anything can import it.

Two environment variables are read at start-up:
- CONTROLQUEST_ENGINE_URL: address of the MPC engine (default http://127.0.0.1:8000)
- CONTROLQUEST_DEV=1: shows developer helpers (e.g. "pretend I passed" buttons)
"""

from __future__ import annotations

import os

WINDOW_TITLE = "ControlQuest"
WINDOW_DEFAULT_SIZE = (1280, 800)  # preferred; shrunk to fit the screen (Windows scaling!)
WINDOW_MIN_SIZE = (900, 560)  # all screens must stay usable down to this size

DEFAULT_ENGINE_URL = os.environ.get("CONTROLQUEST_ENGINE_URL", "http://127.0.0.1:8000")
ENGINE_POLL_INTERVAL_MS = 5000  # how often the menu re-checks the engine
ENGINE_TIMEOUT_MS = 1500  # health-check timeout
ENGINE_RUN_TIMEOUT_MS = 30000  # timeout for one level run (PRD 9.5: < 2 s expected)

ANIMATION_FRAME_MS = 33  # ~30 fps for decorative animations

MAX_STARS = 3  # PRD section 6

DEV_MODE = os.environ.get("CONTROLQUEST_DEV", "") not in ("", "0")
