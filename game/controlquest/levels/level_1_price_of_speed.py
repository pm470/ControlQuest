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
from ..gameplay.level_intro import LevelIntro
from ..gameplay.level_play_widget import LevelPlayWidget, standard_ocp
from .base import LevelInfo


class PriceOfSpeedWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Bring the ball to the star and stop there within {d.t_limit:g} s, "
                f"without using more than {d.budget['energy']:g} units of energy. "
                r"The run stops when the battery is empty. Energy used $= \sum \Delta t\,\|u\|^2$.")

    def add_extras(self, column: QVBoxLayout) -> None:
        self.battery = BudgetBar("Battery", self.data.budget["energy"], self.data.pars.get("energy"))
        self.battery.setToolTip("Energy used so far (the run stops when the battery is empty). "
                                "The yellow tick: use less than this for ★★★.\n"
                                "\"Energy\" here is the effort measure Σ Δt‖u‖² (in m²/s³), "
                                "not physical energy in joules.")
        column.addWidget(self.battery)

    def update_extras(self, t: float) -> None:
        tr = self.result.trajectory
        self.battery.set_used(tr.interp(tr.energy, t))

    def debrief_visual(self, result):
        """The battery bar at the end of the run (Research debrief)."""
        bar = BudgetBar("Battery", self.data.budget["energy"], self.data.pars.get("energy"))
        bar.set_used(result.metrics.get("energy", 0.0))
        bar.setToolTip("Effort used in this run: Σ Δt‖u‖² (not physical energy). "
                       "The yellow tick: ★★★ par.")
        return bar

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s", f"limit {d.t_limit:g} s · ★★ ≤ {d.pars['time']:g} s"),
            ("Energy", f"{m['energy']:.2f}", f"battery {d.budget['energy']:g} · ★★★ ≤ {d.pars['energy']:g}"),
            ("Peak accel.", f"{m['max_accel']:.2f} m/s²", f"limit {d.a_max:g}"),
        ]


def build(ctx, level: LevelInfo) -> PriceOfSpeedWidget:
    return PriceOfSpeedWidget(ctx, level, load_level_data(level.id))


def intro(d) -> LevelIntro:
    """The level intro's numbers and math (first level: nothing is marked as new)."""
    return LevelIntro(
        goal=(f"Bring the ball to the star and stop there within {d.t_limit:g} s, using at most "
              f"{d.budget['energy']:g} units of energy " r"($\sum \Delta t\,\|u\|^2$)."),
        stars=("reach the star", f"within {d.pars['time']:g} s",
               f"also energy ≤ {d.pars['energy']:g}"),
        ocp=standard_ocp(d),
        fixed=rf"$N = {d.N}$, $P = {d.raw.get('terminal_factor', 10):g}\,Q$",
    )


LEVEL = LevelInfo(
    number=1,
    id="price_of_speed",
    title="The Price of Speed",
    topic="Cost trade-off",
    briefing=("The battery is small this time. Get to the target before the timer "
              "runs out, without using more energy than the battery holds."),
    concept=("The cost function is a trade-off. $Q$ prices being far from the target and moving "
             "fast; $R$ prices accelerating. Large $Q$ compared with $R$ gives a fast, aggressive "
             "controller; large $R$ gives a slow, economical one. Only the ratios matter: "
             "multiplying every weight by the same number changes nothing."),
    teaching=("The default weights ($q_p = 10$, $q_v = 1$, $r = 0.1$) make an aggressive controller: the "
              "ball accelerates and brakes at full power, and the battery runs empty just before "
              "the star. Make inputs more expensive relative to the position error (raise $r$ or "
              "lower $q_p$) so it brakes more gently, but not so gently that time runs out. The "
              "battery bar shows the energy used during the replay."),
    hints=(
        "Watch the arrow on the ball: it is the acceleration. How hard does it push at the start?",
        "Make inputs more expensive compared with being far from the target (raise $r$ or lower "
        "$q_p$). Scaling every weight by the same factor changes nothing.",
        "Try $q_p = 0.1$, $q_v = 1$, $r = 1$. For ★★★ the velocity weight $q_v$ helps like damping.",
    ),
    accent="coral",
    icon="bolt",
    play_screen=build,
    intro=intro,
)
