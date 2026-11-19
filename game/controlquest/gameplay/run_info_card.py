"""Solver info, under the OCP in the same tile: "Whole run" with the number of solves and
the run time, and four big numbers for the whole run (total cost, average solve time,
average SQP iterations, solved count / acados status). Details are in the tooltips.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..engine.protocol import RunResult
from ..ui import theme
from ..ui.math_text import math_text
from ..ui.widgets import label, star_subscript

ACADOS_STATUS = {0: "solved", 1: "NaN detected", 2: "max. iterations", 3: "min. step size",
                 4: "QP failure", 5: "ready"}


def _sci(x: float) -> str:
    """4.025e+04 -> '4.0·10⁴' (short, readable); small numbers stay plain."""
    if x == 0 or 1e-2 <= abs(x) < 100:
        return f"{x:.3g}"
    if 100 <= abs(x) < 1e4:
        return f"{x:.0f}"
    mant, exp = f"{x:.1e}".split("e")
    sup = str(int(exp)).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{mant}·10{sup}"


class _Stat(QWidget):
    """A big number with a small caption under it."""

    def __init__(self, caption: str, tooltip: str = ""):
        super().__init__()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.value = label("–", "stat", wrap=True)
        self.caption = label(caption, "caption")
        self.caption.setStyleSheet("font-size: 12px; font-weight: 700;")
        col.addWidget(self.value)
        col.addWidget(self.caption)
        self.setToolTip(star_subscript(tooltip))  # rich text: x★ with a subscript star

    def set(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class RunInfoCard(QWidget):
    """Not a card of its own: a section of the OCP tile (no boxes in boxes).

    Whole-run numbers (decided 2026-11-18): title "Whole run" with "n solves · t = run time"
    next to it, then total cost, average solve time, average SQP iterations, solved count.
    The "‹ k /n ›" stepper only moves the map; no per-solve numbers are shown here."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._result: RunResult | None = None
        self._hidden = False  # see set_hidden() (Level 0 until its run has been watched)
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(label("Whole run", "subheading"))
        top.addStretch(1)
        self.run_title = math_text("", "caption", wrap=False, bold=True)
        top.addWidget(self.run_title)
        body.addLayout(top)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        self.cost = _Stat("total cost", "Total cost (closed loop): Σ Δt·(‖x_k − x★‖²_Q + ‖u_k‖²_R) "
                          "over what actually happened in the whole run, with this level's weights. "
                          "Compare it only between runs with the same weights. (Not the plan cost J* "
                          "of one solve, which is a prediction over N steps plus the terminal cost.)")
        self.time = _Stat("avg solve time", "Average acados time per MPC solve")
        self.iter = _Stat("avg SQP iterations", "Average SQP iterations per solve. Without obstacles "
                          "the OCP is a QP and SQP needs 1; obstacle ellipses make it nonlinear.")
        self.status = _Stat("solved · acados status", "How many solves acados finished with status 0 "
                            "(solved). Any other status means the solver found no valid plan.")
        for i, stat in enumerate((self.cost, self.time, self.iter, self.status)):
            grid.addWidget(stat, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        body.addLayout(grid)

        self.note = label("Press Run to see the numbers.", "caption", wrap=True)
        self.note.setStyleSheet("font-weight: 700;")
        body.addWidget(self.note)

    def set_hidden(self, hidden: bool) -> None:
        """Keep every number at "–" (Level 0: until its run has been watched to the end)."""
        self._hidden = hidden
        self._show()

    def set_result(self, result: RunResult | None) -> None:
        self._result = result
        self._show()

    def _show(self) -> None:
        stats = (self.cost, self.time, self.iter, self.status)
        for stat in stats:
            stat.set("–")
        self.status.caption.setText("solved · acados status")
        self.run_title.setText("")
        self.note.hide()
        r = self._result
        if r is None:
            self.note.setText("Press Run to see the numbers.")
            self.note.setVisible(not self._hidden)
            return
        if self._hidden:
            return
        m, tr = r.metrics, r.trajectory
        self.run_title.setText(f"{tr.n_solves} solves · $t = {tr.duration:.1f}$ s")
        needed = ("closed_loop_cost", "mean_solve_ms", "mean_iterations", "max_solve_ms",
                  "total_solve_ms", "max_iterations")
        if not all(k in m for k in needed) or not tr.status:
            # an engine running older code does not send these values: "–", never fake zeros
            self.note.setText("Some values are missing: the MPC engine runs older code. "
                              "Restart it (Ctrl+C, then start_engine) and run again.")
            self.note.show()
            return
        self.cost.set(_sci(m["closed_loop_cost"]))
        self.time.set(f"{m['mean_solve_ms']:.2f} ms")
        self.time.setToolTip(f"Average acados time per MPC solve: {m['mean_solve_ms']:.2f} ms "
                             f"(max {m['max_solve_ms']:.2f} ms, {m['total_solve_ms']:.0f} ms in total)"
                             + (f"\nEngine time for the whole run: {m['compute_time_s']:.2f} s"
                                if "compute_time_s" in m else ""))
        self.iter.set(f"{m['mean_iterations']:.1f}")
        self.iter.setToolTip(f"Average SQP iterations per solve: {m['mean_iterations']:.2f} "
                             f"(max {m['max_iterations']}). Without obstacles the OCP is a QP and "
                             "SQP needs 1; obstacle ellipses make it nonlinear.")
        n, ok = len(tr.status), sum(1 for s in tr.status if s == 0)
        self.status.set(f"{ok} / {n}", theme.SUCCESS_INK if ok == n else theme.DANGER)
        failed = [(k, s) for k, s in enumerate(tr.status) if s != 0]
        self.status.setToolTip(
            "How many solves acados finished with status 0 (solved)."
            + "".join(f"\nSolve {k + 1}: status {s} ({ACADOS_STATUS.get(s, 'unknown')})"
                      for k, s in failed[:5]))
