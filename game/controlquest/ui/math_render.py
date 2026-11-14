"""LaTeX-style math in Qt widgets, rendered with matplotlib's mathtext
(no LaTeX installation needed; Computer Modern font, like a textbook).

    lab = MathLabel(r"\\min_{u}\\ \\sum_{k=0}^{N-1} \\ell(x_k, u_k)", size_px=15)

Supported syntax: matplotlib mathtext (a large LaTeX subset: sub/superscripts,
\\sum, \\min, \\|x\\|, \\hat{x}, \\mathrm{...}, \\quad, Greek letters, ...).
No environments (aligned, cases): build multi-line math from several MathLabels.

Knob colours: write \\knob{name}{tex} around the part of a line that a knob changes,
e.g. r"\\ell = \\knob{q_p}{q_p}\\,\\|p\\|^2". With knob_colors={"q_p": KnobColor(...)}
that part is drawn in the knob's colour on a tinted chip (same colour as its slider);
without colours it is drawn like the rest. Only at the top level of a line (not
inside {...}, e.g. not in a subscript).
"""

from __future__ import annotations

import io
import math

from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme

_cache: dict[tuple, QPixmap] = {}
_mathtext = None  # lazily imported matplotlib.mathtext (slow import)
PAD_PX = 3  # transparent margin around each formula (logical px)
KNOB = "\\knob{"
SEGMENT_GAP_EM = 0.12  # space between a coloured chip and its neighbours
CHIP_PAD_EM = 0.12  # extra room for the chip's rounded background


def split_knobs(tex: str) -> list[tuple[str, str | None]]:
    """'a \\knob{q}{b} c' -> [('a', None), ('b', 'q'), ('c', None)] (empty parts dropped)."""
    parts: list[tuple[str, str | None]] = []
    i = 0
    while True:
        j = tex.find(KNOB, i)
        if j < 0:
            break
        name_end = tex.find("}", j + len(KNOB))
        if name_end < 0 or name_end + 1 >= len(tex) or tex[name_end + 1] != "{":
            break  # malformed: render the rest as it is
        depth, k = 0, name_end + 1
        while k < len(tex):
            depth += {"{": 1, "}": -1}.get(tex[k], 0)
            if depth == 0:
                break
            k += 1
        parts.append((tex[i:j], None))
        parts.append((tex[name_end + 2:k], tex[j + len(KNOB):name_end]))
        i = k + 1
    parts.append((tex[i:], None))

    def clean(t: str) -> str:  # trim, but keep an escaped space ("\ ") at the end intact
        s = t.strip()
        return s + " " if s.endswith("\\") and not s.endswith("\\\\") else s

    return [(clean(t), n) for t, n in parts if t.strip()]


def plain_tex(tex: str) -> str:
    """The line without knob markup (e.g. for tooltips or a text fallback)."""
    return " ".join(t for t, _n in split_knobs(tex))


def _backend():
    global _mathtext
    if _mathtext is None:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import mathtext, rcParams

        rcParams["mathtext.fontset"] = "cm"
        _mathtext = mathtext
    return _mathtext


def render_tex(tex: str, size_px: float = 15, color: str = theme.INK, dpr: float = 1.0,
               knob_colors: dict | None = None) -> QPixmap | None:
    """Render one line of math (without $...$) to a transparent QPixmap; None if impossible.
    knob_colors: {knob name: theme.KnobColor} for the \\knob{name}{...} parts."""
    parts = split_knobs(tex) if KNOB in tex else [(tex, None)]
    colors = knob_colors or {}
    used = tuple(sorted((n, colors[n]) for _t, n in parts if n in colors))
    key = (tex, round(size_px, 1), color, round(dpr, 2), used)
    if key in _cache:
        return _cache[key]
    try:
        _backend()
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        # at dpi = 72 * dpr, 1 pt = 1 logical pixel. A tight bounding box *with padding*:
        # math_to_image crops exactly at the glyphs, which cut off tops of digits after
        # rounding at high display scaling.
        dpi = 72 * dpr
        fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
        canvas = FigureCanvasAgg(fig)
        if len(parts) == 1 and parts[0][1] not in colors:
            fig.text(0, 0, f"${parts[0][0]}$", fontsize=size_px, color=color)
        else:
            # one text per part, side by side on the same baseline; coloured parts on a chip.
            # Positions in figure fractions (transFigure), which follow the tight bbox crop.
            renderer = canvas.get_renderer()
            em = size_px * dpr
            x = 0.0
            for i, (part, name) in enumerate(parts):
                kc = colors.get(name)
                pad = CHIP_PAD_EM * em if kc else 0.0
                x += (SEGMENT_GAP_EM * em if i else 0.0) + pad
                t = fig.text(x / fig.bbox.width, 0, f"${part}$", fontsize=size_px,
                             color=kc.ink if kc else color, va="baseline", ha="left")
                if kc:
                    t.set_bbox(dict(boxstyle="round,pad=0.1,rounding_size=0.3", fc=kc.tint, ec="none"))
                x = t.get_window_extent(renderer).x1 + pad
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, transparent=True,
                    bbox_inches="tight", pad_inches=PAD_PX / 72)
    except Exception as exc:  # matplotlib missing or invalid math: caller shows plain text
        print(f"[math] could not render {tex!r}: {exc}")
        return None
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    pm.setDevicePixelRatio(dpr)
    _cache[key] = pm
    return pm


