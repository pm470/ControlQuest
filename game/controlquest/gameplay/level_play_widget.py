"""The playable level (PRD 5.2): map + playback on the left, goal / knobs / Run /
level extras / hints on the right, result card over the map at the end.

Flow of one run:
    Run -> RunRequest(level id, knobs) -> engine (Docker) -> RunResult
        -> map + playback replay it -> at the end: result card, stars saved

A level subclasses LevelPlayWidget and overrides the hooks at the bottom:
goal_text(), ocp_spec(), add_extras(column), update_extras(t), result_rows(result),
and for levels with other controls than weights (e.g. waypoints): controls_title(),
add_controls(layout), waypoints(), reset_controls(), set_controls_enabled(enabled);
they call controls_changed() when the player edits something.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..core.context import AppContext
from ..core.navigation import ScreenId
from ..engine.protocol import EngineStatus, RunRequest, RunResult
from ..levels.base import LevelInfo
from ..ui.widgets import Button, Card, label, scrollable
from .knob_panel import KnobPanel
from .level_data import LevelData
from .map_view import MapView
from .ocp_card import OcpCard, OcpSpec
from .playback import Playback, PlaybackBar
from .result_panel import ResultPanel
from .run_info_card import RunInfoCard
from .solve_selector import SolveSelector

SIDE_WIDTH = 330
MIDDLE_WIDTH = 350
WIDE_MIN_WIDTH = 1150  # below this the OCP column moves into the right column


class LevelPlayWidget(QWidget):
    navigate = Signal(str, object)  # forwarded by LevelScreen, like BaseScreen.navigate

    def __init__(self, ctx: AppContext, level: LevelInfo, data: LevelData,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx, self.level, self.data = ctx, level, data
        self.result: RunResult | None = None
        self._ticket = None
        self._hints_shown = 0
        self.playback = Playback(self)

        # --- left: map with the result card on top, playback below ---
        self.map = MapView()
        self.map.set_level(data)
        self.result_panel = ResultPanel()
        self.result_panel.hide()
        map_area = QWidget()
        stack = QGridLayout(map_area)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addWidget(self.map, 0, 0)
        stack.addWidget(self.result_panel, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.bar = PlaybackBar(self.playback)
        self.solve_selector = SolveSelector()
        self.solve_selector.setToolTip("Step through the MPC solves of this run: the map shows "
                                       "the plan computed in the selected solve")
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(map_area, 1)
        self.add_extras(left)  # level extras (e.g. battery) under the map, near the replay
        left.addWidget(self.bar)
        left.addWidget(self.solve_selector)

        # --- middle: the OCP and the solver info ---
        # Wide window: own column next to the map. Narrow window: moved into the
        # right column below the knobs (see resizeEvent).
        self._middle = QWidget()
        mid = QVBoxLayout(self._middle)
        mid.setContentsMargins(4, 4, 8, 8)
        mid.setSpacing(12)
        mid.addWidget(OcpCard(self.ocp_spec()))
        self.run_info = RunInfoCard()
        mid.addWidget(self.run_info)
        mid.addStretch(1)
        self._middle_scroll = scrollable(self._middle)
        self._middle_scroll.setFixedWidth(MIDDLE_WIDTH)
        self._wide = True

        # --- right: goal, knobs + run, hints ---
        side = QWidget()
        col = QVBoxLayout(side)
        col.setContentsMargins(4, 4, 8, 8)
        col.setSpacing(12)
        self._side_col = col

        goal = Card(padding=18, spacing=6, shadow=False)
        goal.body.addWidget(label("Goal", "subheading"))
        goal.body.addWidget(label(self.goal_text(), "body", wrap=True))
        col.addWidget(goal)

        knobs_card = Card(padding=18, spacing=10, shadow=False)
        knobs_card.body.addWidget(label(self.controls_title(), "subheading"))
        self.knobs = KnobPanel(data.knobs)
        knobs_card.body.addWidget(self.knobs)
        self.knobs.setVisible(bool(data.knobs))
        self.add_controls(knobs_card.body)
        buttons = QHBoxLayout()
        self.reset_button = Button("Reset", variant="ghost")
        self.reset_button.setToolTip("Back to the level's default settings")
        self.run_button = Button("Run  ▶", variant="primary")
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.run_button)
        knobs_card.body.addLayout(buttons)
        self.status = label("", "caption", wrap=True)
        knobs_card.body.addWidget(self.status)
        col.addWidget(knobs_card)
        self._middle_slot = col.count()  # where the middle column goes when narrow

        if level.hints:
            hints = Card(padding=18, spacing=8, shadow=False)
            row = QHBoxLayout()
            row.addWidget(label("Stuck?", "subheading"), 1)
            self.hint_button = Button(f"Hint 1/{len(level.hints)}", variant="ghost")
            row.addWidget(self.hint_button)
            hints.body.addLayout(row)
            self.hint_box = QVBoxLayout()
            hints.body.addLayout(self.hint_box)
            col.addWidget(hints)
            self.hint_button.clicked.connect(self._show_hint)
        col.addStretch(1)

        side_scroll = scrollable(side)
        side_scroll.setFixedWidth(SIDE_WIDTH)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addLayout(left, 1)
        root.addWidget(self._middle_scroll)
        root.addWidget(side_scroll)

        # --- wiring ---
        self.run_button.clicked.connect(self.start_run)
        self.reset_button.clicked.connect(self.reset_controls)
        self.knobs.changed.connect(self._on_knobs_changed)
        self.playback.time_changed.connect(self._on_time)
        self.playback.finished.connect(self._on_replay_end)
        self.solve_selector.solve_selected.connect(self._show_solve)
        self.result_panel.watch_again.connect(self._watch_again)
        self.result_panel.try_again.connect(self.result_panel.hide)
        self.result_panel.next_level.connect(self._go_next)
        ctx.engine.status_changed.connect(self._on_engine_status)
        self._on_engine_status(ctx.engine.status)

    # --- responsive layout ---------------------------------------------------------------
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        wide = self.width() >= WIDE_MIN_WIDTH
        if wide == self._wide:
            return
        self._wide = wide
        if wide:
            self._side_col.removeWidget(self._middle)
            self._middle_scroll.setWidget(self._middle)
            self._middle_scroll.show()
        else:
            self._middle_scroll.takeWidget()
            self._middle_scroll.hide()
            self._side_col.insertWidget(self._middle_slot, self._middle)
            self._middle.show()

    # --- running ------------------------------------------------------------------------
    def start_run(self) -> None:
        if not self.ctx.engine.status.can_run:
            self.status.setText(f"Can't run: {self.ctx.engine.status.message}. Start the engine "
                                "with engine_server/start_engine (see game/README.md).")
            return
        self.playback.pause()
        self.result_panel.hide()
        self._set_busy(True)
        self.status.setText("The MPC is computing your run...")
        self._ticket = self.ctx.engine.request_run(
            RunRequest(self.level.id, self.knobs.values(), self.waypoints()), parent=self)
        self._ticket.finished.connect(self._on_result)
        self._ticket.failed.connect(self._on_failed)

    def _on_result(self, result: RunResult) -> None:
        self._set_busy(False)
        self.result = result
        m = result.metrics
        self.status.setText(f"Replaying: {result.trajectory.duration:.1f} s of motion, "
                            f"{len(result.trajectory.u)} MPC solves "
                            f"(~{m.get('mean_solve_ms', 0):.2f} ms each).")
        self.map.set_trajectory(result.trajectory)
        self.solve_selector.set_count(result.trajectory.n_solves, result.trajectory.dt)
        self.run_info.set_result(result)
        self.playback.load(result.trajectory.duration)
        self.bar.set_enabled_for_run(True)
        self.playback.play()

    def _on_failed(self, reason: str) -> None:
        self._set_busy(False)
        self.status.setText(f"Run failed: {reason}")

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.run_button.setText("Computing..." if busy else "Run  ▶")
        self.knobs.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)
        self.set_controls_enabled(not busy)

    # --- replay ---------------------------------------------------------------------------
    def _on_time(self, t: float) -> None:
        self.map.set_time(t)
        if self.result is not None:
            k = self.result.trajectory.solve_at(t)
            self.solve_selector.set_current(k)
            self.run_info.set_solve(k)
            self.update_extras(t)

    def _show_solve(self, k: int) -> None:
        """The player picked MPC solve k: pause there so the map shows its plan."""
        if self.result is None:
            return
        self.result_panel.hide()
        self.playback.pause()
        self.playback.seek(self.result.trajectory.time_of_solve(k))

    def _on_replay_end(self) -> None:
        r = self.result
        if r is None:
            return
        if r.stars > 0:
            self.ctx.state.record_result(self.level.id, r.stars)
        nxt = self.ctx.next_level(self.level)
        can_next = nxt is not None and self.ctx.state.is_unlocked(nxt, self.ctx.levels)
        self.result_panel.show_result(r, self.result_rows(r), can_next)

    def _watch_again(self) -> None:
        self.result_panel.hide()
        self.playback.replay()

    def controls_changed(self) -> None:
        """Call when the player changed a control (hides the old result)."""
        self._on_knobs_changed()

    def _on_knobs_changed(self) -> None:
        self.result_panel.hide()
        if self.result is not None:
            self.status.setText("Settings changed: press Run to try them.")

    def _go_next(self) -> None:
        nxt = self.ctx.next_level(self.level)
        if nxt is not None:
            self.navigate.emit(ScreenId.LEVEL.value, nxt)

    def _show_hint(self) -> None:
        hints = self.level.hints
        if self._hints_shown < len(hints):
            self.hint_box.addWidget(label(f"{self._hints_shown + 1}. {hints[self._hints_shown]}",
                                          "body", wrap=True))
            self._hints_shown += 1
        done = self._hints_shown >= len(hints)
        self.hint_button.setEnabled(not done)
        self.hint_button.setText("No more hints" if done else
                                 f"Hint {self._hints_shown + 1}/{len(hints)}")

    def _on_engine_status(self, status: EngineStatus) -> None:
        self.run_button.setToolTip("Simulate this controller" if status.can_run
                                   else f"{status.message}: start the MPC engine first")
        if status.state == "outdated":
            self.status.setText(status.message + " (Ctrl+C in its terminal, then start_engine).")

    # --- hooks for levels ----------------------------------------------------------------
    def goal_text(self) -> str:
        return f"Bring the ball to the star and stop there within {self.data.t_limit:g} s."

    def ocp_spec(self) -> OcpSpec:
        """The OCP shown in the side panel. Default: the standard point-mass OCP with
        weights q_p, q_v, r, built from the level file's numbers."""
        d = self.data
        n = d.N
        (x0, y0), (x1, y1) = d.workspace
        return OcpSpec(
            objective=[
                rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
                rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2",
                r"\ell(x,u) = q_p\,\|p-p_{\star}\|^2 + q_v\,\|v\|^2 + r\,\|u\|^2",
                rf"Q = \mathrm{{diag}}(q_p,q_p,q_v,q_v),\quad P = {d.raw.get('terminal_factor', 10):g}\,Q",
            ],
            constraints=[
                r"x_0 = \hat{x}",
                r"x_{k+1} = f(x_k,\,u_k)",
                rf"|a_x|,\ |a_y| \leq {d.a_max:g}",
                rf"|v_x|,\ |v_y| \leq {d.v_max:g}",
                rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
            ],
            notes=(f"Re-solved every Δt = {d.dt:g} s from the measured state x̂, "
                   f"{n} steps ({n * d.dt:g} s) ahead; only u₀ is applied."),
            legend=["x = (p, v): position, velocity · u = a: acceleration · p★: target"],
        )

    def controls_title(self) -> str:
        return "Tune the weights"

    def add_controls(self, layout: QVBoxLayout) -> None:
        """Add level-specific controls to the knobs card (above Reset / Run)."""

    def waypoints(self) -> list[tuple[float, float]]:
        """Waypoints sent with the run (levels with waypoints override this)."""
        return []

    def reset_controls(self) -> None:
        """Reset button: back to the level's defaults."""
        self.knobs.reset()

    def set_controls_enabled(self, enabled: bool) -> None:
        """Lock level-specific controls while the engine computes."""

    def add_extras(self, column: QVBoxLayout) -> None:
        """Add level-specific widgets (e.g. a budget bar) under the map, above the replay bar.
        Keep them low (one row, ~70 px): the map gets the rest of the height."""

    def update_extras(self, t: float) -> None:
        """Update level-specific widgets for replay time t."""

    def result_rows(self, result: RunResult) -> list[tuple[str, str, str]]:
        """(name, value, note) rows for the result card."""
        return [("Time", f"{result.metrics.get('time', 0):.1f} s",
                 f"limit {self.data.t_limit:g} s")]

