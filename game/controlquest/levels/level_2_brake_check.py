"""Level 2: "Brake Check" (PRD 7, Level 2): horizon length, recursive feasibility,
terminal constraint.

Numbers (map, limits, locked weights, the N choices, the terminal-stop toggle, pars)
live in game/level_data/brake_check.json, shared with the engine. The engine's rules
are in engine_server/level_rules/brake_check.py.

The ball is fast but brakes weakly, and the target is just in front of the wall. The
player picks the horizon N (dropdown, precompiled solvers) and can switch on the
terminal stop v_N = 0. Under the map, the brake check compares the room left to the
wall with the braking distance and with how far the plan looks ahead.
"""

import math

from PySide6.QtWidgets import QVBoxLayout

from ..gameplay.brake_gauge import BrakeGauge
from ..gameplay.level_data import load_level_data
from ..gameplay.level_intro import LevelIntro
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.ocp_card import OcpSpec
from .base import LevelInfo


def _wall_ahead(p, v, lo, hi) -> float:
    """Distance to the field's wall in the direction of motion (inf at rest); same as the engine."""
    speed = math.hypot(v[0], v[1])
    if speed < 1e-6:
        return math.inf
    d = (v[0] / speed, v[1] / speed)
    dists = [((hi[i] if d[i] > 0 else lo[i]) - p[i]) / d[i] for i in range(2) if abs(d[i]) > 1e-9]
    return max(0.0, min(dists))


class BrakeCheckWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d, pars = self.data, self.data.pars
        brake_s, brake_m = d.v_max / d.a_max, d.v_max**2 / (2 * d.a_max)
        return (f"Stop on the star, {d.workspace[1][0] - d.target[0]:g} m in front of the wall, within "
                f"{d.t_limit:g} s. The ball is fast ({d.v_max:g} m/s) but brakes weakly "
                f"({d.a_max:g} m/s²): stopping from full speed takes {brake_s:g} s and {brake_m:g} m. "
                f"★★: within {pars['time']:g} s; ★★★: also with a short horizon, N ≤ {pars['max_N']:g} "
                "(cheaper solves).")

    def controls_title(self) -> str:
        return "Tune the controller"

    def add_controls(self, layout: QVBoxLayout) -> None:
        self.knobs.changed.connect(self.refresh_ocp)

    # --- under the map: the brake check ---------------------------------------------------
    def add_extras(self, column: QVBoxLayout) -> None:
        self.gauge = BrakeGauge(scale_m=20.0)
        self.gauge.setToolTip("Red means the point of no return: from this speed the ball can no "
                              "longer stop before the wall.")
        column.addWidget(self.gauge)

    def update_extras(self, t: float) -> None:
        tr, d = self.result.trajectory, self.data
        k, a = tr.index_at(t)
        xa, xb = tr.x[k], tr.x[min(k + 1, len(tr.x) - 1)]
        x = [xa[i] + a * (xb[i] - xa[i]) for i in range(4)]
        speed = math.hypot(x[2], x[3])
        (lo, hi) = d.workspace
        n_run = int(self.result.metrics.get("N", d.N))
        self.gauge.set_values(_wall_ahead(x[:2], x[2:], lo, hi), speed**2 / (2 * d.a_max),
                              n_run * d.dt * speed)

    # --- the OCP with the chosen N and terminal stop ------------------------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        knobs = self.knobs.values() if hasattr(self, "knobs") else {k.name: k.default for k in d.knobs}
        return ocp(d, int(knobs["N"]), knobs["stop"] >= 0.5)

    def result_rows(self, result):
        m, d = result.metrics, self.data
        pars = d.pars
        return [
            ("Time", f"{m['time']:.1f} s", f"limit {d.t_limit:g} s · ★★ ≤ {pars['time']:g} s"),
            ("Horizon", f"N = {m['N']} ({m['horizon_s']:g} s)", f"★★★ N ≤ {pars['max_N']:g}"),
            ("Terminal stop", "on" if m.get("terminal_stop") else "off", ""),
            ("Overshoot", f"{m['overshoot']:.2f} m", "past the star, towards the wall"),
        ]


