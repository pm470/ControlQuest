"""Level 3: "Dead End" (PRD 7, Level 3): nonconvexity and local optima.

Numbers (map, blocks, locked weights and margin, waypoint rules, pars) live in
game/level_data/dead_end.json, shared with the engine. The engine's rules are in
engine_server/level_rules/dead_end.py. The player does not tune weights here: they
place up to 3 waypoints on the map (gameplay/waypoint_editor.py), and the MPC
reference switches from one to the next.
"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from ..gameplay.level_data import load_level_data
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.ocp_card import OcpSpec
from ..gameplay.waypoint_editor import WaypointEditor
from ..ui.widgets import Button, label
from .base import LevelInfo


class DeadEndWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Bring the ball to the star and stop there within {d.t_limit:g} s. "
                f"The weights are fixed: help the controller with up to {d.max_waypoints} "
                f"waypoints instead. For ★★★: within {d.pars['time']:g} s using at most "
                f"{d.pars['waypoints']:g} waypoint.")

    def controls_title(self) -> str:
        return "Place waypoints"

    def add_controls(self, layout: QVBoxLayout) -> None:
        d = self.data
        layout.addWidget(label("Click on the map to add a waypoint, drag it to move it, "
                               "right-click to delete it. The MPC aims at waypoint 1, then 2, ... "
                               f"and switches to the next one {d.switch_radius:g} m before "
                               "reaching it.", "caption", wrap=True))
        row = QHBoxLayout()
        self.wp_count = label("", "body")
        row.addWidget(self.wp_count, 1)
        self.clear_button = Button("Clear", variant="ghost")
        self.clear_button.setToolTip("Remove all waypoints")
        row.addWidget(self.clear_button)
        layout.addLayout(row)
        self.wp_list = label("", "caption", wrap=True)
        layout.addWidget(self.wp_list)

        self.editor = WaypointEditor(self.map, d.max_waypoints)
        self.editor.changed.connect(self._on_waypoints)
        self.editor.rejected.connect(lambda msg: self.status.setText(msg))
        self.clear_button.clicked.connect(self.editor.clear)
        self._on_waypoints([], initial=True)

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

    def waypoints(self):
        return [list(w) for w in self.editor.points]

    def reset_controls(self) -> None:
        self.editor.clear()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.editor.set_enabled(enabled)
        self.clear_button.setEnabled(enabled and bool(self.editor.points))

    def ocp_spec(self) -> OcpSpec:
        d = self.data
        n = d.N
        lk = d.locked
        (x0, y0), (x1, y1) = d.workspace
        return OcpSpec(
            objective=[
                rf"\min_{{u_0,\,\ldots,\,u_{{{n - 1}}}}}\;\; \sum_{{k=0}}^{{{n - 1}}} \Delta t\,"
                rf"\ell(x_k,u_k) \;+\; \|x_{{{n}}}-x_{{\mathrm{{ref}}}}\|_P^2",
                rf"\ell(x,u) = {lk['q_p']:g}\,\|p-p_{{\mathrm{{ref}}}}\|^2 + {lk['q_v']:g}\,\|v\|^2 "
                rf"+ {lk['r']:g}\,\|u\|^2",
                rf"p_{{\mathrm{{ref}}}} = \mathrm{{next\ waypoint}}\ \mathrm{{(last:}}\ p_{{\star}}),"
                rf"\quad P = {d.raw.get('terminal_factor', 10):g}\,Q",
            ],
            constraints=[
                r"x_0 = \hat{x}",
                r"x_{k+1} = f(x_k,\,u_k)",
                rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
                rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
                rf"(p_k-c_j)^{{T}} E_j\, (p_k-c_j) \geq 1,\quad j = 1,\ldots,{len(d.blocks)}",
            ],
            notes=(f"Re-solved every Δt = {d.dt:g} s, {n} steps ({n * d.dt:g} s) ahead. With "
                   "obstacles the OCP is nonconvex: SQP finds a local optimum."),
            legend=[f"c_j, E_j: ellipse around block j (dashed), {d.margin:g} m margin · "
                    "p_ref: the current reference · p★: target",
                    "The ellipse constraints are soft (large L1 penalty) so the QP stays solvable."],
        )

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s", f"limit {d.t_limit:g} s · ★★ ≤ {d.pars['time']:g} s"),
            ("Waypoints", f"{m.get('waypoints', 0)}", f"★★★ ≤ {d.pars['waypoints']:g}"),
            ("Closest to a block", f"{m.get('min_clearance', 0):.1f} m", ""),
        ]


def build(ctx, level: LevelInfo) -> DeadEndWidget:
    return DeadEndWidget(ctx, level, load_level_data(level.id))


LEVEL = LevelInfo(
    number=3,
    id="dead_end",
    title="Dead End",
    topic="Local optima",
    briefing=("The direct route looks open... it isn't. Help the controller with up to "
              "3 waypoints."),
    concept=("With obstacles the OCP is nonconvex. A short-horizon MPC is a local planner "
             "and can get trapped; a rough higher-level route (waypoints) gets it out."),
    hints=(
        "The controller only sees 3 seconds ahead. What does it see inside the U?",
        "Give it an intermediate goal it can reach without entering the trap.",
        "One well-placed waypoint beside the U is enough for three stars.",
    ),
    accent="lilac",
    play_screen=build,
)
