"""Level 0: "Hello, MPC" (tutorial, no stars): a guided tour of the MPC loop.

Numbers (small open field, moving start, fixed weights and horizon) live in
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

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..gameplay.level_data import load_level_data
from ..gameplay.level_intro import LevelIntro
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.loop_diagram import LoopDiagram
from ..gameplay.ocp_card import OcpSpec
from ..ui.widgets import Button, label
from .base import LevelInfo


# --- the OCP, with the line of the current tour step highlighted -------------------------------
def ocp(d, n: int, focus: str | None = None) -> OcpSpec:
    """The OCP with horizon n. focus: the tour step whose OCP line is highlighted
    ("measure", "predict", "optimise") or None."""
    lk = d.locked

    def hl(line: str, key: str) -> str:
        return rf"\new{{{line}}}" if focus == key else line

    (x0, y0), (x1, y1) = d.workspace
    return OcpSpec(
        objective=[
            hl(rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
               rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2", "optimise"),
            hl(rf"\ell(x,u) = {lk['q_p']:g}\,\|p-p_{{\star}}\|^2 + {lk['q_v']:g}\,\|v\|^2 "
               rf"+ {lk['r']:g}\,\|u\|^2", "optimise"),
            rf"P = {d.raw.get('terminal_factor', 10):g}\,Q,\quad \mathrm{{horizon}}\ N = {n}",
        ],
        constraints=[
            hl(r"x_0 = \hat{x}", "measure"),
            hl(r"x_{k+1} = f(x_k,\,u_k)", "predict"),
            hl(rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}", "optimise"),
            rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
        ],
        notes=(f"Re-solved every Δt = {d.dt:g} s from the measured state x̂, N = {n} steps "
               f"({n * d.dt:g} s) ahead; only u₀ is applied."),
        legend=["x = (p, v): position, velocity · u = a: acceleration · p★: target"],
    )


# --- the tour ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TourStep:
    title: str
    text: str  # rich text (subscripts as <sub>)
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
                 f"An MPC controller drives this ball. Every Δt = {dt:g} s it runs the same loop: "
                 "measure, predict, optimise, apply. Let's walk through the first round.", "start"),
        TourStep("① Measure",
                 "First it measures the state x̂: where the ball is and how fast it moves. Right "
                 f"now p = ({x[0]:g}, {x[1]:g}) m and v = ({x[2]:g}, {x[3]:g}) m/s: the ball is "
                 "already moving.", "measure", ocp="measure"),
        TourStep("② Predict",
                 "Its model x<sub>k+1</sub> = f(x<sub>k</sub>, u<sub>k</sub>) says how the ball "
                 "moves (velocity changes position, acceleration changes velocity). With it, the "
                 "controller can predict where any sequence of accelerations would take the ball "
                 f"over the next N = {n} steps ({T:g} s). The faint lines are a few examples.",
                 "predict", ocp="predict"),
        TourStep("③ Optimise",
                 f"Of all input sequences that respect the limits (|a| ≤ {d.a_max:g} m/s², "
                 f"|v| ≤ {d.v_max:g} m/s), it picks the one with the lowest cost: being far from "
                 "the star, moving fast and accelerating all cost something. That best sequence is "
                 "the plan: the dashed line, its dots the predicted positions, ending "
                 f"{T:g} s ahead (x<sub>N</sub>).", "plan", ocp="optimise"),
        TourStep("④ Apply the first input",
                 f"Only the first input u<sub>0</sub> (the arrow) is sent to the motors, for "
                 f"{dt:g} s. The rest of the plan is not used.", "apply"),
        TourStep("⑤ Repeat",
                 f"Every {dt:g} s the loop starts again from the new measurement: a new plan, a new "
                 f"first input. Here we are {later * dt:g} s ({later} rounds) later (grey: the first "
                 "plan). The plan always reaches N steps ahead and moves with the ball: a receding "
                 "horizon. Re-planning from measurements is also what corrects for anything the "
                 "model gets wrong.", "repeat", solve=later, ocp="measure"),
        TourStep("Watch it run",
                 f"Press Play to watch the remaining {max(0, tr.n_solves - later - 1)} rounds. With "
                 "‹ k /n › under the map you can look at any single plan.", "repeat", solve=later),
    ]


GOAL = "Follow the tour through one round of the MPC loop, then watch the whole run."
REPEAT_SOLVE = 10  # step "Repeat" shows the solve 1 s (10 rounds) after the first one
UNSOLVED = ("start", "measure", "predict")  # tour steps before the OCP is solved: no solver numbers


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
        self.step_text = label("Computing the run...", "body", wrap=True)
        box.addWidget(self.step_count)
        box.addWidget(self.step_title)
        box.addWidget(self.step_text)
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
        self.done_text = label("", "body", wrap=True)
        done.addWidget(self.done_text)
        replay_row = QHBoxLayout()
        self.replay_tour_button = Button("Replay the tour", variant="link")
        replay_row.addWidget(self.replay_tour_button)
        replay_row.addStretch(1)
        done.addLayout(replay_row)
        layout.addWidget(self.done_box)

        self.back_button.clicked.connect(lambda: self._go(self._step - 1))
        self.next_button.clicked.connect(self._next)
        self.replay_tour_button.clicked.connect(self._replay_tour)
        self.result_panel.set_watch_text("Replay tour")
        self.result_panel.set_retry_visible(False)  # nothing to change in this level
        self.ctx.engine.status_changed.connect(lambda _s: self._try_start())
        # the Run/Reset buttons are built after this hook: switch modes once the widget is complete
        QTimer.singleShot(0, self, self._begin)

    def _begin(self) -> None:
        self.run_info.show_parts(solve=False, run=False)  # "–" until the story gets there
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
                f"Measure, predict, optimise, apply the first input, repeat: every {self.data.dt:g} s, "
                f"{n} times in this run. From Level 1 on you design this controller yourself: its "
                "cost, its horizon, its constraints.")

    # --- the run -------------------------------------------------------------------------------
    def _on_result(self, result) -> None:
        if self._touring:  # the solver tile follows the story (see _go)
            self.run_info.show_parts(solve=False, run=False)
        super()._on_result(result)  # loads the replay and starts playing
        if self._touring:
            self.playback.pause()
            self._steps = tour_steps(self.data, result)
            self._go(0)

    def _on_failed(self, reason: str) -> None:
        super()._on_failed(reason)
        if self._touring:
            self._started = False
            self.step_title.setText("The run failed")
            self.step_text.setText(f"{reason}. The tour tries again when the engine is ready.")

    def _on_replay_end(self) -> None:
        super()._on_replay_end()  # the result card (no stars)
        self.run_info.show_parts(solve=True, run=True)  # the whole run has been watched
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
        # solver tile: no solve before step "Optimise"; the whole run only once it is watched
        self.run_info.show_parts(solve=step.focus not in UNSOLVED, run=False)
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
        self.run_info.show_parts(solve=True, run=False)  # follows the replay; totals at the end
        self.step_title.setText("Watching the run")
        self.step_text.setText(f"Every {self.data.dt:g} s: measure, plan, apply the first input. "
                               "Watch the dashed plan move along with the ball.")
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
        self._steps = tour_steps(self.data, self.result)
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
            ("Horizon", f"N = {m['N']} ({m['horizon_s']:g} s)", ""),
            ("MPC solves", f"{m.get('solves', 0)}", f"one every {self.data.dt:g} s"),
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
    briefing=("Before you design controllers yourself, watch one at work: "
              "step by step, the way it thinks."),
    concept=("Model predictive control in one sentence: predict, optimise, apply the first move, "
             "repeat. At every step the controller measures the state, uses a model to predict "
             "where different input sequences would take the ball over the next N steps, picks "
             "the sequence with the lowest cost that respects the limits, applies only its first "
             "input, and starts again from the new measurement."),
    teaching=("A guided tour walks you through the first round of the loop on the map. The "
              "matching part of the OCP lights up at each step. Then you watch the whole run."),
    accent="rose",
    icon="loop",
    tutorial=True,
    play_screen=build,
    intro=intro,
)
