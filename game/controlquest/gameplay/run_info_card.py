"""Solver info, under the OCP in the same tile: four big numbers for the MPC solve
shown on the map (plan cost J*, solve time, SQP iterations, status) and one line for
the whole run (solves, average solve time, total cost). Details are in the tooltips.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ..engine.protocol import RunResult
from ..ui import theme
from ..ui.widgets import label

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
        self.setToolTip(tooltip)

    def set(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class RunInfoCard(QWidget):
    """Not a card of its own: a section of the OCP tile (no boxes in boxes)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._result: RunResult | None = None
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(label("This solve", "subheading"))
        top.addStretch(1)
        self.solve_title = label("", "caption")
        self.solve_title.setStyleSheet("font-weight: 700;")
        top.addWidget(self.solve_title)
        body.addLayout(top)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        self.cost = _Stat("plan cost J*", "Optimal value of THIS solve's OCP: the predicted cost of "
                          "its plan over the next N steps plus the terminal cost (not the cost of "
                          "the whole run)")
        self.time = _Stat("solve time", "acados time for this solve")
        self.iter = _Stat("SQP iterations", "SQP iterations acados needed for this solve")
        self.status = _Stat("acados status", "acados return code: 0 = solved; anything else means "
                            "the solver found no valid plan (the run then ends as a controller failure)")
        for i, stat in enumerate((self.cost, self.time, self.iter, self.status)):
            grid.addWidget(stat, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        body.addLayout(grid)

        self.run_line = label("Press Run to see the numbers.", "caption", wrap=True)
        self.run_line.setStyleSheet("font-weight: 700;")
        body.addWidget(self.run_line)

    def set_result(self, result: RunResult | None) -> None:
        self._result = result
        for stat in (self.cost, self.time, self.iter, self.status):
            stat.set("–")
        self.solve_title.setText("")
        if result is None:
            self.run_line.setText("Press Run to see the numbers.")
            return
        m = result.metrics
        needed = ("solves", "max_solve_ms", "total_solve_ms", "mean_iterations", "closed_loop_cost")
        if not (all(k in m for k in needed) and result.trajectory.costs):
            # an engine running older code does not send these values
            self.run_line.setText("Some values are missing: the MPC engine runs older code. "
                                  "Restart it (Ctrl+C, then start_engine) and run again.")
            self.run_line.setToolTip("")
        else:
            parts = [f"{m['solves']} solves", f"{m['mean_solve_ms']:.2f} ms avg",
                     f"total cost {_sci(m['closed_loop_cost'])}"]
            self.run_line.setText("Whole run: " + " · ".join(parts))
            self.run_line.setToolTip(
                f"Solve time: {m['mean_solve_ms']:.2f} ms avg, {m['max_solve_ms']:.2f} ms max, "
                f"{m['total_solve_ms']:.0f} ms in total\n"
                f"SQP iterations: {m['mean_iterations']:.1f} avg, {m['max_iterations']} max\n"
                "Total cost (closed loop): Σ Δt·(‖x_k − x★‖²_Q + ‖u_k‖²_R) over what actually happened, "
                "with your weights (compare it only between runs with the same weights)"
                + (f"\nEngine time for the whole run: {m['compute_time_s']:.2f} s"
                   if "compute_time_s" in m else ""))
        self.set_solve(0)

    def set_solve(self, k: int) -> None:
        tr = self._result.trajectory if self._result is not None else None
        if tr is None or not tr.n_solves:
            return
        k = max(0, min(k, tr.n_solves - 1))
        self.solve_title.setText(f"{k + 1} of {tr.n_solves} · t = {tr.time_of_solve(k):.1f} s")
        cost = tr.costs[k] if k < len(tr.costs) else None
        self.cost.set("–" if cost is None else _sci(cost))
        if k < len(tr.solve_time_ms):
            self.time.set(f"{tr.solve_time_ms[k]:.2f} ms")
        if k < len(tr.iterations):
            self.iter.set(f"{tr.iterations[k]}")
        if k < len(tr.status):
            s = tr.status[k]
            self.status.set(ACADOS_STATUS.get(s, "unknown"), theme.SUCCESS_INK if s == 0 else theme.DANGER)
            self.status.caption.setText(f"acados status {s}")
