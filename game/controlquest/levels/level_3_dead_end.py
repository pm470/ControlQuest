"""Level 3: "Dead End" (PRD 7, Level 3): nonconvexity and local optima.

Numbers (map, blocks, locked weights and margin, fixes, the N knob, waypoint rules,
pars) live in game/level_data/dead_end.json, shared with the engine. The engine's
rules are in engine_server/level_rules/dead_end.py.

The default MPC gets stuck in the U. The player picks ONE fix at a time
(gameplay/fix_selector.py) and tunes only its control:
    Longer horizon  -> the horizon N (knob "N": slider or typed, any whole number in range)
    Waypoints       -> click / drag / right-click on the map (gameplay/waypoint_editor.py)
"Your experiments" (gameplay/comparison_card.py) keeps the best run of each fix, so the
player sees which fix works and what it costs per MPC solve. A third fix (a better
terminal cost / cost-to-go) is planned: see the TODO in AGENTS.md section 6.
"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..gameplay.comparison_card import ComparisonCard
from ..gameplay.fix_selector import FixSelector
from ..gameplay.level_data import load_level_data
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.ocp_card import OcpSpec
from ..gameplay.waypoint_editor import WaypointEditor
from ..ui.widgets import Button, label
from .base import LevelInfo

HORIZON, WAYPOINTS = "horizon", "waypoints"


class DeadEndWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Bring the ball to the star and stop there within {d.t_limit:g} s. The weights "
                "are fixed and the default MPC gets stuck. Pick one fix at a time, run it, and "
                f"compare them under \"Your experiments\". ★★: within {d.pars['time']:g} s; ★★★: "
                f"also with at most {d.pars['waypoints']:g} waypoint.")

    def controls_title(self) -> str:
        return "Choose a fix"

    # --- controls --------------------------------------------------------------------------
    def add_controls(self, layout: QVBoxLayout) -> None:
        d = self.data
        self.selector = FixSelector(d.fixes)
        layout.insertWidget(1, self.selector)  # under the title, above the knobs (N)

        # waypoint controls (shown for the waypoint fix only)
        self.wp_box = QWidget()
        box = QVBoxLayout(self.wp_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addWidget(label("Map: click = add, drag = move, right-click = delete. The MPC aims at "
                            f"them in order, switching {d.switch_radius:g} m before each one.",
                            "caption", wrap=True))
        row = QHBoxLayout()
        self.wp_count = label("", "body")
        row.addWidget(self.wp_count, 1)
        self.clear_button = Button("Clear", variant="ghost")
        self.clear_button.setToolTip("Remove all waypoints")
        row.addWidget(self.clear_button)
        box.addLayout(row)
        self.wp_list = label("", "caption", wrap=True)
        box.addWidget(self.wp_list)
        layout.addWidget(self.wp_box)

        # horizon note (shown for the horizon fix only)
        self.n_note = label("", "caption", wrap=True)
        layout.addWidget(self.n_note)

        self.editor = WaypointEditor(self.map, d.max_waypoints)
        self.editor.changed.connect(self._on_waypoints)
        self.editor.rejected.connect(lambda msg: self.status.setText(msg))
        self.clear_button.clicked.connect(self.editor.clear)
        self.selector.changed.connect(self._on_fix)
        self.knobs.changed.connect(self._on_n_changed)
        self._built_ns = {d.N}  # horizons the engine has compiled (as far as this screen knows)
        self._on_waypoints([], initial=True)
        self._on_fix(self.selector.current(), initial=True)

    def add_side_cards(self, column: QVBoxLayout) -> None:
        self.comparison = ComparisonCard(self.data.fixes)
        column.addWidget(self.comparison)

    def _on_fix(self, fix: str, initial: bool = False) -> None:
        """Show only the chosen fix's controls; waypoints only exist for the waypoint fix."""
        self.knobs.set_visible_knobs([k.name for k in self.data.knobs if k.fix == fix])
        self.wp_box.setVisible(fix == WAYPOINTS)
        self.n_note.setVisible(fix == HORIZON)
        self.editor.set_enabled(fix == WAYPOINTS)
        self.map.set_waypoints(self.editor.points if fix == WAYPOINTS else [])
        self._on_n_changed()
        self.refresh_ocp()
        if not initial:
            self.status.setText("")
            self.controls_changed()

    def _on_n_changed(self) -> None:
        n = int(self.knobs.values().get("N", self.data.N))
        k = next((k for k in self.data.knobs if k.name == "N"), None)
        rng = f"Type any N from {k.min:g} to {k.max:g}. " if k else ""
        self.n_note.setText(f"N = {n} steps = {n * self.data.dt:g} s ahead "
                            f"({n * self.data.dt * self.data.v_max:g} m at full speed). {rng}A bigger N "
                            "means a bigger OCP to solve at every step; a new N first builds its "
                            "solver (a few seconds, once).")
        if self.selector.current() == HORIZON:
            self.refresh_ocp()

    def _on_waypoints(self, points, initial: bool = False) -> None:
        n = len(points)
        self.wp_count.setText(f"{n} / {self.data.max_waypoints} waypoints")
        self.wp_list.setText("  ·  ".join(f"{i + 1}: ({x:.1f}, {y:.1f})"
                                          for i, (x, y) in enumerate(points)) or "No waypoints: "
                             "the MPC aims straight at the star.")
        self.clear_button.setEnabled(n > 0)
        if not initial:
            self.status.setText("")
            self.controls_changed()

    def computing_text(self) -> str:
        n = int(self.knobs.values().get("N", self.data.N))
        if self.fix() == HORIZON and n not in self._built_ns:
            return (f"The engine is building the solver for N = {n} (a few seconds, only the first "
                    "time), then computing your run...")
        return super().computing_text()

    def fix(self) -> str:
        return self.selector.current()

    def waypoints(self):
        return [list(w) for w in self.editor.points] if self.fix() == WAYPOINTS else []

    def reset_controls(self) -> None:
        self.knobs.reset()
        self.editor.clear()
        if self.fix() != WAYPOINTS:
            self.map.set_waypoints([])

    def set_controls_enabled(self, enabled: bool) -> None:
        self.selector.setEnabled(enabled)
        self.editor.set_enabled(enabled and self.fix() == WAYPOINTS)
        self.clear_button.setEnabled(enabled and bool(self.editor.points))

    def on_result(self, result) -> None:
        self._built_ns.add(int(result.metrics.get("N", self.data.N)))
        self.comparison.record(result)

    # --- the OCP of the chosen fix -----------------------------------------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        selector = getattr(self, "selector", None)  # ocp_spec() is first called before add_controls
        fix = selector.current() if selector else "none"
        n = int(self.knobs.values().get("N", d.N)) if fix == HORIZON and hasattr(self, "knobs") else d.N
        lk = d.locked
        ref = r"p_{\mathrm{ref}}" if fix == WAYPOINTS else r"p_{\star}"
        xref = r"x_{\mathrm{ref}}" if fix == WAYPOINTS else r"x_{\star}"
        (x0, y0), (x1, y1) = d.workspace
        objective = [
            rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
            rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-{xref}\|_P^2",
            rf"\ell(x,u) = {lk['q_p']:g}\,\|p-{ref}\|^2 + {lk['q_v']:g}\,\|v\|^2 + {lk['r']:g}\,\|u\|^2",
        ]
        if fix == WAYPOINTS:
            objective.append(rf"p_{{\mathrm{{ref}}}} = \mathrm{{next\ waypoint}}\ \mathrm{{(last:}}\ "
                             rf"p_{{\star}}),\quad P = {d.raw.get('terminal_factor', 10):g}\,Q")
        else:
            objective.append(rf"P = {d.raw.get('terminal_factor', 10):g}\,Q")
        notes = {
            "none": "The default MPC.",
            HORIZON: f"Fix: a longer horizon, N = {n}.",
            WAYPOINTS: "Fix: waypoints; the reference switches from one to the next.",
        }[fix]
        return OcpSpec(
            objective=objective,
            constraints=[
                r"x_0 = \hat{x}",
                r"x_{k+1} = f(x_k,\,u_k)",
                rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
                rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
                rf"(p_k-c_j)^{{T}} E_j\, (p_k-c_j) \geq 1,\quad j = 1,\ldots,{len(d.blocks)}",
            ],
            notes=(f"{notes} Re-solved every Δt = {d.dt:g} s, {n} steps ({n * d.dt:g} s) ahead. "
                   "With obstacles the OCP is nonconvex: SQP finds a local optimum."),
            legend=[f"c_j, E_j: ellipse around block j (dashed), {d.margin:g} m margin · "
                    + ("p_ref: the current waypoint · " if fix == WAYPOINTS else "") + "p★: target",
                    "The ellipse constraints are soft (large L1 penalty) so the QP stays solvable."],
        )

    def result_rows(self, result):
        m, d = result.metrics, self.data
        fix = m.get("fix", "none")
        rows = [
            ("Fix", self.selector.label_of(fix), ""),
            ("Time", f"{m['time']:.1f} s", f"limit {d.t_limit:g} s · ★★ ≤ {d.pars['time']:g} s"),
            ("Solve time", f"{m.get('mean_solve_ms', 0):.2f} ms", f"per solve, N = {m.get('N', d.N)}"),
        ]
        if fix == WAYPOINTS:
            rows.append(("Waypoints", f"{m.get('waypoints', 0)}", f"★★★ ≤ {d.pars['waypoints']:g}"))
        return rows


def build(ctx, level: LevelInfo) -> DeadEndWidget:
    return DeadEndWidget(ctx, level, load_level_data(level.id))


LEVEL = LevelInfo(
    number=3,
    id="dead_end",
    title="Dead End",
    topic="Local optima",
    briefing=("The direct route looks open... it isn't. Two ideas to get the controller out: "
              "let it look further ahead, or give it a route. Find out which one works."),
    concept=("With obstacles the OCP is nonconvex. MPC with SQP is a local planner and can get "
             "trapped; more foresight does not help, a rough higher-level route (waypoints) does."),
    hints=(
        "Try a fix and watch the dashed plan: does the MPC ever plan a way around the wall?",
        "A longer horizon sees further, but SQP starts from the previous plan and stays on the same "
        "side. Compare the solve times in \"Your experiments\" too.",
        "Waypoints give the MPC a route out of the trap: one above the top-right corner of the U "
        "is enough for three stars.",
    ),
    accent="lilac",
    play_screen=build,
)
