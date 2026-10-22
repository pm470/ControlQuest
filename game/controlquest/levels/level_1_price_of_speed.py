"""Level 1: "The Price of Speed" (PRD 7, Level 1): the cost function is a trade-off.

Gameplay (map, knobs q_p, q_v, r, energy budget) is added here later via
`play_screen`; see levels/base.py.
"""

from .base import LevelInfo

LEVEL = LevelInfo(
    number=1,
    id="price_of_speed",
    title="The Price of Speed",
    topic="Cost trade-off",
    briefing=("The battery is small this time. Get to the target before the timer "
              "runs out, without using more energy than the battery holds."),
    concept=("The cost function is a trade-off: Q against R decides between fast and "
             "cheap, and only the ratios between the weights matter."),
    hints=(
        "Which term of the cost punishes hard accelerations?",
        "Make inputs more expensive compared with being far from the target.",
        "Raise r step by step until the energy fits; stop before you run out of time.",
    ),
    accent="coral",
)
