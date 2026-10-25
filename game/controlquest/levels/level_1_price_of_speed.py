"""Level 1: "The Price of Speed" (PRD 7, Level 1): the cost function is a trade-off.

Numbers (start, target, limits, battery, pars, knobs) live in
game/level_data/price_of_speed.json, shared with the engine. The engine's rules
for this level are in engine_server/level_rules/price_of_speed.py.
This file only adds what the player sees on top of the standard level layout:
the goal text, the battery bar, and the rows of the result card.
"""

from PySide6.QtWidgets import QVBoxLayout

from ..gameplay.budget_bar import BudgetBar
from ..gameplay.level_data import load_level_data
from ..gameplay.level_play_widget import LevelPlayWidget
from ..ui.widgets import Card
from .base import LevelInfo


class PriceOfSpeedWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Bring the ball to the star and stop there within {d.t_limit:g} s, "
                f"without using more than {d.budget['energy']:g} units of energy. "
                f"The run stops when the battery is empty. Energy used = Σ Δt·|u|².")

    def add_extras(self, column: QVBoxLayout) -> None:
        card = Card(padding=12, spacing=0, shadow=False)
        self.battery = BudgetBar("Battery", self.data.budget["energy"], self.data.pars.get("energy"))
        self.battery.setToolTip("Energy used so far. The dashed star line: use less than this "
                                "for ★★★.")
        card.body.addWidget(self.battery)
        column.addWidget(card)

    def update_extras(self, t: float) -> None:
        tr = self.result.trajectory
        self.battery.set_used(tr.interp(tr.energy, t))

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s", f"limit {d.t_limit:g} s · ★★ ≤ {d.pars['time']:g} s"),
            ("Energy", f"{m['energy']:.2f}", f"battery {d.budget['energy']:g} · ★★★ ≤ {d.pars['energy']:g}"),
            ("Peak accel.", f"{m['max_accel']:.2f} m/s²", f"limit {d.a_max:g}"),
        ]


def build(ctx, level: LevelInfo) -> PriceOfSpeedWidget:
    return PriceOfSpeedWidget(ctx, level, load_level_data(level.id))


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
        "Watch the arrow on the ball: it is the acceleration. How hard does it push at the start?",
        "Make inputs more expensive compared with being far from the target (raise r or lower "
        "q_p). Scaling every weight by the same factor changes nothing.",
        "Try q_p = 0.1, q_v = 1, r = 1. For ★★★ the velocity weight q_v helps like damping.",
    ),
    accent="coral",
    play_screen=build,
)
