"""Level 0: "Hello, MPC" (tutorial, no stars): a guided tour of the MPC loop.

Numbers (small open field, start at rest, fixed weights and horizon) live in
game/level_data/hello_mpc.json, shared with the engine. The engine's rules are in
engine_server/level_rules/hello_mpc.py.

The play screen computes the run as soon as it opens, then the controls tile becomes a
tour panel: seven steps (TOUR) walk through the first round of the loop (measure,
predict, optimise, apply, repeat). In each step the map highlights what the text talks
about (MapView.set_tour) and the OCP highlights its matching line (\\new{...}). After the
tour the replay plays to the end; then "Tour complete" with a link to replay the tour.
The player changes nothing in this level (no knobs, no Run): it only introduces MPC
(decided 2026-11-18; the horizon is Level 2's topic).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..gameplay.level_data import load_level_data
from ..gameplay.level_intro import LevelIntro
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.analysis_panel import (Events, PlotSpec, RefLine, Series, Shade, distances,
                                       speeds, state_times)
from ..ui import theme
from ..gameplay.loop_diagram import LoopDiagram
from ..gameplay.ocp_card import STATE_LEGEND, OcpSpec
from ..ui.math_text import math_text
from ..ui.widgets import Button, label
from .base import LevelInfo


# --- the OCP, with the line of the current tour step highlighted -------------------------------
def ocp(d, n: int, focus: str | None = None) -> OcpSpec:
    """The OCP with horizon n, written as simply as possible for a first look (2026-11-18):
    weights of 1 are left out, and the terminal cost P = 10·Q is written as its number
    (Q = diag(q_p, q_p, q_v, q_v) = I here). focus: the tour step whose OCP line is
    highlighted ("measure", "predict", "optimise") or None."""
    lk = d.locked
    tf = d.raw.get("terminal_factor", 10)

    def hl(line: str, key: str) -> str:
        return rf"\new{{{line}}}" if focus == key else line

    def w(value: float) -> str:  # a weight in front of a term; 1 is left out
        return "" if value == 1 else rf"{value:g}\,"

    terminal = rf"\|x_{{{n}}}-x_{{\star}}\|"
    objective_extra = []
    if lk["q_p"] == lk["q_v"]:  # Q = q·I, so P = 10·q·I: write the number
        terminal = rf"{w(tf * lk['q_p'])}{terminal}^2"
    else:  # Q is not a multiple of I: keep P and say what it is
        terminal = rf"{terminal}_P^2"
        objective_extra = [rf"P = {tf:g}\,\mathrm{{diag}}({lk['q_p']:g},{lk['q_p']:g},"
                           rf"{lk['q_v']:g},{lk['q_v']:g})"]
    (x0, y0), (x1, y1) = d.workspace
    return OcpSpec(
        objective=[
            hl(rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
               rf"\ell(x_k,u_k) \;+\; {terminal}", "optimise"),
            hl(rf"\ell(x,u) = {w(lk['q_p'])}\|p-p_{{\star}}\|^2 + {w(lk['q_v'])}\|v\|^2 "
               rf"+ {w(lk['r'])}\|u\|^2", "optimise"),
            *objective_extra,
        ],
        constraints=[
            hl(r"x_0 = \hat{x}", "measure"),
            hl(r"x_{k+1} = f(x_k,\,u_k)", "predict"),
            hl(rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}", "optimise"),
            hl(rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}", "optimise"),
        ],
        notes=(rf"Re-solved every $\Delta t = {d.dt:g}\ \mathrm{{s}}$ from the measured state $\hat{{x}}$, "
               rf"$N = {n}$ steps ({n * d.dt:g} s) ahead; only $u_0$ is applied."),
        legend=STATE_LEGEND,
    )


# --- the tour ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TourStep:
    title: str
    text: str  # rich text; symbols as $...$ (LaTeX font, ui/math_text.py)
    focus: str  # what the map highlights (gameplay/map_view.py TOUR_FOCUS)
    solve: int = 0  # which MPC solve the map shows
    ocp: str | None = None  # which OCP line is highlighted ("measure", "predict", "optimise")


def tour_steps(d, result) -> list[TourStep]:
    """The seven steps, with the numbers of this run (its horizon N, its first state)."""
    tr = result.trajectory
    n = int(result.metrics.get("N", d.N))
    T, dt = n * d.dt, d.dt
    x = tr.x[0]
    later = min(REPEAT_SOLVE, tr.n_solves - 1)  # step "Repeat": this many rounds later
    return [
        TourStep("You are not steering",
                 "An MPC controller drives this ball. "
                 rf"Every $\Delta t = {dt:g}\ \mathrm{{s}}$ it runs the same loop: measure, predict, optimise, "
                 "apply. Let's walk through the first round.", "start"),
        TourStep("① Measure",
                 r"First it measures the state $\hat{x}$: where the ball is located and how fast it moves."
                 "<br><br><b>Current state:</b>"
                 f"<br>$p = ({x[0]:g},\\, {x[1]:g})\\ \\mathrm{{m}}$"
                 f"<br>$v = ({x[2]:g},\\, {x[3]:g})\\ \\mathrm{{m/s}}$", "measure", ocp="measure"),
        TourStep("② Predict",
                 r"The model $x_{k+1} = f(x_k,\, u_k)$ defines the ball's motion. With it, the "
                 "controller can predict where any sequence of accelerations would take the ball "
                 f"over the next $N = {n}$ steps ({T:g} s). The faint lines are a few examples.",
                 "predict", ocp="predict"),
        TourStep("③ Optimise",
                 "Now it picks the best input sequence: the one with the lowest cost that "
                 "respects the limits."
                 "<br><br><b>Cost:</b> being far from the star, moving fast, accelerating"
                 # one bullet per limit (2026-11-22); the units inside the formula, so they are in
                 # the LaTeX font, on the formula's baseline, and never wrap away from it
                 "<br><b>Limits:</b>"
                 rf"<br>•&nbsp;$|a_x|,\ |a_y| \leq {d.a_max:g}\ \mathrm{{m/s^2}}$"
                 rf"<br>•&nbsp;$|v_x|,\ |v_y| \leq {d.v_max:g}\ \mathrm{{m/s}}$"
                 rf"<br>•&nbsp;${field_limits(d)}$"
                 "<br><b>Result:</b> the plan represented by the dashed line on the map, ending "
                 f"{T:g} s ahead ($x_N$)", "plan", ocp="optimise"),
        TourStep("④ Apply the first input",
                 "Only the first input $u_0$ is sent to the motors, for "
                 f"{dt:g} s. The rest of the plan is not applied.", "apply"),
        TourStep("⑤ Repeat",
                 rf"Every $\Delta t = {dt:g}\ \mathrm{{s}}$ the whole loop runs again from the new measurement: "
                 "a new plan, a new first input."
                 f"<br><br><b>On the map:</b> {later * dt:g} s ({later} rounds) later."
                 "<br>•&nbsp;Grey: the first plan"
                 "<br>•&nbsp;Coral: the current plan."
                 f"<br><b>Receding horizon:</b> the plan always reaches $N = {n}$ steps ahead, so it "
                 "moves with the ball."
                 "<br><b>Why it matters:</b> re-planning from each new measurement lets the controller "
                 "react to what its model got wrong.", "repeat", solve=later, ocp="measure"),
        TourStep("Watch it run",
                 f"Press Play to watch the remaining {max(0, tr.n_solves - later - 1)}"
                 " rounds.", "repeat", solve=later),
    ]


GOAL = "Follow the tour through one round of the MPC loop, then watch the whole run."
WATCHING = (r"Every $\Delta t = {dt:g}\ \mathrm{{s}}$: measure, plan, apply the first input. "
            "Watch the dashed plan move along with the ball.")  # while the rest of the run plays
REPEAT_SOLVE = 10  # step "Repeat" shows the solve 1 s (10 rounds) after the first one


def field_limits(d) -> str:
    """The position limits (the field) as TeX, with the unit: one range when x and y share it."""
    (x0, y0), (x1, y1) = d.workspace
    if (x0, x1) == (y0, y1):
        return rf"{x0:g} \leq p_x,\ p_y \leq {x1:g}\ \mathrm{{m}}"
    return rf"{x0:g} \leq p_x \leq {x1:g}\ \mathrm{{m}},\quad {y0:g} \leq p_y \leq {y1:g}\ \mathrm{{m}}"
TOUR_ANALYSIS = "The plots are available after the tour's replay"  # Analysis tab during the tour


def example_predictions(d, n: int, x0) -> list[list[tuple[float, float]]]:
    """A few predictions from the measured state x0 with constant accelerations, through the
    same double-integrator model the MPC uses (velocity clipped to v_max): the tour's fan."""
    a, paths = d.a_max, []
    for ax, ay in ((a, 0.0), (0.75 * a, 0.75 * a), (0.75 * a, -0.75 * a), (0.0, a), (0.0, -a)):
        px, py, vx, vy = x0
        path = [(px, py)]
        for _ in range(n):
            px, py = px + d.dt * vx + 0.5 * d.dt**2 * ax, py + d.dt * vy + 0.5 * d.dt**2 * ay
            vx = max(-d.v_max, min(d.v_max, vx + d.dt * ax))
            vy = max(-d.v_max, min(d.v_max, vy + d.dt * ay))
            path.append((px, py))
        paths.append(path)
    return paths


class HelloMpcWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        return GOAL

    def controls_title(self) -> str:
        return "Guided tour"

    # --- controls: the tour panel, then "Tour complete" (nothing to tune here) --------------
    def add_controls(self, layout: QVBoxLayout) -> None:
        self._eyebrow = layout.itemAt(0).widget()  # the controls title (base class)
        self._steps: list[TourStep] = []
        self._step = 0
        self._touring = True
        self._started = False
        self._ocp_focus: str | None = None

        self.tour_box = QWidget()
        box = QVBoxLayout(self.tour_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        self.step_count = label("", "caption")
        self.step_title = label("", "subheading", wrap=True)
        self.step_text = math_text("Computing the run...", "body")
        box.addWidget(self.step_count)
        # title + text in an area as tall as the longest step, so Back / Next stay in place
        # when the text gets shorter or longer (decided 2026-11-19)
        self.step_area = QWidget()
        area = self._area_layout = QVBoxLayout(self.step_area)
        area.setContentsMargins(0, 0, 0, 0)
        area.setSpacing(6)
        area.addWidget(self.step_title)
        area.addWidget(self.step_text)
        area.addStretch(1)
        self.step_area.installEventFilter(self)
        self._measure_title = label("", "subheading", wrap=True)  # never shown: measures texts
        self._measure_text = math_text("", "body")
        self._area_width = -1
        box.addWidget(self.step_area)
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 0)
        row.setSpacing(10)
        self.back_button = Button("‹  Back", scale="tall")
        self.next_button = Button("Next  ›", variant="primary", scale="large")
        row.addWidget(self.back_button)
        row.addWidget(self.next_button, 1)
        box.addLayout(row)
        layout.addWidget(self.tour_box)

        self.done_box = QWidget()
        done = QVBoxLayout(self.done_box)
        done.setContentsMargins(0, 0, 0, 0)
        done.setSpacing(6)
        done.addWidget(label("That's MPC", "subheading"))
        self.done_text = math_text("", "body")
        done.addWidget(self.done_text)
        # like the tour's Back / Next: a tonal button on the left, the main action on the right
        replay_row = QHBoxLayout()
        replay_row.setContentsMargins(0, 8, 0, 0)
        replay_row.setSpacing(6)  # both buttons fit the 330 px controls tile at the type scale
        self.replay_tour_button = Button("Replay tour", scale="tall")
        self.replay_tour_button.setToolTip("Walk through the MPC loop again")
        self.next_level_button = Button("Next level  ›", variant="primary", scale="large")
        nxt = self.ctx.next_level(self.level)
        if nxt is not None:
            self.next_level_button.setToolTip(f"Level {nxt.number}: {nxt.title}")
        self.next_level_button.setVisible(nxt is not None)
        replay_row.addWidget(self.replay_tour_button)
        replay_row.addWidget(self.next_level_button, 1)
        done.addLayout(replay_row)
        layout.addWidget(self.done_box)

        self.back_button.clicked.connect(lambda: self._go(self._step - 1))
        self.next_button.clicked.connect(self._next)
        self.replay_tour_button.clicked.connect(self._replay_tour)
        self.next_level_button.clicked.connect(self._go_next)  # Level 1's intro
        self.result_panel.set_watch_text("Replay tour")
        self.result_panel.set_retry_visible(False)  # nothing to change in this level
        self.ctx.engine.status_changed.connect(lambda _s: self._try_start())
        # the Run/Reset buttons are built after this hook: switch modes once the widget is complete
        QTimer.singleShot(0, self, self._begin)

    # --- a steady panel: the text area is as tall as the longest step -----------------------------
    def eventFilter(self, obj, event) -> bool:
        if obj is self.step_area and event.type() == QEvent.Type.Resize:
            if event.size().width() != self._area_width:  # re-measure only when the width changes
                self._area_width = event.size().width()
                self._fix_step_height()
        return super().eventFilter(obj, event)

    def _fix_step_height(self) -> None:
        """Make the title + text area as tall as the tallest of all tour texts at this width,
        so the Back / Next buttons under it never move while stepping through the tour."""
        w = self.step_area.width()
        if w <= 0:
            return
        texts = [(s.title, s.text) for s in self._steps]
        texts += [("Getting ready", "The MPC is computing the run..."),
                  ("Watching the run", WATCHING.format(dt=self.data.dt))]
        self._measure_title.ensurePolished()
        spacing = self._area_layout.spacing()
        tallest = 0
        for title, text in texts:
            self._measure_title.setText(title)
            self._measure_text.setText(text)
            tallest = max(tallest, self._measure_title.heightForWidth(w) + spacing
                          + self._measure_text.heightForWidth(w))
        self.step_area.setMinimumHeight(tallest)

    def _begin(self) -> None:
        self.run_info.set_hidden(True)  # "–" until the run has been watched
        self._set_mode(tour=True)
        self.back_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self._try_start()

    def _try_start(self) -> None:
        """Compute the run as soon as the engine can (the tour needs it)."""
        if self._started or not self._touring:
            return
        if not self.ctx.engine.status.can_run:
            self.step_title.setText("Waiting for the MPC engine")
            self.step_text.setText(f"{self.ctx.engine.status.message}. Start it with "
                                   "engine_server/start_engine (see game/README.md); the tour "
                                   "starts by itself.")
            return
        self._started = True
        self.step_title.setText("Getting ready")
        self.step_text.setText("The MPC is computing the run...")
        self.start_run()

    def _set_mode(self, tour: bool) -> None:
        """Tour panel during the tour; "Tour complete" after it. No knobs, Reset or Run in
        this level: the player only watches (the tour text says what is going on)."""
        self._touring = tour
        self.tour_box.setVisible(tour)
        self.done_box.setVisible(not tour)
        for widget in (self.knobs, self.run_button, self.reset_button, self.status):
            widget.setVisible(False)
        self._eyebrow.setText("Guided tour" if tour else "Tour complete")
        if not tour and self.result is not None:
            n = self.result.trajectory.n_solves
            self.done_text.setText(
                rf"Measure, predict, optimise, apply the first input, repeat: every $\Delta t = {self.data.dt:g}\ \mathrm{{s}}$, "
                f"{n} times in this run.<br><br>"  # two paragraphs (rich text ignores \n)
                f"From Level 1 on you design this controller yourself: its "
                "cost, its horizon, its constraints.")

    # --- the run -------------------------------------------------------------------------------
    def _on_result(self, result) -> None:
        if self._touring:  # whole-run numbers only once the run has been watched
            self.run_info.set_hidden(True)
        super()._on_result(result)  # loads the replay and starts playing
        if self._touring:
            self.set_analysis_available(False, TOUR_ANALYSIS)
            self._autoplay_pending = False  # the tour starts paused, also if it arrived hidden
            self.playback.pause()
            self._steps = tour_steps(self.data, result)
            self._fix_step_height()
            self._go(0)

    # --- the Analysis tab (2026-11-20): only after the tour's replay, like the solver numbers --
    def analysis_plots(self, result):
        tr, d = result.trajectory, self.data
        t = state_times(tr)
        tol = d.raw["tolerance"]
        return [
            PlotSpec(
                title="Speed",
                description=(r"The controller accelerates, drives and brakes so that the ball arrives "
                             rf"at rest. The limits act per axis ($|v_x|,\ |v_y| \leq {d.v_max:g}\ \mathrm{{m/s}}$), "
                             rf"so $\|v\|$ can be a little higher than {d.v_max:g} m/s."),
                y_label=r"speed $\|v\|$ [m/s]", t_end=tr.duration,
                series=(Series(t, speeds(tr), color=theme.PLOT_1),)),
            PlotSpec(
                title="Distance to the target",
                description=("It falls as the ball approaches the star. The run succeeds when the ball "
                             rf"is within {tol['position']:g} m of it and slower than "
                             rf"{tol['speed']:g} m/s."),
                y_label=r"distance $\|p - p_{\star}\|$ [m]", t_end=tr.duration,
                series=(Series(t, distances(tr, d.target), color=theme.PLOT_1),)),
        ]

    def debrief_visual(self, result):
        """The MPC loop diagram of the intro (Research debrief)."""
        return LoopDiagram(self.data.dt)

    def _on_failed(self, reason: str) -> None:
        super()._on_failed(reason)
        if self._touring:
            self._started = False
            self.step_title.setText("The run failed")
            self.step_text.setText(f"{reason}. The tour tries again when the engine is ready.")

    def _on_replay_end(self) -> None:
        super()._on_replay_end()  # the result card (no stars)
        self.run_info.set_hidden(False)  # the whole run has been watched
        self.set_analysis_available(True)
        if self._touring and self._step == len(self._steps) - 1:
            self._end_tour()

    # --- tour steps ------------------------------------------------------------------------------
    def _go(self, i: int) -> None:
        if not self._steps:
            return
        i = max(0, min(i, len(self._steps) - 1))
        self._step, step = i, self._steps[i]
        tr = self.result.trajectory
        self.result_panel.hide()
        self.playback.pause()
        self.playback.seek(tr.time_of_solve(min(step.solve, tr.n_solves - 1)))
        n = int(self.result.metrics.get("N", self.data.N))
        fan = example_predictions(self.data, n, tr.x[0]) if step.focus == "predict" else None
        self.map.set_tour(step.focus, fan, earlier=0)  # step "repeat": the first plan in grey
        self._ocp_focus = step.ocp
        self.refresh_ocp()
        self.run_info.set_hidden(True)  # whole-run numbers only after the replay
        self.step_count.setText(f"Step {i + 1} of {len(self._steps)}")
        self.step_title.setText(step.title)
        self.step_text.setText(step.text)
        self.back_button.setEnabled(i > 0)
        self.next_button.setEnabled(True)
        last = i == len(self._steps) - 1
        self.next_button.setText("Play  ▶" if last else "Next  ›")

    def _next(self) -> None:
        if self._step < len(self._steps) - 1:
            self._go(self._step + 1)
            return
        # last step: watch the rest of the run with the normal map
        self.map.set_tour(None)
        self._ocp_focus = None
        self.refresh_ocp()
        self.next_button.setEnabled(False)
        self.step_title.setText("Watching the run")
        self.step_text.setText(WATCHING.format(dt=self.data.dt))
        self.playback.play()

    def _end_tour(self) -> None:
        self.map.set_tour(None)
        self._ocp_focus = None
        self.refresh_ocp()
        self._set_mode(tour=False)

    def _replay_tour(self) -> None:
        if self.result is None:
            return
        self._set_mode(tour=True)
        self.set_analysis_available(False, TOUR_ANALYSIS)
        self._steps = tour_steps(self.data, self.result)
        self._fix_step_height()
        self._go(0)

    def _watch_again(self) -> None:  # the result card's "Replay tour"
        self._replay_tour()

    # --- the OCP: the run's horizon, the tour step's line highlighted ----------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        n = int(self.result.metrics.get("N", d.N)) if self.result is not None else d.N
        return ocp(d, n, getattr(self, "_ocp_focus", None))

    def result_rows(self, result):
        m = result.metrics
        return [
            ("Time", f"{m['time']:.1f} s", ""),
            ("Horizon", f"$N = {m['N']}$ ({m['horizon_s']:g} s)", ""),
            ("MPC solves", f"{m.get('solves', 0)}",""),
        ]


def build(ctx, level: LevelInfo) -> HelloMpcWidget:
    return HelloMpcWidget(ctx, level, load_level_data(level.id))


def intro(d) -> LevelIntro:
    """The level intro: no stars, the plain OCP, the loop diagram, nothing to control."""
    return LevelIntro(
        goal=GOAL,
        ocp=ocp(d, d.N),
        ocp_title="The OCP your MPC solves",
        illustration=lambda: LoopDiagram(d.dt),
    )


LEVEL = LevelInfo(
    number=0,
    id="hello_mpc",
    title="Hello, MPC",
    topic="The MPC loop",
    briefing=("Before you design controllers yourself, watch one at work."),
    concept=("Model predictive control in one sentence: predict, optimise, apply the first control, "
             "repeat. At every step the controller measures the state, uses a model to predict "
             "where different input sequences would take the ball over the next $N$ steps, picks "
             "the sequence with the lowest cost that respects the limits, applies only its first "
             "input, and starts again from the new measurement."),
    teaching=("A guided tour walks you through the first round of the loop on the map. The "
              "corresponding part of the OCP lights up at each step. Then you watch the whole run."),
    accent="rose",
    icon="loop",
    tutorial=True,
    play_screen=build,
    intro=intro,
)
