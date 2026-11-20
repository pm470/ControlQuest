"""The playable level (PRD 5.2): three tiles (AGENTS.md section 10, "Design rules"):

    map tile                     | OCP tile               | controls tile
    [Simulation | Analysis]      | the OCP your MPC solves| Goal
    map (+ result card) / plots  | Whole run (4 numbers)  | knobs (+ level controls)
    level extras                 |                        | Reset · Run
    replay well: ▶ scrubber time 2× ‹ k/n ›               | (level sections) · Stuck? hints

The map tile has two tabs (2026-11-20): Simulation (the map, default) and Analysis (the
level's time-series plots of the latest run, gameplay/analysis_panel.py). Both share the
level extras and the replay well; the time cursor in the plots follows the playback clock.

Narrow windows: the OCP tile moves into the right column, under the controls tile.

Flow of one run:
    Run -> RunRequest(level id, knobs) -> engine (Docker) -> RunResult
        -> map + playback replay it -> at the end: result card, stars saved

A level subclasses LevelPlayWidget and overrides the hooks at the bottom:
goal_text(), ocp_spec(), add_extras(column), update_extras(t), result_rows(result),
analysis_plots(result) (the two plots of the Analysis tab),
and for levels with other controls than weights (e.g. waypoints): controls_title(),
add_controls(layout), add_side_cards(column), waypoints(), fix(), on_result(result),
reset_controls(), set_controls_enabled(enabled);
they call controls_changed() when the player edits something, and refresh_ocp() when
the OCP shown should change.
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ..core.context import AppContext
from ..core.navigation import ScreenId
from ..engine.protocol import EngineStatus, RunRequest, RunResult
from ..levels.base import LevelInfo
from ..research import research_for
from ..ui.math_text import math_text
from ..ui.widgets import Button, Card, SegmentedControl, label, scrollable, well
from .analysis_panel import AnalysisPanel, PlotSpec
from .knob_panel import KnobPanel, knob_colors
from .level_data import LevelData
from .map_view import MapView
from .ocp_card import STATE_LEGEND, OcpCard, OcpSpec
from .playback import Playback, PlaybackBar
from .result_panel import ResultPanel
from .run_info_card import RunInfoCard
from .solve_selector import SolveSelector

SIDE_WIDTH = 330
MIDDLE_WIDTH = 350
WIDE_MIN_WIDTH = 1150  # below this the OCP column moves into the right column
TILE_PADDING = 20


def standard_ocp(data: LevelData) -> OcpSpec:
    """The standard point-mass OCP with the weights q_p, q_v, r as knobs, built from the
    level file's numbers (Level 1; also its intro)."""
    d = data
    n = d.N
    (x0, y0), (x1, y1) = d.workspace
    return OcpSpec(
        objective=[
            rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
            rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\star}}\|_P^2",
            r"\ell(x,u) = \knob{q_p}{q_p}\,\|p-p_{\star}\|^2 + \knob{q_v}{q_v}\,\|v\|^2"
            r" + \knob{r}{r}\,\|u\|^2",
            rf"Q = \mathrm{{diag}}(q_p,q_p,q_v,q_v),\quad P = {d.raw.get('terminal_factor', 10):g}\,Q",
        ],
        constraints=[
            r"x_0 = \hat{x}",
            r"x_{k+1} = f(x_k,\,u_k)",
            rf"|a_x|,\ |a_y| \leq {d.a_max:g}",
            rf"|v_x|,\ |v_y| \leq {d.v_max:g}",
            rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
        ],
        notes=(rf"Re-solved every $\Delta t = {d.dt:g}$ s from the measured state $\hat{{x}}$, "
               rf"$N = {n}$ steps ({n * d.dt:g} s) ahead; only $u_0$ is applied."),
        legend=STATE_LEGEND,
    )