def ocp(d, n: int, stop: bool, intro: bool = False) -> OcpSpec:
    """The OCP with horizon n and the terminal stop on/off. intro=True: the level intro's
    version (the horizon and the terminal stop marked as new, the stop shown as optional)."""
    lk = d.locked
    knob = r"\newknob" if intro else r"\knob"
    (x0, y0), (x1, y1) = d.workspace
    constraints = [
        r"x_0 = \hat{x}",
        r"x_{k+1} = f(x_k,\,u_k)",
        rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
        rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
    ]
    if stop or intro:
        what = r"terminal\ stop,\ optional" if intro else r"terminal\ stop"
        constraints.append(rf"{knob}{{stop}}{{v_{{{n}}} = 0}}\quad \mathrm{{({what})}}")
    return OcpSpec(
        objective=[
            rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
            rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2",
            rf"\ell(x,u) = {lk['q_p']:g}\,\|p-p_{{\star}}\|^2 + {lk['q_v']:g}\,\|v\|^2 "
            rf"+ {lk['r']:g}\,\|u\|^2",
            rf"P = {d.raw.get('terminal_factor', 10):g}\,Q,\quad \mathrm{{horizon}}\ {knob}{{N}}{{N = {n}}}",
        ],
        constraints=constraints,
        notes=(f"Re-solved every Δt = {d.dt:g} s, N = {n} steps ({n * d.dt:g} s) ahead"
               + ("; every plan must end at rest." if stop else ".")),
        legend=["x = (p, v): position, velocity · u = a: acceleration · p★: target"],
    )


def build(ctx, level: LevelInfo) -> BrakeCheckWidget:
    return BrakeCheckWidget(ctx, level, load_level_data(level.id))


def intro(d) -> LevelIntro:
    """The level intro's numbers and math."""
    lk, n = d.locked, int(next(k.default for k in d.knobs if k.name == "N"))
    return LevelIntro(
        goal=(f"Stop on the star, {d.workspace[1][0] - d.target[0]:g} m in front of the wall, "
              f"within {d.t_limit:g} s."),
        stars=("stop on the star", f"within {d.pars['time']:g} s",
               f"also N ≤ {d.pars['max_N']:g}"),
        ocp=ocp(d, n, False, intro=True),
        fixed=(f"q_p = {lk['q_p']:g}, q_v = {lk['q_v']:g}, r = {lk['r']:g}, "
               f"P = {d.raw.get('terminal_factor', 10):g}·Q"),
    )


LEVEL = LevelInfo(
    number=2,
    id="brake_check",
    title="Brake Check",
    topic="Horizon & feasibility",
    briefing=("New, faster ball, weaker brakes. The target is right in front of the "
              "wall. Stop on it."),
    concept=("The horizon has to see far enough. An MPC that plans N steps ahead notices the "
             "wall only once the wall is inside its horizon. If braking takes longer than that, "
             "it notices too late and no feasible plan is left: recursive feasibility is lost. "
             "A terminal constraint (every plan must end at rest) guarantees that a way to stop "
             "always exists, at the price of a more cautious controller."),
    teaching=("With the default N = 10 (1 s, about 4 m at full speed) the ball rushes at the "
              "wall. Braking from 4 m/s needs 8 m, so the OCP eventually has no solution: "
              "controller failure. Two ideas: a longer horizon (fast and safe, but bigger "
              "solves), or a short horizon plus the terminal stop (always safe, but slower). The "
              "brake check under the map compares the distance to the wall, the braking "
              "distance, and how far the plan looks."),
    hints=(
        "Watch the brake check under the map: when does \"braking needs\" become longer than "
        "\"wall ahead\"? How far does the plan look at that moment?",
        "A longer horizon sees the wall in time. Or force every plan to end at rest (terminal "
        "stop): then a way to stop always exists, but the ball may only go as fast as it can "
        "stop within the horizon.",
        "For three stars: N = 20 with the terminal stop on.",
    ),
    accent="sky",
    icon="wall",
    play_screen=build,
    intro=intro,
)
