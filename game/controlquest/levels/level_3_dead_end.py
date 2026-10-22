"""Level 3: "Dead End" (PRD 7, Level 3): nonconvexity and local optima.

Gameplay (U-shaped trap, placing up to 3 waypoints) is added here later via
`play_screen`; see levels/base.py.
"""

from .base import LevelInfo

LEVEL = LevelInfo(
    number=3,
    id="dead_end",
    title="Dead End",
    topic="Local optima",
    briefing=("The direct route looks open... it isn't. Help the controller with up to "
              "3 waypoints."),
    concept=("With obstacles the OCP is nonconvex. A short-horizon MPC is a local planner "
             "and can get trapped; a rough higher-level route (waypoints) gets it out."),
    hints=(
        "The controller only sees 3 seconds ahead. What does it see inside the U?",
        "Give it an intermediate goal it can reach without entering the trap.",
        "One well-placed waypoint beside the U is enough for three stars.",
    ),
    accent="lilac",
)
