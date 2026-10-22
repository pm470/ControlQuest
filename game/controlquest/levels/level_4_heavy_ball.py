"""Level 4: "Heavy Ball" (PRD 7, Level 4): model mismatch, constraint tightening
vs a better model.

Gameplay (parking bay, obstacle margin, model gain g, test drive) is added here
later via `play_screen`; see levels/base.py.
"""

from .base import LevelInfo

LEVEL = LevelInfo(
    number=4,
    id="heavy_ball",
    title="Heavy Ball",
    topic="Model mismatch",
    briefing=("Someone swapped the ball. It looks the same but responds less to the "
              "motors. Park it in the bay without touching the walls."),
    concept=("The controller plans with a model. If the real system differs, safe plans "
             "crash in reality. Fix it with a safety margin (robust, slower) or a better "
             "model (identify the real parameter)."),
    hints=(
        "Watch where the plan says the ball will be, and where it actually is.",
        "A test drive tells you how strongly the real ball responds.",
        "Set the model gain to what you measured, then shrink the margin.",
    ),
    accent="mint",
)
