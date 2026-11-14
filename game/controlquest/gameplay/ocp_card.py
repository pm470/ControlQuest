"""The "OCP your MPC solves" section (PRD 5.5): the optimal control problem the MPC
solves at every step, typeset as math. It is the top part of the middle tile (the
solver info sits under it in the same tile).

A level describes its OCP as an OcpSpec (LaTeX lines, see ui/math_render.py):

    OcpSpec(objective=[r"\\min_{u} ...", r"\\ell(x,u) = \\knob{q_p}{q_p}\\,\\|p-p_\\star\\|^2 ..."],
            constraints=[r"x_0 = \\hat{x}", r"x_{k+1} = f(x_k, u_k)", ...],
            notes="every 0.1 s, from the measured state")

Mark what a knob changes with \\knob{knob name}{tex}: it is drawn in the knob's colour,
the same colour as the knob's slider and symbol chip.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from ..ui.math_render import MathLabel
from ..ui.widgets import label


@dataclass
class OcpSpec:
    objective: list[str]  # first line: the minimisation; more lines: definitions (e.g. stage cost)
    constraints: list[str]  # one constraint (group) per line, shown after "s.t."
    legend: list[str] = field(default_factory=list)  # short plain-text explanations of symbols
    notes: str = ""  # caption under the title


class OcpCard(QWidget):
    def __init__(self, spec: OcpSpec, title: str = "The OCP your MPC solves",
                 knob_colors: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._knob_colors = knob_colors or {}
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        self.body.addWidget(label(title, "subheading"))
        self._content = QWidget()
        self.body.addWidget(self._content)
        self.set_spec(spec)

    def set_spec(self, spec: OcpSpec) -> None:
        """Show another OCP (e.g. after the player picked a different fix)."""
        old = self._content
        self._content = QWidget()
        box = QVBoxLayout(self._content)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self.body.replaceWidget(old, self._content)
        old.hide()  # hide and detach now: deleteLater only runs in the event loop
        old.setParent(None)
        old.deleteLater()
        if spec.notes:
            box.addWidget(label(spec.notes, "caption", wrap=True))

        kc = self._knob_colors
        grid = QGridLayout()
        grid.setContentsMargins(0, 6, 0, 2)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        row = 0
        for tex in spec.objective:
            grid.addWidget(MathLabel(tex, size_px=15, knob_colors=kc), row, 0, 1, 2)
            row += 1
        for i, tex in enumerate(spec.constraints):
            if i == 0:
                grid.addWidget(MathLabel(r"\mathrm{s.t.}", size_px=15), row, 0,
                               Qt.AlignmentFlag.AlignTop)
            grid.addWidget(MathLabel(tex, size_px=15, knob_colors=kc), row, 1)
            row += 1
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        for text in spec.legend:
            box.addWidget(label(text, "caption", wrap=True))
        self._content.adjustSize()  # re-layout now (formula sizes changed), not on the next resize
        self.body.activate()
        self.updateGeometry()
