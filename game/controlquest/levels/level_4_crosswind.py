"""Level 4: "Crosswind" (PRD 7, Level 4; Level 5 until "Heavy Ball" was removed on 2026-11-19): feedback, i.e. why we re-plan.

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
from ..gameplay.level_intro import LevelIntro
import math

from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.analysis_panel import (Events, PlotSpec, RefLine, Series, Shade, distances,
                                       speeds, state_times)
from ..ui import theme
from ..gameplay.ocp_card import STATE_LEGEND, OcpSpec
from ..ui.math_text import math_text
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
        self.k_note = math_text("", "caption")
        layout.addWidget(self.k_note)
        self.map.show_wind = True
        self.knobs.changed.connect(self._on_knobs)
        self._on_knobs()

    def _on_knobs(self) -> None:
        v = self.knobs.values()
        k = int(v["k"])
        rate = 1 / (k * self.data.dt)
        self.k_note.setText(f"$k = {k}$: re-plan every {k * self.data.dt:g} s ({rate:g} "
                            f"solve{'' if rate == 1 else 's'} per second). In between, the ball "
                            "follows the last plan open-loop (solid line on the map).")
        self.map.set_margin(v["margin"])
        self.refresh_ocp()

    # --- under the map: the compute budget -------------------------------------------------
    def add_extras(self, column: QVBoxLayout) -> None:
        self.budget = BudgetBar("Compute budget", self.data.budget["solves"], self.data.pars.get("solves"),
                                unit=" solves")
        self.budget.setToolTip("MPC solves used so far (the run stops when they are used up). "
                               "The yellow tick: use fewer than this for ★★★.")
        column.addWidget(self.budget)

    def update_extras(self, t: float) -> None:
        self.budget.set_used(self.result.trajectory.solves_until(t))

    def debrief_visual(self, result):
        """The compute-budget bar at the end of the run (Research debrief)."""
        bar = BudgetBar("Compute budget", self.data.budget["solves"], self.data.pars.get("solves"),
                        unit=" solves")
        bar.set_used(result.metrics.get("solves_used", result.trajectory.n_solves))
        bar.setToolTip("MPC solves used in this run. The yellow tick: ★★★ par.")
        return bar

    # --- the OCP --------------------------------------------------------------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        v = self.knobs.values() if hasattr(self, "knobs") else {k.name: k.default for k in d.knobs}
        return ocp(d, int(v["k"]), v["margin"])

    def analysis_plots(self, result):
        return crosswind_plots(result, self.data)

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s", f"★★ ≤ {d.pars['time']:g} s"),
            ("Solves", f"{m.get('solves_used', 0)} / {m.get('solve_budget', 0)}",
             f"★★★ ≤ {d.pars['solves']:g} · $k = {m.get('k', 1)}$"),
            ("Off the plan", f"{m.get('max_drift', 0):.2f} m",
             f"max vs the plan in force, margin $m = {m.get('margin', 0):g}$ m"),
        ]


def wind_bound(d) -> float:
    """Largest possible wind acceleration |w| [m/s^2] from the level file: per axis the constant
    part plus the gust amplitude (gusts are uniform in +-amplitude)."""
    w = d.raw["wind"]
    return math.hypot(*(abs(c) + abs(a) for c, a in zip(w["constant"], w["gust_amplitude"])))


def prediction_segments(tr, w_max: float):
    """The engine's prediction error (trajectory.drift, engine >= 0.14.0) and its bound, one
    segment per plan: plan i is in force for the samples k with steps[i] < k <= steps[i+1] (the
    last sample is the re-planning instant, compared with this OUTGOING plan); tau = (k -
    steps[i]) dt. Between re-plans the plant gets exactly the planned inputs and differs from
    the model only by the wind, so the error is the double integral of the wind: at most
    0.5 w_max tau^2. NaN separates the segments; t = 0 (no prediction) is left out."""
    steps, n, dt = tr.steps, len(tr.x) - 1, tr.dt
    t, err, bound = [], [], []
    for i, s in enumerate(steps):
        end = steps[i + 1] if i + 1 < len(steps) else n
        for k in range(s + 1, end + 1):
            t.append(tr.t[k])
            err.append(tr.drift[k])
            bound.append(0.5 * w_max * ((k - s) * dt) ** 2)
        if end > s:
            t.append(math.nan)
            err.append(math.nan)
            bound.append(math.nan)
    return t, err, bound


def crosswind_plots(result, d) -> list:
    """The Analysis tab of Crosswind (also used by the tests)."""
    tr = result.trajectory
    w = wind_bound(d)
    t, err, bound = prediction_segments(tr, w)
    replans = [s * tr.dt for s in tr.steps[1:]]
    solve_t = [s * tr.dt for s in tr.steps]
    count = list(range(1, len(solve_t) + 1))
    budget = tr.solve_budget or int(d.budget["solves"])
    return [
        PlotSpec(
            title="Prediction error",
            description=(r"Distance between the ball and the prediction of the plan in force, up to "
                         r"the moment that plan is replaced ($\tau$: time since it was solved). "
                         r"Between re-plans the ball gets exactly the planned inputs and only the wind "
                         rf"($|w| \leq {w:.1f}$ m/s²) differs from the model, so the error stays below "
                         r"the bound, which grows with $\tau^2$."),
            y_label="prediction error [m]", t_end=tr.duration,
            series=(Series(t, err, "prediction error", theme.PLOT_1, style="segments"),
                    Series(t, bound, r"bound $\frac{1}{2} w_{\max} \tau^2$", theme.PLOT_GUIDE,
                           style="segments", dashed=True)),
            events=(Events(replans, "re-plan", theme.PLOT_2, rug=True),), legend_above=True),
        PlotSpec(
            title="MPC solves",
            description=("Every solve uses one unit of the compute budget; the run stops when it is "
                         "used up. ★★★ needs at most the threshold."),
            y_label="solves so far", t_end=tr.duration,
            series=(Series(solve_t + [tr.duration], count + [len(count)], "solves", theme.PLOT_1,
                           style="step"),),
            ref_lines=(RefLine(budget, f"budget {budget:g} solves", theme.PLOT_LIMIT),
                       RefLine(d.pars["solves"], f"★★★ threshold {d.pars['solves']:g}", theme.PLOT_PAR))),
    ]


def ocp(d, k: int, m: float, intro: bool = False) -> OcpSpec:
    """The OCP with re-plan interval k and obstacle margin m. intro=True: the level intro's
    version (the re-plan interval and "no wind in the model" marked as new)."""
    n, lk = d.N, d.locked
    (x0, y0), (x1, y1) = d.workspace
    if intro:  # touching highlights read as one: no gaps between the new parts
        replan = (rf"\new{{\mathrm{{solve\ every}}}}\newknob{{k}}{{k = {k}}}"
                  rf"\new{{\mathrm{{samples}}}}")
        no_wind = r"\new{\mathrm{(no\ wind\ in\ the\ model)}}"
    else:
        replan = rf"\mathrm{{solve\ every}}\ \knob{{k}}{{k = {k}}}\ \mathrm{{samples}}"
        no_wind = r"\mathrm{(no\ wind\ in\ the\ model)}"
    return OcpSpec(
        objective=[
            rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
            rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2",
            rf"\ell(x,u) = {lk['q_p']:g}\,\|p-p_{{\star}}\|^2 + {lk['q_v']:g}\,\|v\|^2 "
            rf"+ {lk['r']:g}\,\|u\|^2",
            rf"P = {d.raw.get('terminal_factor', 10):g}\,Q,\quad {replan}",
        ],
        constraints=[
            r"x_0 = \hat{x}",
            rf"x_{{k+1}} = f(x_k,\,u_k)\quad {no_wind}",
            rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
            rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
            rf"(p_k-c_j)^{{T}} E_j(\knob{{margin}}{{m}})\, (p_k-c_j) \geq 1,\quad "
            rf"\knob{{margin}}{{m = {m:.2g}\ \mathrm{{m}}}}",
        ],
        notes=(f"Solved only every $k = {k}$ sample(s) ({k * d.dt:g} s) from the measured state; in "
               r"between the ball gets $u_1, u_2, \ldots$ of the last plan, open-loop. "
               f"$N = {n}$ steps ({n * d.dt:g} s) ahead."),
        legend=[("E_j(m)", "ellipse around block $j$, each half axis enlarged by the margin $m$"),
                *STATE_LEGEND, "The wind acts on the real ball only. The ellipse constraints are soft "
                "(large $L_1$ penalty)."],
    )


def build(ctx, level: LevelInfo) -> CrosswindWidget:
    return CrosswindWidget(ctx, level, load_level_data(level.id))


def intro(d) -> LevelIntro:
    """The level intro's numbers and math."""
    lk, knobs = d.locked, {k.name: k.default for k in d.knobs}
    return LevelIntro(
        goal=(f"Get through the gap and stop on the star within {d.t_limit:g} s, using at most "
              f"{d.budget['solves']:g} solves."),
        stars=("reach the star", f"within {d.pars['time']:g} s",
               f"also ≤ {d.pars['solves']:g} solves"),
        ocp=ocp(d, int(knobs["k"]), knobs["margin"], intro=True),
        fixed=(f"$q_p = {lk['q_p']:g}$, $q_v = {lk['q_v']:g}$, $r = {lk['r']:g}$, "
               rf"$P = {d.raw.get('terminal_factor', 10):g}\,Q$, $N = {d.N}$"),
    )


