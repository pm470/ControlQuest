"""Level 2: "Brake Check" (PRD 7, Level 2): horizon length, recursive feasibility,
terminal constraint.

Gameplay (horizon N dropdown, terminal-stop toggle) is added here later via
`play_screen`; see levels/base.py.
"""

from .base import LevelInfo

LEVEL = LevelInfo(
    number=2,
    id="brake_check",
    title="Brake Check",
    topic="Horizon & feasibility",
    briefing=("New, faster ball, weaker brakes. The target is right in front of the "
              "wall. Stop on it."),
    concept=("The horizon has to cover the braking distance, or the controller sees the "
             "problem too late and runs out of feasible plans. A terminal constraint "
             "restores safety, but makes the controller conservative."),
    hints=(
        "How far does the ball travel before it can stop from full speed?",
        "Compare the braking distance with how far the plan reaches ahead.",
        "Either look further ahead, or force every plan to end at rest.",
    ),
    accent="sky",
)