class MathLabel(QWidget):
    """One line of math, drawn pixel-exact.

    Two details keep it sharp on displays with fractional scaling (e.g. 175%):
    - the image is drawn snapped to whole *device* pixels (otherwise Qt resamples it
      and some lines look blurry, depending on where they happen to sit);
    - a line that is too wide is re-rendered at a smaller font size, never shrunk as
      an image.
    """

    MIN_SIZE_PX = 9.0

    def __init__(self, tex: str = "", size_px: float = 15, color: str = theme.INK,
                 parent: QWidget | None = None, knob_colors: dict | None = None):
        super().__init__(parent)
        self._tex, self._size, self._color = tex, size_px, color
        self._knob_colors = knob_colors
        self._fit_size = size_px  # font size actually used (<= size_px)
        self._natural: QPixmap | None = None  # rendered at size_px
        self._pixmap: QPixmap | None = None  # rendered at _fit_size
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_tex(tex)

    # --- content ---------------------------------------------------------------------------
    def set_tex(self, tex: str) -> None:
        self._tex = tex
        self._fit_size = self._size
        self._render()
        if self._natural is None and tex:
            self.setToolTip("Install matplotlib to see the formula (pip install -r requirements.txt)")
        self.setFixedHeight(self._natural_size().height())
        self.updateGeometry()
        self.update()

    def _render(self) -> None:
        dpr = self.devicePixelRatioF()
        self._dpr = dpr
        kc = self._knob_colors
        self._natural = render_tex(self._tex, self._size, self._color, dpr, kc) if self._tex else None
        self._pixmap = (self._natural if self._fit_size == self._size or self._natural is None
                        else render_tex(self._tex, self._fit_size, self._color, dpr, kc))

    def _natural_size(self) -> QSize:
        if self._natural is None:
            text = plain_tex(self._tex)
            return QSize(self.fontMetrics().horizontalAdvance(text) + 4, self.fontMetrics().height() + 4)
        return self._natural.deviceIndependentSize().toSize()

    # --- layout --------------------------------------------------------------------------
    def sizeHint(self) -> QSize:
        return self._natural_size()

    def minimumSizeHint(self) -> QSize:
        return QSize(40, self._natural_size().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        """Choose the largest font size (<= size_px) at which the line fits the width."""
        if self._natural is None or self.width() <= 0:
            return
        nat_w = self._natural.deviceIndependentSize().width()
        size = self._size
        if nat_w > self.width():
            size = max(self.MIN_SIZE_PX, math.floor(2 * self._size * self.width() / nat_w) / 2)
        if size != self._fit_size:
            self._fit_size = size
            self._render()
            self.update()

    # --- painting ------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        if abs(self.devicePixelRatioF() - getattr(self, "_dpr", 1.0)) > 1e-6:
            self._render()  # moved to a screen with another scaling
        pm = self._pixmap
        if pm is None:
            p.setPen(QColor(self._color))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       plain_tex(self._tex))
            return
        size = pm.deviceIndependentSize()
        x, y = 0.0, (self.height() - size.height()) / 2
        # snap the top-left corner to a whole device pixel of the window's backing store
        dpr = self.devicePixelRatioF()
        origin = self.mapTo(self.window(), QPoint(0, 0))
        gx, gy = (origin.x() + x) * dpr, (origin.y() + y) * dpr
        x += (round(gx) - gx) / dpr
        y += (round(gy) - gy) / dpr
        p.drawPixmap(QPointF(x, y), pm)


class MathChip(QWidget):
    """A knob's symbol (math) on a tinted rounded chip, in the knob's colour. The same
    colours mark the knob's part of the OCP (knob markup), so the two are easy to match."""

    PAD_X, PAD_Y, RADIUS = 6, 2, 8

    def __init__(self, tex: str, knob_color, size_px: float = 16, parent: QWidget | None = None):
        super().__init__(parent)
        self._tex, self._kc, self._size = tex, knob_color, size_px
        self._pm: QPixmap | None = None
        self._dpr = 0.0
        self._render()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _render(self) -> None:
        self._dpr = self.devicePixelRatioF()
        self._pm = render_tex(self._tex, self._size, self._kc.ink, self._dpr)
        if self._pm is not None:
            s = self._pm.deviceIndependentSize()
            self.setFixedSize(round(s.width()) + 2 * self.PAD_X, round(s.height()) + 2 * self.PAD_Y)
        else:
            fm = self.fontMetrics()
            self.setFixedSize(fm.horizontalAdvance(self._tex) + 2 * self.PAD_X, fm.height() + 2 * self.PAD_Y)

    def paintEvent(self, _event) -> None:
        if abs(self.devicePixelRatioF() - self._dpr) > 1e-6:
            self._render()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._kc.tint))
        p.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)
        if self._pm is None:
            p.setPen(QColor(self._kc.ink))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._tex)
            return
        size = self._pm.deviceIndependentSize()
        x, y = (self.width() - size.width()) / 2, (self.height() - size.height()) / 2
        dpr = self.devicePixelRatioF()  # snap to device pixels (sharp at 175%)
        origin = self.mapTo(self.window(), QPoint(0, 0))
        gx, gy = (origin.x() + x) * dpr, (origin.y() + y) * dpr
        p.drawPixmap(QPointF(x + (round(gx) - gx) / dpr, y + (round(gy) - gy) / dpr), self._pm)
