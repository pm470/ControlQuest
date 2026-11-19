"""The "OCP your MPC solves" section (PRD 5.5): the optimal control problem the MPC
solves at every step, typeset as math. It is the top part of the middle tile (the
solver info sits under it in the same tile).

A level describes its OCP as an OcpSpec (LaTeX lines, see ui/math_render.py):

    OcpSpec(objective=[r"\\min_{u} ...", r"\\ell(x,u) = \\knob{q_p}{q_p}\\,\\|p-p_\\star\\|^2 ..."],
            constraints=[r"x_0 = \\hat{x}", r"x_{k+1} = f(x_k, u_k)", ...],
            notes=r"Re-solved every $\\Delta t = 0.1$ s",
            legend=[(r"x = (p, v)", "position, velocity"), (r"p_\\star", "target")])

Mark what a knob changes with \\knob{knob name}{tex}: it is drawn in the knob's colour,
the same colour as the knob's slider and symbol chip.

Everything math-like is in the LaTeX font (2026-11-19):
- notes: a caption in the game font; write symbols as $...$ (ui/math_text.py).
- legend: one entry per line. A tuple (symbol tex, words) is typeset entirely in the LaTeX
  font, "symbol:  words" with the words upright; the words may contain $...$ too. A plain
  string is a remark in the game font ($...$ allowed). Avoid "-" in legend words (mathtext
  draws it as a minus sign).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from ..ui import theme
from ..ui.math_render import MathLabel
from ..ui.math_text import MATH, math_text
from ..ui.widgets import label

LEGEND_SIZE_PX = 13.5
# the symbols every OCP uses (legend entries)
STATE_LEGEND = [(r"x = (p,\, v)", "position, velocity"), (r"u = a", "acceleration"),
                (r"p_{\star}", "target")]


@dataclass
class OcpSpec:
    objective: list[str]  # first line: the minimisation; more lines: definitions (e.g. stage cost)
    constraints: list[str]  # one constraint (group) per line, shown after "s.t."
    # symbol explanations: (symbol tex, words) lines in the LaTeX font, or plain-text remarks
    legend: list = field(default_factory=list)
    notes: str = ""  # caption under the title ($...$ for symbols)


def legend_tex(symbol: str, words: str) -> str:
    """("x = (p, v)", "position, velocity") -> one mathtext line "x = (p, v):  position, velocity"
    with the words upright (mathrm); $...$ parts inside the words stay math."""
    out = []
    for i, part in enumerate(MATH.split(words)):
        if i % 2:
            out.append(part)
        elif part:
            safe = part.replace("{", "").replace("}", "").replace("%", "\\%")
            out.append("\\mathrm{" + safe.replace(" ", "\\ ") + "}")
    return symbol + ":\\ \\ " + "".join(out)


class OcpCard(QWidget):
    def __init__(self, spec: OcpSpec, title: str | None = "The OCP your MPC solves",
                 knob_colors: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._knob_colors = knob_colors or {}
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        if title:  # None: the caller shows its own title (e.g. the level intro's eyebrow)
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
            box.addWidget(math_text(spec.notes, "caption"))

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

        legend = QVBoxLayout()
        legend.setSpacing(2)
        for entry in spec.legend:  # symbols in the LaTeX font, one per line
            if isinstance(entry, tuple):
                legend.addWidget(MathLabel(legend_tex(*entry), size_px=LEGEND_SIZE_PX,
                                           color=theme.MUTED))
            else:
                legend.addWidget(math_text(entry, "caption"))
        box.addLayout(legend)
        self._content.adjustSize()  # re-layout now (formula sizes changed), not on the next resize
        self.body.activate()
        self.updateGeometry()
