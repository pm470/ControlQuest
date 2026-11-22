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

New parts (level intros): \\new{tex} draws the part on a soft yellow highlight
(theme.NEW_GLOW); \\newknob{name}{tex} is a knob part that is also new (knob chip on
the highlight). Same rule: top level of a line only.
"""

from __future__ import annotations

import io
import math

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme

# Events after which the display scaling (device pixel ratio) may have changed, e.g. the
# window moved to a monitor with other Windows scaling (175% laptop -> 125% monitor).
_DPR_EVENTS = {t for t in (getattr(QEvent.Type, "DevicePixelRatioChange", None),
                           getattr(QEvent.Type, "ScreenChangeInternal", None),
                           QEvent.Type.Show) if t is not None}

_cache: dict[tuple, QPixmap] = {}
_mathtext = None  # lazily imported matplotlib.mathtext (slow import)
PAD_PX = 3  # transparent margin around each formula (logical px)
KNOB = "\\knob{"
NEW = "\\new{"
NEWKNOB = "\\newknob{"
MARKS = (KNOB, NEW, NEWKNOB)
SEGMENT_GAP_EM = 0.12  # space between a coloured chip and its neighbours
CHIP_PAD_EM = 0.12  # extra room for the chip's rounded background
GLOW_PAD_EM = 0.3  # extra room for the soft highlight behind a new part


def _group(tex: str, start: int) -> int:
    """Index of the '}' that closes the brace group opening at tex[start] ('{'); -1 if none."""
    depth = 0
    for k in range(start, len(tex)):
        depth += {"{": 1, "}": -1}.get(tex[k], 0)
        if depth == 0:
            return k
    return -1


def split_marks(tex: str) -> list[tuple[str, str | None, bool]]:
    """Split a line at its markup into (tex, knob name or None, new?) parts, e.g.
    'a \\knob{q}{b} \\new{c} \\newknob{N}{d}' ->
    [('a', None, False), ('b', 'q', False), ('c', None, True), ('d', 'N', True)].
    Empty parts are dropped; malformed markup is rendered as it is."""
    parts: list[tuple[str, str | None, bool]] = []
    i = 0
    while True:
        found = [(tex.find(m, i), m) for m in MARKS]
        found = [(j, m) for j, m in found if j >= 0]
        if not found:
            break
        j, mark = min(found)
        name, body_open = None, j + len(mark) - 1  # index of the '{' after the command
        if mark != NEW:  # \knob / \newknob: {name}{tex}
            name_end = _group(tex, body_open)
            if name_end < 0 or name_end + 1 >= len(tex) or tex[name_end + 1] != "{":
                break
            name, body_open = tex[body_open + 1:name_end], name_end + 1
        body_end = _group(tex, body_open)
        if body_end < 0:
            break
        parts.append((tex[i:j], None, False))
        parts.append((tex[body_open + 1:body_end], name, mark != KNOB))
        i = body_end + 1
    parts.append((tex[i:], None, False))

    def clean(t: str) -> str:  # trim, but keep an escaped space ("\ ") at the end intact
        s = t.strip()
        return s + " " if s.endswith("\\") and not s.endswith("\\\\") else s

    return [(clean(t), n, new) for t, n, new in parts if t.strip()]


def has_marks(tex: str) -> bool:
    return any(m in tex for m in MARKS)


def split_knobs(tex: str) -> list[tuple[str, str | None]]:
    """'a \\knob{q}{b} c' -> [('a', None), ('b', 'q'), ('c', None)] (empty parts dropped)."""
    return [(t, n) for t, n, _new in split_marks(tex)]


def plain_tex(tex: str) -> str:
    """The line without markup (e.g. for tooltips or a text fallback)."""
    return " ".join(t for t, _n, _new in split_marks(tex))



def _backend():
    global _mathtext
    if _mathtext is None:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import mathtext, rcParams

        rcParams["mathtext.fontset"] = "cm"
        _mathtext = mathtext
    return _mathtext


def render_tex(tex: str, size_px: float = theme.FS_MATH, color: str = theme.INK, dpr: float = 1.0,
               knob_colors: dict | None = None) -> QPixmap | None:
    """Render one line of math (without $...$) to a transparent QPixmap; None if impossible.
    knob_colors: {knob name: theme.KnobColor} for the \\knob{name}{...} parts."""
    parts = split_marks(tex) if has_marks(tex) else [(tex, None, False)]
    colors = knob_colors or {}
    used = tuple(sorted((n, colors[n]) for _t, n, _new in parts if n in colors))
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
        if len(parts) == 1 and parts[0][1] not in colors and not parts[0][2]:
            fig.text(0, 0, f"${parts[0][0]}$", fontsize=size_px, color=color)
        else:
            # one text per part, side by side on the same baseline; coloured parts on a chip,
            # new parts on a soft highlight (a copy of the text with an invisible face and a
            # wider bbox, drawn behind it). Positions in figure fractions (transFigure), which
            # follow the tight bbox crop.
            renderer = canvas.get_renderer()
            em = size_px * dpr
            x = 0.0
            prev_new = False
            for i, (part, name, new) in enumerate(parts):
                kc = colors.get(name)
                pad = GLOW_PAD_EM * em if new else CHIP_PAD_EM * em if kc else 0.0
                gap = 0.0 if i == 0 or (new and prev_new) else SEGMENT_GAP_EM * em
                x += gap + pad
                pos = (x / fig.bbox.width, 0)
                t = fig.text(*pos, f"${part}$", fontsize=size_px, color=kc.ink if kc else color,
                             va="baseline", ha="left", zorder=2)
                if kc:
                    t.set_bbox(dict(boxstyle="round,pad=0.1,rounding_size=0.3", fc=kc.tint, ec="none"))
                if new:
                    fig.text(*pos, f"${part}$", fontsize=size_px, color=(0, 0, 0, 0), va="baseline",
                             ha="left", zorder=1,
                             bbox=dict(boxstyle=f"round,pad={GLOW_PAD_EM},rounding_size=0.45",
                                       fc=theme.NEW_GLOW, ec="none"))
                x = t.get_window_extent(renderer).x1 + pad
                prev_new = new
        buf = io.BytesIO()
        # the tight crop only sees the glyphs, not the highlight boxes: leave room for them
        glow = GLOW_PAD_EM * size_px + 1 if any(new for _t, _n, new in parts) else 0.0
        fig.savefig(buf, format="png", dpi=dpi, transparent=True,
                    bbox_inches="tight", pad_inches=(PAD_PX + glow) / 72)
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
    When the display scaling changes (another monitor), the image is re-rendered in
    event(), NEVER in paintEvent(): rendering or resizing while Qt paints crashed the game
    (Windows access violation) when the window moved to a monitor with other scaling.
    """

    MIN_SIZE_PX = 12.0  # shrink-to-fit floor (a formula wider than its column)

    def __init__(self, tex: str = "", size_px: float = theme.FS_MATH, color: str = theme.INK,
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

    # --- display scaling -------------------------------------------------------------------
    def event(self, e) -> bool:
        if e.type() in _DPR_EVENTS:
            self._check_dpr()
        return super().event(e)

    def _check_dpr(self) -> None:
        """Re-render if the display scaling changed (outside of painting)."""
        if abs(self.devicePixelRatioF() - getattr(self, "_dpr", 0.0)) > 1e-6:
            self._render()
            self.setFixedHeight(self._natural_size().height())
            self.updateGeometry()
            self.update()

    def _own_fit(self) -> float:
        """The largest font size (<= size_px) at which this line fits its width."""
        if self._natural is None or self.width() <= 0:
            return self._size
        nat_w = self._natural.deviceIndependentSize().width()
        if nat_w <= self.width():
            return self._size
        return max(self.MIN_SIZE_PX, math.floor(2 * self._size * self.width() / nat_w) / 2)

    def _set_fit(self, size: float) -> None:
        if self._natural is not None and size != self._fit_size:
            self._fit_size = size
            self._render()
            self.update()

    def _fit(self) -> None:
        group = getattr(self, "_group", None)
        if group is not None:
            group.refit()  # one size for all lines of the group (an OCP), set by the group
        elif self._natural is not None and self.width() > 0:
            self._set_fit(self._own_fit())

    # --- painting ------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        if abs(self.devicePixelRatioF() - getattr(self, "_dpr", 1.0)) > 1e-6:
            # scaling changed without an event we saw: draw the old image now and
            # re-render right after this paint (never during it)
            QTimer.singleShot(0, self, self._check_dpr)
        p = QPainter(self)
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


class FitGroup(QObject):
    """MathLabels that share one font size: the largest at which every member fits its width.
    The lines of one OCP use one group, so a long line makes all of them a little smaller
    instead of being the only small one (consistent sizes, 2026-11-22). The size is applied
    right after the resize that triggered it (all members then have their new widths)."""

    def __init__(self, parent: QObject):
        super().__init__(parent)  # lives (and dies) with the widget that holds the labels
        self._members: list[MathLabel] = []
        self._pending = False

    def add(self, label: "MathLabel") -> "MathLabel":
        self._members.append(label)
        label._group = self
        return label

    def refit(self) -> None:
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self, self._apply)

    def _apply(self) -> None:
        self._pending = False
        sized = [m for m in self._members if m.width() > 0 and m._natural is not None]
        if not sized:
            return
        size = min(m._own_fit() for m in sized)
        for m in sized:
            m._set_fit(size)


class MathChip(QWidget):
    """A knob's symbol (math) on a tinted rounded chip, in the knob's colour. The same
    colours mark the knob's part of the OCP (knob markup), so the two are easy to match."""

    PAD_X, PAD_Y, RADIUS = 6, 2, 8

    def __init__(self, tex: str, knob_color, size_px: float = theme.FS_CHIP, parent: QWidget | None = None):
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

    def event(self, e) -> bool:
        if e.type() in _DPR_EVENTS:
            self._check_dpr()
        return super().event(e)

    def _check_dpr(self) -> None:
        """Re-render (and resize) if the display scaling changed; never called while painting."""
        if abs(self.devicePixelRatioF() - self._dpr) > 1e-6:
            self._render()
            self.update()

    def paintEvent(self, _event) -> None:
        if abs(self.devicePixelRatioF() - self._dpr) > 1e-6:
            QTimer.singleShot(0, self, self._check_dpr)  # re-render after this paint, not during it
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
