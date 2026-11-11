"""Level 4: "Heavy Ball" (PRD 7, Level 4): model mismatch, constraint tightening
vs a better model.

Numbers (bay map, the hidden real gain, test drive, limits, weights, pars, knobs)
live in game/level_data/heavy_ball.json, shared with the engine. The engine's rules
are in engine_server/level_rules/heavy_ball.py.

The real ball responds less to the motors than the controller's model thinks. The
player tunes the obstacle margin m and the model gain g, and can make a test drive
(constant acceleration from rest: predicted vs measured distance) to identify g.
The map shows a dashed "ghost" ball: where the plan from 1 s earlier expected the ball.
"""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from ..engine.protocol import TestDrive
from ..gameplay.level_data import load_level_data
from ..gameplay.level_play_widget import LevelPlayWidget
from ..gameplay.ocp_card import OcpSpec
from ..ui.widgets import Button, Card, label
from .base import LevelInfo


class HeavyBallWidget(LevelPlayWidget):
    def goal_text(self) -> str:
        d = self.data
        return (f"Park the ball on the star in the bay within {d.t_limit:g} s without touching the "
                "walls. The real ball responds less to the motors than the controller's model "
                f"thinks. ★★: within {d.pars['time']:g} s; ★★★: within {d.pars['time_best']:g} s.")

    def controls_title(self) -> str:
        return "Tune the controller"

    # --- controls: knobs (margin, g) + test drive ---------------------------------------------
    def add_controls(self, layout: QVBoxLayout) -> None:
        td = self.data.raw["test_drive"]
        layout.addWidget(label(f"Test drive: push with a_x = {td['accel']:g} m/s² for "
                               f"{td['duration']:g} s from rest and compare what your model (g) "
                               "predicts with what the real ball does.", "caption", wrap=True))
        row = QHBoxLayout()
        self.drive_button = Button("Test drive", variant="default")
        self.drive_button.setToolTip("No MPC involved: a constant push on an empty field")
        row.addWidget(self.drive_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.drive_result = label("", "body", wrap=True)
        self.drive_result.hide()
        layout.addWidget(self.drive_result)
        self.drive_button.clicked.connect(self._test_drive)
        self.map.show_ghost = True
        self.knobs.changed.connect(self._on_knobs)
        self._on_knobs()

    def _on_knobs(self) -> None:
        self.map.set_margin(self.knobs.values()["margin"])
        self.refresh_ocp()

    def _test_drive(self) -> None:
        if not self.ctx.engine.status.can_run:
            self.status.setText(f"Can't test drive: {self.ctx.engine.status.message}.")
            return
        self.drive_button.setEnabled(False)
        self.drive_button.setText("Driving...")
        ticket = self.ctx.engine.request_test_drive(self.level.id, self.knobs.values(), parent=self)
        ticket.finished.connect(self._on_test_drive)
        ticket.failed.connect(self._on_test_drive_failed)

    def _on_test_drive(self, r: TestDrive) -> None:
        self.drive_button.setEnabled(True)
        self.drive_button.setText("Test drive")
        self.drive_result.setText(f"Your model (g = {r.g:g}) predicts <b>{r.predicted_m:.2f} m</b>; "
                                  f"the real ball went <b>{r.measured_m:.2f} m</b>.")
        self.drive_result.show()

    def _on_test_drive_failed(self, reason: str) -> None:
        self.drive_button.setEnabled(True)
        self.drive_button.setText("Test drive")
        self.status.setText(f"Test drive failed: {reason}")

    def set_controls_enabled(self, enabled: bool) -> None:
        self.drive_button.setEnabled(enabled)

    # --- under the map: what the dashed ghost ball means ----------------------------------------
    def add_extras(self, column: QVBoxLayout) -> None:
        card = Card(padding=10, spacing=0, shadow=False)
        M = int(self.data.raw.get("prediction_lookahead", 10))
        card.body.addWidget(label(f"Dashed ball: where the plan from {M * self.data.dt:g} s earlier "
                                  "expected the ball to be now. If it runs ahead of the real ball, the "
                                  "model is wrong.", "caption", wrap=True))
        column.addWidget(card)

    # --- the OCP with the current knob values ---------------------------------------------------
    def ocp_spec(self) -> OcpSpec:
        d = self.data
        n, lk = d.N, d.locked
        knobs = self.knobs.values() if hasattr(self, "knobs") else {k.name: k.default for k in d.knobs}
        g, m = knobs["g"], knobs["margin"]
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
                rf"p_{{k+1}} = p_k + \Delta t\, v_k + \frac{{1}}{{2}}\Delta t^2\, g\, u_k",
                rf"v_{{k+1}} = v_k + \Delta t\, g\, u_k,\quad g = {g:.2g}",
                rf"|a_x|,\ |a_y| \leq {d.a_max:g},\quad |v_x|,\ |v_y| \leq {d.v_max:g}",
                rf"{x0:g} \leq p_x \leq {x1:g},\quad {y0:g} \leq p_y \leq {y1:g}",
                rf"(p_k-c_j)^{{T}} E_j(m)\, (p_k-c_j) \geq 1,\quad m = {m:.2g}\ \mathrm{{m}}",
            ],
            notes=(f"Re-solved every Δt = {d.dt:g} s, {n} steps ({n * d.dt:g} s) ahead. The model "
                   "uses YOUR gain g; the real ball has its own."),
            legend=["g: model actuator gain (1 = the ball does exactly what is commanded) · "
                    "E_j(m): ellipse around block j, each semi-axis enlarged by the margin m"],
        )

    def result_rows(self, result):
        m, d = result.metrics, self.data
        return [
            ("Time", f"{m['time']:.1f} s",
             f"★★ ≤ {d.pars['time']:g} s · ★★★ ≤ {d.pars['time_best']:g} s"),
            ("Model gain g", f"{m.get('g', 0):g}", f"margin {m.get('margin', 0):g} m"),
            ("Prediction error", f"{m.get('max_prediction_error', 0):.2f} m",
             f"max, {m.get('prediction_lookahead_s', 1):g} s ahead"),
        ]


def build(ctx, level: LevelInfo) -> HeavyBallWidget:
    return HeavyBallWidget(ctx, level, load_level_data(level.id))


LEVEL = LevelInfo(
    number=4,
    id="heavy_ball",
    title="Heavy Ball",
    topic="Model mismatch",
    briefing=("Someone swapped the ball. It looks the same but responds less to the "
              "motors. Park it in the bay without touching the walls."),
    concept=("The controller plans with a model. If the real system differs, safe plans "
             "crash in reality. Fix it with a safety margin (robust, slower) or a better "
             "model (identify the real parameter)."),
    hints=(
        "Watch the dashed ghost ball: where the plan said the ball would be, and where it is.",
        "A test drive tells you how strongly the real ball responds.",
        "Set the model gain to what you measured: predicted distance = g · ½ · a · t².",
    ),
    accent="mint",
    play_screen=build,
)