LEVEL = LevelInfo(
    number=4,
    id="crosswind",
    title="Crosswind",
    topic="Feedback",
    briefing=("It's windy. You have a limited compute budget: every re-plan uses one "
              "solve. Get through the gap."),
    concept=("MPC is feedback: it re-plans from the measured state, so it can correct disturbances "
             "its model does not know about (here, the wind). Between two re-plans the "
             "controller runs open-loop. Re-planning costs computation, so how often to re-plan "
             "is a trade-off between robustness and compute."),
    teaching=("The default re-plans every sample ($k = 1$): the most feedback, but the 60 solves "
              "run out after 6 s: budget exceeded. Re-plan less often and the wind pushes the "
              "ball off its plan between re-plans, towards the blocks. Find a $k$ that is cheap "
              "enough but still corrects the wind, and give the ball room with the margin $m$. The "
              "budget bar counts the solves; the solid part of the plan on the map is what runs "
              "open-loop."),
    hints=(
        "Between two re-plans, who corrects for the wind?",
        "Re-planning every step gives the most feedback, but it is too expensive. Watch the budget bar.",
        "Re-plan every second ($k = 10$) and give the wind a little room: a margin of about $m = 0.3$ m.",
    ),
    accent="sun",
    icon="wind",
    play_screen=build,
    intro=intro,
)
