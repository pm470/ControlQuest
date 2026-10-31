"""Level 5: "Crosswind" (PRD 7, Level 5): feedback, i.e. why we re-plan.

Numbers (blocks, wind, limits, weights, the solve budget, pars, knobs) live in
game/level_data/crosswind.json, shared with the engine. The engine's rules are in
engine_server/level_rules/crosswind.py.

The wind pushes the ball; the controller does not know about it. The player picks
the re-plan interval k (solve every k samples, open-loop in between) and the obstacle
margin. Every solve costs one unit of the compute budget (bar under the map). The
map shows the wind arrow and the open-loop part of the plan being executed (solid).
"""

from PySide6.QtWidgets import QVBoxLayout

from ..gameplay.budget_bar import BudgetBar
from ..gameplay.level_data import load_level_data
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.ocp_card import OcpSpec
from ..ui.widgets import Card, label
from .base import LevelInfo


class CrosswindWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Get through the gap and stop on the star within {d.t_limit:g} s. The wind pushes "
                f"the ball, and every re-plan costs one of {d.budget['solves']:g} solves; the run stops "
                f"when they are used up. ★★: within {d.pars['time']:g} s; ★★★: also with at most "
                f"{d.pars['solves']:g} solves.")

    def controls_title(self) -> str:
        return "Tune the controller"

    def add_controls(self, layout: QVBoxLayout) -> None:
        self.k_note = label("", "caption", wrap=True)
        layout.addWidget(self.k_note)
        self.map.show_wind = True
        self.knobs.changed.connect(self._on_knobs)
        self._on_knobs()

    def _on_knobs(self) -> None:
        v = self.knobs.values()
        k = int(v["k"])
        rate = 1 / (k * self.data.dt)
        self.k_note.setText(f"k = {k}: re-plan every {k * self.data.dt:g} s ({rate:g} "
                            f"solve{'' if rate == 1 else 's'} per second). In between, the ball "
                            "follows the last plan open-loop (solid line on the map).")
        self.map.set_margin(v["margin"])
        self.refresh_ocp()

    # --- under the map: the compute budget -------------------------------------------------
    def add_extras(self, column: QVBoxLayout) -> None:
        card = Card(padding=12, spacing=0, shadow=False)
        self.budget = BudgetBar("Compute budget", self.data.budget["solves"], self.data.pars.get("solves"),
                                unit=" solves")
        self.budget.setToolTip("MPC solves used so far. The dashed star line: use fewer than this "
                               "for ★★★.")
        card.body.addWidget(self.budget)
        column.addWidget(card)

    def update_extras(self, t: float) -> None:
        self.budget.set_used(self.result.trajectory.solves_until(t))

    # --- the OCP --------------------------------------------------------------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        n, lk = d.N, d.locked
        v = self.knobs.values() if hasattr(self, "knobs") else {k.name: k.default for k in d.knobs}
        k, m = int(v["k"]), v["margin"]
        (x0, y0), (x1, y1) = d.workspace
        return OcpSpec(
            objective=[
                rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
                rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2",
                rf"\ell(x,u) = {lk['q_p']:g}\,\|p-p_{{\star}}\|^2 + {lk['q_v']:g}\,\|v\|^2 "
                rf"+ {lk['r']:g}\,\|u\|^2",
                rf"P = {d.raw.get('terminal_factor', 10):g}\,Q",
            ],
            constraints=[
                r"x_0 = \hat{x}",
                r"x_{k+1} = f(x_k,\,u_k)\quad \mathrm{(no\ wind\ in\ the\ model)}",
                rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
                rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
                rf"(p_k-c_j)^{{T}} E_j(m)\, (p_k-c_j) \geq 1,\quad m = {m:.2g}\ \mathrm{{m}}",
            ],
            notes=(f"Solved only every {k} sample(s) ({k * d.dt:g} s) from the measured state; in between "
                   f"the ball gets u₁, u₂, … of the last plan, open-loop. {n} steps ({n * d.dt:g} s) ahead."),
            legend=["E_j(m): ellipse around block j, each semi-axis enlarged by the margin m · "
                    "the wind acts on the real ball only"],
        )

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s", f"★★ ≤ {d.pars['time']:g} s"),
            ("Solves", f"{m.get('solves_used', 0)} / {m.get('solve_budget', 0)}",
             f"★★★ ≤ {d.pars['solves']:g} · k = {m.get('k', 1)}"),
            ("Off the plan", f"{m.get('max_drift', 0):.2f} m", f"max, margin {m.get('margin', 0):g} m"),
        ]


def build(ctx, level: LevelInfo) -> CrosswindWidget:
    return CrosswindWidget(ctx, level, load_level_data(level.id))


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
        "Re-planning every step is perfect, but too expensive. Watch the budget bar.",
        "Re-plan every second (k = 10) and give the wind a little room: a margin of about 0.3 m.",
    ),
    accent="sun",
    play_screen=build,
)
