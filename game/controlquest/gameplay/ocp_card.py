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
  draws it as a minus sign). The legend keeps the caption size and wraps between words
  (every word is its own formula, legend_text), indented under the words (2026-11-22).

Sizes (type scale, 2026-11-22): all formula lines of one OCP share one size
(ui/math_render.FitGroup): the largest that fits the column. Keep lines short enough
for a ~280 px wide constraint column at FS_MATH: break a long one into a continuation line
starting with \\quad (e.g. "x_{k+1} = f(x_k, u_k)" and "\\quad (no wind in the model)").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from ..ui import theme
from ..ui.math_render import FitGroup, MathLabel
from ..ui.math_text import MATH, inline_image, math_text
from ..ui.widgets import label

# the symbols every OCP uses (legend entries)
STATE_LEGEND = [(r"x = (p,\, v)", "position, velocity"), (r"u = a", "acceleration"),
                (r"p_{\star}", "target position")]


@dataclass
class OcpSpec:
    objective: list[str]  # first line: the minimisation; more lines: definitions (e.g. stage cost)
    constraints: list[str]  # one constraint (group) per line, shown after "s.t."
    # symbol explanations: (symbol tex, words) lines in the LaTeX font, or plain-text remarks
    legend: list = field(default_factory=list)
    notes: str = ""  # caption under the title ($...$ for symbols)


def legend_text(symbol: str, words: str) -> str:
    """("x = (p, v)", "position, velocity") -> text for a wrapping MathText in which every word
    is its own $...$ formula: "$x = (p, v):\\ $ $\\mathrm{position,}$ $\\mathrm{velocity}$".
    So the whole entry is in the LaTeX font (words upright) at one fixed size, and a long entry
    wraps between words instead of shrinking (the user, 2026-11-22). $...$ parts inside the
    words stay math."""
    out = []
    for i, part in enumerate(MATH.split(words)):
        if i % 2:
            out.append(f"${part}$")
            continue
        for token in re.split(r"( +)", part):
            if not token:
                continue
            if token.isspace():
                out.append(" ")
            else:
                safe = token.replace("{", "").replace("}", "").replace("%", "\\%")
                out.append("$\\mathrm{" + safe + "}$")
    return f"${symbol}:\\ $ " + "".join(out)


def _symbol_width(symbol: str) -> float:
    """Width (logical px) of an entry's "symbol: " at the caption size: the hanging indent."""
    got = inline_image(f"{symbol}:\\ ", theme.FS_SMALL * theme.MATH_SCALE, theme.MUTED, 1.0)
    space = QFontMetricsF(theme.font(theme.FS_SMALL)).horizontalAdvance(" ")
    return (got[0].width() if got else 0.0) + space


def legend_entries(legend: list) -> list:
    """The legend with every ("", words) continuation merged into the entry before it (a legend
    line wraps by itself now)."""
    out: list = []
    for entry in legend:
        if isinstance(entry, tuple) and not entry[0] and out and isinstance(out[-1], tuple):
            out[-1] = (out[-1][0], out[-1][1] + " " + entry[1])
        else:
            out.append(entry)
    return out


CONTINUATION = "\\quad "  # a constraint line that starts with this continues the line before


def joined(spec: OcpSpec) -> OcpSpec:
    """The spec with its continuation lines put back on the line before them (wide tiles)."""
    constraints: list[str] = []
    for tex in spec.constraints:
        if tex.startswith(CONTINUATION) and constraints:
            constraints[-1] = constraints[-1] + "\\quad " + tex[len(CONTINUATION):]
        else:
            constraints.append(tex)
    legend: list = []
    for entry in legend_entries(spec.legend):
        if entry in STATE_LEGEND and legend and isinstance(legend[-1], list):
            legend[-1].append(entry)  # the standard symbols share one line in a wide tile
        elif entry in STATE_LEGEND:
            legend.append([entry])
        else:
            legend.append(entry)
    return replace(spec, constraints=constraints, legend=legend)


class OcpCard(QWidget):
    def __init__(self, spec: OcpSpec, title: str | None = "The OCP your MPC solves",
                 knob_colors: dict | None = None, parent: QWidget | None = None,
                 join: bool = False):
        """join=True: a wide tile (the level intro) shows continuation lines (r"\\quad ..."
        constraints, ("", words) legend entries) on the line before them again."""
        super().__init__(parent)
        self._knob_colors = knob_colors or {}
        self._join = join
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
        if self._join:
            spec = joined(spec)
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
        lines = FitGroup(self._content)  # all formula lines at one size (the largest that fits)
        grid = QGridLayout()
        grid.setContentsMargins(0, 6, 0, 2)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)  # the formula images carry their own padding (math_render.PAD_PX)
        row = 0
        for tex in spec.objective:
            grid.addWidget(lines.add(MathLabel(tex, size_px=theme.FS_MATH, knob_colors=kc)), row, 0, 1, 2)
            row += 1
        for i, tex in enumerate(spec.constraints):
            if i == 0:
                grid.addWidget(lines.add(MathLabel(r"\mathrm{s.t.}", size_px=theme.FS_MATH)), row, 0,
                               Qt.AlignmentFlag.AlignTop)
            grid.addWidget(lines.add(MathLabel(tex, size_px=theme.FS_MATH, knob_colors=kc)), row, 1)
            row += 1
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        # the legend: fixed size (caption), every word in the LaTeX font, long entries wrap
        legend = QVBoxLayout()
        legend.setSpacing(2)
        for entry in legend_entries(spec.legend):
            if isinstance(entry, list):  # several entries in one paragraph (joined(), wide tiles)
                text = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(legend_text(*e) for e in entry)  # nbsp: no collapse
            elif isinstance(entry, tuple):
                # a wrapped line continues under the words, not under the symbol
                indent = _symbol_width(entry[0])
                text = (f'<div style="margin-left: {indent:.0f}px; text-indent: -{indent:.0f}px">'
                        f"{legend_text(*entry)}</div>")
            else:
                text = entry  # a remark in the game font ($...$ allowed)
            legend.addWidget(math_text(text, "caption"))
        box.addLayout(legend)
        self._content.adjustSize()  # re-layout now (formula sizes changed), not on the next resize
        self.body.activate()
        self.updateGeometry()