class LevelPlayWidget(QWidget):
    navigate = Signal(str, object)  # forwarded by LevelScreen, like BaseScreen.navigate
    insights_requested = Signal()  # "Insights" on the result card: LevelScreen opens the debrief

    def __init__(self, ctx: AppContext, level: LevelInfo, data: LevelData,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx, self.level, self.data = ctx, level, data
        self.result: RunResult | None = None
        self._ticket = None
        self._hints_shown = 0
        # a result that arrives while this screen is hidden (the player went to the intro during
        # "Computing...") is replayed when the screen is shown again, not unseen in the background
        self._autoplay_pending = False
        self.playback = Playback(self)

        # --- left: the map tile: map (result card on top), level extras, replay well ---
        self.map = MapView()
        self.map.set_level(data)
        self.result_panel = ResultPanel()
        self.result_panel.hide()
        sim_page = QWidget()  # the Simulation tab: the map with the result card on top
        stack = QGridLayout(sim_page)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addWidget(self.map, 0, 0)
        stack.addWidget(self.result_panel, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.analysis = AnalysisPanel()  # the Analysis tab: the level's plots of the latest run
        self.pages = QStackedWidget()
        self.pages.addWidget(sim_page)
        self.pages.addWidget(self.analysis)
        self.tabs = SegmentedControl(["Simulation", "Analysis"])
        self.tabs.buttons[0].setToolTip("The playing field with the ball and the MPC's plan")
        self.tabs.buttons[1].setToolTip("Plots of the latest run over time, with the replay time")
        self.tabs.changed.connect(self.pages.setCurrentIndex)
        self.bar = PlaybackBar(self.playback)
        self.solve_selector = SolveSelector()
        self.solve_selector.setToolTip("Step through the MPC solves of this run: the map shows "
                                       "the plan computed in the selected solve")
        map_tile = Card(padding=16, spacing=10, shadow=False)
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(0, 0, 0, 0)
        tabs_row.addWidget(self.tabs)
        tabs_row.addStretch(1)
        map_tile.body.addLayout(tabs_row)
        map_tile.body.addWidget(self.pages, 1)
        self.add_extras(map_tile.body)  # level extras (e.g. battery) under the map, above the replay
        replay = well()
        replay_row = QHBoxLayout(replay)
        replay_row.setContentsMargins(8, 7, 8, 7)
        replay_row.setSpacing(10)
        replay_row.addWidget(self.bar, 1)
        replay_row.addWidget(self.solve_selector)
        map_tile.body.addWidget(replay)

        # --- middle: one tile with the OCP and the solver info ---
        # Wide window: own column next to the map. Narrow window: moved into the
        # right column below the controls (see resizeEvent).
        self.knob_colors = knob_colors(data.knobs)  # same colours in the knobs and in the OCP
        self._middle = QWidget()
        mid = QVBoxLayout(self._middle)
        mid.setContentsMargins(0, 0, 0, 0)
        ocp_tile = Card(padding=TILE_PADDING, spacing=18, shadow=False)
        self.ocp_card = OcpCard(self.ocp_spec(), knob_colors=self.knob_colors)
        ocp_tile.body.addWidget(self.ocp_card)
        ocp_tile.body.addStretch(1)
        self.run_info = RunInfoCard()
        ocp_tile.body.addWidget(self.run_info)
        mid.addWidget(ocp_tile, 1)
        self._middle_scroll = scrollable(self._middle)
        self._middle_scroll.setFixedWidth(MIDDLE_WIDTH)
        self._wide = True

        # --- right: one tile with goal, controls + Reset/Run, level sections, hints ---
        side = QWidget()
        col = QVBoxLayout(side)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(16)
        self._side_col = col
        controls = Card(padding=TILE_PADDING, spacing=16, shadow=False)
        tile = controls.body

        goal = QVBoxLayout()
        goal.setSpacing(3)
        goal.addWidget(label("Goal", "eyebrow"))
        goal.addWidget(math_text(self.goal_text(), "goal"))  # $...$ in the LaTeX font
        tile.addLayout(goal)

        # the level's controls: title, knobs, and whatever add_controls() adds
        self.controls_box = QVBoxLayout()
        self.controls_box.setSpacing(12)
        self.controls_box.addWidget(label(self.controls_title(), "eyebrow"))
        self.knobs = KnobPanel(data.knobs)
        self.controls_box.addWidget(self.knobs)
        self.knobs.setVisible(bool(data.knobs))
        self.add_controls(self.controls_box)
        tile.addLayout(self.controls_box)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.reset_button = Button("Reset", scale="tall")
        self.reset_button.setToolTip("Back to the level's default settings")
        self.run_button = Button("Run  ▶", variant="primary", scale="large")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.run_button, 1)
        tile.addLayout(buttons)
        self.status = math_text("", "caption")
        tile.addWidget(self.status)
        self.add_side_cards(tile)  # level sections under the controls (e.g. a comparison table)
        tile.addStretch(1)

        if level.hints:
            row = QHBoxLayout()
            row.addWidget(label("Stuck?", "subheading"), 1)
            self.hint_button = Button(f"Show hint 1/{len(level.hints)}", variant="link")
            row.addWidget(self.hint_button)
            tile.addLayout(row)
            self.hint_box = QVBoxLayout()
            self.hint_box.setSpacing(6)
            tile.addLayout(self.hint_box)
            self.hint_button.clicked.connect(self._show_hint)
        col.addWidget(controls, 1)
        self._middle_slot = col.count()  # where the middle column goes when narrow

        side_scroll = scrollable(side)
        side_scroll.setFixedWidth(SIDE_WIDTH)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addWidget(map_tile, 1)
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
        self.result_panel.insights.connect(self.insights_requested)
        self.result_panel.set_insights_visible(research_for(level.id) is not None)
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
        self.status.setText(self.computing_text())
        self._ticket = self.ctx.engine.request_run(
            RunRequest(self.level.id, self.knobs.values(), self.waypoints(), self.fix()), parent=self)
        self._ticket.finished.connect(self._on_result)
        self._ticket.failed.connect(self._on_failed)

    def _on_result(self, result: RunResult) -> None:
        self._set_busy(False)
        self.result = result
        m = result.metrics
        self.status.setText(f"Replaying: {result.trajectory.duration:.1f} s of motion, "
                            f"{result.trajectory.n_solves} MPC solves "
                            f"(~{m.get('mean_solve_ms', 0):.2f} ms each).")
        self.map.set_trajectory(result.trajectory)
        tr = result.trajectory
        self.solve_selector.set_count(tr.n_solves, tr.dt, [tr.time_of_solve(i) for i in range(tr.n_solves)])
        self.run_info.set_result(result)
        self._build_analysis(result)
        self.on_result(result)
        self.playback.load(result.trajectory.duration)
        self.bar.set_enabled_for_run(True)
        if self.isVisible():
            self.playback.play()
        else:
            self._autoplay_pending = True

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._autoplay_pending:
            self._autoplay_pending = False
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
        self.analysis.set_time(t)  # moves the plots' cursor only (no re-render)
        if self.result is not None:
            k = self.result.trajectory.solve_at(t)
            self.solve_selector.set_current(k)
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
        self.result_panel.show_result(r, self.result_rows(r), self.next_unlocked(),
                                      show_stars=not self.level.tutorial)

    def next_unlocked(self) -> bool:
        """True if there is a next level and it is unlocked (the result card then offers
        "Next level" after a success; the debrief follows the same rule)."""
        nxt = self.ctx.next_level(self.level)
        return nxt is not None and self.ctx.state.is_unlocked(nxt, self.ctx.levels)

    def _watch_again(self) -> None:
        self.result_panel.hide()
        self.playback.replay()

    def refresh_ocp(self) -> None:
        """Re-render the OCP card from ocp_spec() (e.g. after the player picked another fix)."""
        self.ocp_card.set_spec(self.ocp_spec())

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
            self.hint_box.addWidget(math_text(f"{self._hints_shown + 1}. {hints[self._hints_shown]}",
                                          "body", wrap=True))
            self._hints_shown += 1
        done = self._hints_shown >= len(hints)
        self.hint_button.setEnabled(not done)
        self.hint_button.setText("No more hints" if done else
                                 f"Show hint {self._hints_shown + 1}/{len(hints)}")

    def _on_engine_status(self, status: EngineStatus) -> None:
        self.run_button.setToolTip("Simulate this controller" if status.can_run
                                   else f"{status.message}: start the MPC engine first")
        if status.state == "outdated":
            self.status.setText(status.message + " (Ctrl+C in its terminal, then start_engine).")

    # --- hooks for levels ----------------------------------------------------------------
    def goal_text(self) -> str:
        return f"Bring the ball to the star and stop there within {self.data.t_limit:g} s."

    def ocp_spec(self) -> OcpSpec:
        """The OCP shown in the middle tile. Default: standard_ocp() (the point-mass OCP
        with weights q_p, q_v, r). Wrap what a knob changes in \\knob{name}{...}: it is
        drawn in that knob's colour (top level of a line only)."""
        return standard_ocp(self.data)

    def computing_text(self) -> str:
        """Status line while the engine computes a run."""
        return "The MPC is computing your run..."

    def controls_title(self) -> str:
        return "Tune the weights"

    def add_controls(self, layout: QVBoxLayout) -> None:
        """Add level-specific controls under the knobs (above Reset / Run). layout holds
        [0] the controls title, [1] the knobs. Plain widgets only: no cards inside the tile."""

    def waypoints(self) -> list[tuple[float, float]]:
        """Waypoints sent with the run (levels with waypoints override this)."""
        return []

    def fix(self) -> str | None:
        """The fix sent with the run (levels with fixes override this)."""
        return None

    def reset_controls(self) -> None:
        """Reset button: back to the level's defaults."""
        self.knobs.reset()

    def set_controls_enabled(self, enabled: bool) -> None:
        """Lock level-specific controls while the engine computes."""

    def add_side_cards(self, column: QVBoxLayout) -> None:
        """Add level-specific sections (e.g. a comparison table) to the controls tile, under
        Reset / Run. Plain widgets with a subheading, not cards (no boxes in boxes)."""

    def on_result(self, result: RunResult) -> None:
        """Called when a new run result arrives (before its replay starts)."""

    def add_extras(self, column: QVBoxLayout) -> None:
        """Add level-specific widgets (e.g. a budget bar) to the map tile, under the map and
        above the replay well. Plain widgets, no cards; keep them low (one row, ~30-90 px):
        the map gets the rest of the height."""

    def update_extras(self, t: float) -> None:
        """Update level-specific widgets for replay time t."""

    # --- the Analysis tab ------------------------------------------------------------------
    def _build_analysis(self, result: RunResult) -> None:
        """Replace the plots with the ones of this run (once per new result)."""
        try:
            self.analysis.set_plots(self.analysis_plots(result))
        except Exception:  # noqa: BLE001: a plot problem must never break a run
            traceback.print_exc()
            self.analysis.clear("The plots could not be drawn for this run.")
        self.analysis.set_time(self.playback.time)

    def set_analysis_available(self, available: bool, reason: str = "") -> None:
        """Enable/disable the Analysis tab (Level 0: only after the tour's replay); disabling
        switches back to the Simulation tab."""
        self.tabs.set_option_enabled(1, available, "" if available else reason)
        if not available and self.tabs.current() == 1:
            self.tabs.set_current(0)
            self.pages.setCurrentIndex(0)

    def analysis_plots(self, result: RunResult) -> list[PlotSpec]:
        """The Analysis tab's plots for this run (each level provides two). Data only: built
        from result.trajectory and the level file, never recomputing the run."""
        return []

    def debrief_rows(self, result: RunResult) -> list[tuple[str, str, str]]:
        """The run's numbers in the Research debrief: by default the result card's rows."""
        return self.result_rows(result)

    def debrief_visual(self, result: RunResult) -> QWidget | None:
        """An existing visual of the level frozen at the run's end, for the Research debrief
        (e.g. the battery bar). A new widget every call; None = no visual."""
        return None

    def result_rows(self, result: RunResult) -> list[tuple[str, str, str]]:
        """(name, value, note) rows for the result card."""
        return [("Time", f"{result.metrics.get('time', 0):.1f} s",
                 f"limit {self.data.t_limit:g} s")]

