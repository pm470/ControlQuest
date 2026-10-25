"""The "Solver info" card: numbers about the MPC solve shown on the map and about
the whole run (cost, solve times, SQP iterations, ...). Lives under the OCP card.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ..engine.protocol import RunResult
from ..ui import theme
from ..ui.widgets import Card, divider, label

ACADOS_STATUS = {0: "solved", 1: "NaN detected", 2: "max. iterations", 3: "min. step size",
                 4: "QP failure", 5: "ready"}
_BOLD = f"font-weight: 700; color: {theme.INK};"


def _bold(text: str, wrap: bool = False) -> QLabel:
    lab = label(text, "caption", wrap=wrap)
    lab.setStyleSheet(_BOLD)
    return lab


class _Rows:
    """A compact 'name  value' grid whose values can be updated."""

    def __init__(self, parent_layout, names: list[tuple[str, str]]):
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        self.values: dict[str, QLabel] = {}
        for i, (key, name) in enumerate(names):
            grid.addWidget(label(name, "caption", wrap=True), i, 0)
            self.values[key] = _bold("–", wrap=True)  # may wrap: never wider than the card
            grid.addWidget(self.values[key], i, 1)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        parent_layout.addLayout(grid)

    def set(self, key: str, text: str, tooltip: str = "") -> None:
        self.values[key].setText(text)
        self.values[key].setToolTip(tooltip)

    def clear(self) -> None:
        for v in self.values.values():
            v.setText("–")


class RunInfoCard(Card):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, padding=16, spacing=4, shadow=False)
        self._result: RunResult | None = None
        self.body.addWidget(label("Solver info", "subheading"))

        self.solve_title = _bold("This solve")
        self.body.addWidget(self.solve_title)
        self.solve = _Rows(self.body, [
            ("cost", "Plan cost J*"),
            ("time", "Solve time"),
            ("iter", "SQP iterations"),
            ("status", "Status"),
        ])
        self.body.addWidget(divider())
        self.body.addWidget(_bold("Whole run"))
        self.run = _Rows(self.body, [
            ("solves", "MPC solves"),
            ("time", "Solve time"),
            ("total", "Total solve time"),
            ("iter", "SQP iterations"),
            ("cost", "Total cost"),
            ("compute", "Engine time"),
        ])
        self.hint = label("Press Run to see the numbers.", "caption", wrap=True)
        self.body.addWidget(self.hint)

    def set_result(self, result: RunResult | None) -> None:
        self._result = result
        self.solve.clear()
        self.run.clear()
        if result is None:
            self.hint.show()
            return
        m = result.metrics
        needed = ("solves", "max_solve_ms", "total_solve_ms", "mean_iterations", "closed_loop_cost")
        if all(k in m for k in needed) and result.trajectory.costs:
            self.hint.hide()
        else:  # an engine running older code does not send these values
            self.hint.setText("Some values are missing: the MPC engine runs older code. "
                              "Restart it (Ctrl+C, then start_engine) and run again.")
            self.hint.show()

        def fmt(key: str, pattern: str) -> str:
            return pattern.format(m[key]) if key in m else "–"

        self.run.set("solves", str(m.get("solves", result.trajectory.n_solves)),
                     "One OCP is solved every Δt; this many until the run ended")
        if "max_solve_ms" in m:
            self.run.set("time", f"{m['mean_solve_ms']:.2f} avg · {m['max_solve_ms']:.2f} max [ms]",
                         "acados time per solve: average and slowest")
            self.run.set("total", f"{m['total_solve_ms']:.0f} ms", "All solve times added up")
        if "mean_iterations" in m:
            self.run.set("iter", f"{m['mean_iterations']:.1f} avg · {m['max_iterations']} max",
                         "SQP iterations per solve over the run")
        self.run.set("cost", fmt("closed_loop_cost", "{:.4g}"),
                     "Closed-loop cost: Σ Δt·(‖x_k − x★‖²_Q + ‖u_k‖²_R) over what actually happened, with your "
                     "weights (compare it only between runs with the same weights)")
        self.run.set("compute", fmt("compute_time_s", "{:.2f} s"),
                     "Wall-clock time the engine needed for the whole run (all solves + simulation)")
        self.set_solve(0)

    def set_solve(self, k: int) -> None:
        tr = self._result.trajectory if self._result is not None else None
        if tr is None or not tr.n_solves:
            return
        k = max(0, min(k, tr.n_solves - 1))
        self.solve_title.setText(f"Solve {k + 1} of {tr.n_solves}  (t = {tr.time_of_solve(k):.1f} s)")
        cost = tr.costs[k] if k < len(tr.costs) else None
        self.solve.set("cost", "–" if cost is None else f"{cost:.4g}",
                       "Optimal value of THIS solve's OCP: the predicted cost of its plan over "
                       "the next N steps plus the terminal cost (not the cost of the whole run)")
        if k < len(tr.solve_time_ms):
            self.solve.set("time", f"{tr.solve_time_ms[k]:.3f} ms")
        if k < len(tr.iterations):
            self.solve.set("iter", f"{tr.iterations[k]}")
        if k < len(tr.status):
            s = tr.status[k]
            self.solve.set("status", f"{ACADOS_STATUS.get(s, 'unknown')} ({s})",
                           "acados return code: 0 = solved; anything else means the solver "
                           "found no valid plan (the run then ends as a controller failure)")
