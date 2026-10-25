"""The "Your OCP" card (PRD 5.5): the optimal control problem the MPC solves at
every step, typeset as math.

A level describes its OCP as an OcpSpec (LaTeX lines, see ui/math_render.py):

    OcpSpec(objective=[r"\\min_{u} ...", r"\\ell(x,u) = ..."],
            constraints=[r"x_0 = \\hat{x}", r"x_{k+1} = f(x_k, u_k)", ...],
            notes="every 0.1 s, from the measured state")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget

from ..ui.math_render import MathLabel
from ..ui.widgets import Card, label


@dataclass
class OcpSpec:
    objective: list[str]  # first line: the minimisation; more lines: definitions (e.g. stage cost)
    constraints: list[str]  # one constraint (group) per line, shown after "s.t."
    legend: list[str] = field(default_factory=list)  # short plain-text explanations of symbols
    notes: str = ""  # caption under the title


class OcpCard(Card):
    def __init__(self, spec: OcpSpec, title: str = "The OCP your MPC solves",
                 parent: QWidget | None = None):
        super().__init__(parent, padding=18, spacing=8, shadow=False)
        self.body.addWidget(label(title, "subheading"))
        if spec.notes:
            self.body.addWidget(label(spec.notes, "caption", wrap=True))

        grid = QGridLayout()
        grid.setContentsMargins(0, 6, 0, 2)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        row = 0
        for tex in spec.objective:
            grid.addWidget(MathLabel(tex, size_px=15), row, 0, 1, 2)
            row += 1
        for i, tex in enumerate(spec.constraints):
            if i == 0:
                grid.addWidget(MathLabel(r"\mathrm{s.t.}", size_px=15), row, 0,
                               Qt.AlignmentFlag.AlignTop)
            grid.addWidget(MathLabel(tex, size_px=15), row, 1)
            row += 1
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)

        for text in spec.legend:
            self.body.addWidget(label(text, "caption", wrap=True))
