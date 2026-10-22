"""Level 5: "Crosswind" (PRD 7, Level 5): feedback, i.e. why we re-plan.

Gameplay (wind, re-plan interval k, solve budget) is added here later via
`play_screen`; see levels/base.py.
"""

from .base import LevelInfo

LEVEL = LevelInfo(
    number=5,
    id="crosswind",
    title="Crosswind",
    topic="Feedback",
    briefing=("It's windy. You have a limited compute budget: every re-plan uses one "
              "solve. Get through the gap."),
    concept=("MPC is feedback because it re-plans from the measured state. Re-plan too "
             "rarely and the ball runs open-loop while the wind pushes it off its plan."),
    hints=(
        "Between two re-plans, who corrects for the wind?",
        "Re-planning every step is perfect, but too expensive.",
        "Find the largest re-plan interval that still gets through the gap.",
    ),
    accent="sun",
)
