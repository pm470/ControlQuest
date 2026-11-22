"""Text with inline math: the words in the game font, every $...$ part typeset in the
LaTeX font (matplotlib mathtext, Computer Modern), like the OCP formulas (2026-11-19).

    t = math_text(r"First it measures the state $\\hat{x}$ and applies $u_0$.", "body")
    t.setText(r"The plan ends at $x_N$.")       # change it later (like QLabel.setText)

Write math-like text with $...$ everywhere a player reads it (tour, intro, goals, hints,
knob help, result card, engine sentences). The words are rich text (<b>, <br>, <sub> work).
For tooltips and the console use to_plain(text), which turns the math into Unicode.

How it works: a read-only QTextBrowser that looks like a QLabel (no frame, transparent, no
scrolling, wheel events go to the parent scroll area). Each formula is rasterised by
mathtext at the display's pixel ratio (sharp at 175 %) and placed as an inline image whose
baseline sits on the text baseline (_rasterise computes the formula's true depth). A formula
is as bold as the text around it (bold role, bold=True or <b>...</b>), and align_baselines()
lines up the cells of a grid row. Like MathLabel,
it re-renders on display-scaling changes in event(), never while painting (AGENTS.md
gotchas: two monitors).
"""

from __future__ import annotations

import math
import re

from PySide6.QtCore import QEvent, QSize, QSizeF, Qt, QUrl
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QTextDocument
from PySide6.QtWidgets import QFrame, QSizePolicy, QTextBrowser, QWidget

from . import theme
from .math_render import _DPR_EVENTS, _backend

MATH = re.compile(r"\$(.+?)\$")
_BOLD_TAG = re.compile(r"<(/?)(?:b|strong)\b[^>]*>", re.IGNORECASE)
MATH_SCALE = theme.MATH_SCALE  # Computer Modern looks smaller than the game font at the same size

# text roles (same sizes/colours as the QSS label roles in theme.stylesheet: the type scale)
ROLES = {
    "body": (theme.FS_BODY, 400, theme.INK_SOFT, False),
    "caption": (theme.FS_SMALL, 400, theme.MUTED, False),
    "goal": (theme.FS_BODY, 600, theme.INK, False),
    "subheading": (theme.FS_H2, 800, theme.INK, False),
    "quote": (theme.FS_H2, 400, theme.INK, True),
}

_cache: dict[tuple, tuple[QImage, float]] = {}
_parser = None


# CSS weight -> pen width as a fraction of the font size (DemiBold, Bold, ExtraBold+), chosen so the
# formula looks as heavy as the game font's words at that weight
BOLD_STROKE = {600: 0.03, 700: 0.04, 800: 0.05}


def stroke_for(weight: int) -> float:
    """How much a formula is thickened (fraction of the font size) to match text of this CSS
    font weight: 0 for regular text, more for semi-bold / bold / extra-bold."""
    return max((f for w, f in BOLD_STROKE.items() if weight >= w), default=0.0)


def inline_image(tex: str, size_px: float, color: str, dpr: float,
                 weight: int = 400) -> tuple[QImage, float] | None:
    """The formula as an image (device pixels, with its pixel ratio set) and its depth below
    the baseline in logical pixels; None if mathtext cannot read it.

    weight: the CSS font weight of the text around the formula (400 regular, 600 DemiBold, 700
    Bold, 800 ExtraBold). From 600 on the glyphs are emboldened: their vector outlines are
    filled and stroked with a round pen (stroke_for(weight) x the font size, half of it on each
    side) before rasterising, so the strokes get evenly thicker and the edges stay sharp
    (_rasterise_bold). The glyph shapes stay those of the OCP's math font; mathtext's own bold
    (\\mathbf / \\mathbfit) switches to other Computer Modern fonts with differently shaped
    letters. (2026-11-22; the first version, shifted copies of the bitmap, looked smeared.)"""
    stroke = stroke_for(weight)
    key = (tex, round(size_px, 1), color, round(dpr, 2), stroke)
    if key in _cache:
        return _cache[key]
    try:
        _backend()  # Computer Modern, Agg
        import numpy as np

        if stroke:
            image, depth = _rasterise_bold(tex, size_px, dpr, stroke * size_px * dpr)
        else:
            image, depth = _rasterise(tex, size_px, dpr)
        alpha = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
    except Exception as exc:  # invalid math: the caller shows the plain text
        print(f"[math] could not render inline {tex!r}: {exc}")
        return None
    h, w = alpha.shape
    c = QColor(color)
    rgba = np.empty((h, w, 4), dtype=np.uint8)  # premultiplied BGRA (Format_ARGB32_Premultiplied)
    a = alpha.astype(np.uint16)
    rgba[..., 0] = (c.blue() * a // 255).astype(np.uint8)
    rgba[..., 1] = (c.green() * a // 255).astype(np.uint8)
    rgba[..., 2] = (c.red() * a // 255).astype(np.uint8)
    rgba[..., 3] = alpha
    img = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_ARGB32_Premultiplied).copy()
    img.setDevicePixelRatio(dpr)
    _cache[key] = (img, depth / dpr)
    return _cache[key]


def _rasterise_bold(tex: str, size_px: float, dpr: float, pen_px: float):
    """Emboldened formula: mathtext's glyph outlines (TextPath, baseline at y = 0, 1 unit = 1
    logical pixel) filled and stroked with a round pen of pen_px device pixels, rasterised by
    Agg with antialiasing. Returns the alpha image and the depth (device pixels from the
    baseline to the image bottom)."""
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import PathPatch
    from matplotlib.textpath import TextPath
    from matplotlib.transforms import Affine2D

    path = TextPath((0, 0), f"${tex}$", size=size_px, prop=FontProperties(size=size_px))
    ext = path.get_extents()
    pad = pen_px / 2 + 2  # room for the pen and the antialiased edge
    # Where a glyph that sits on the baseline ends at the bottom (device px above the image
    # bottom): the pen grows it by half its width below the baseline too. That line is the
    # bold formula's baseline (a bold font's glyphs also stand on the baseline). Lift the drawing
    # by a fraction of a pixel so it falls on a pixel row: no rounding when it is placed in text.
    base = pad - ext.y0 * dpr - pen_px / 2
    lift = math.ceil(base) - base
    w = math.ceil(ext.width * dpr + 2 * pad)
    h = math.ceil(ext.height * dpr + 2 * pad + lift)
    fig = Figure(figsize=(w / 72, h / 72), dpi=72)  # 1 point = 1 device pixel
    fig.patch.set_alpha(0)
    canvas = FigureCanvasAgg(fig)
    to_px = Affine2D().translate(-ext.x0, -ext.y0).scale(dpr).translate(pad, pad + lift)  # display
    fig.add_artist(PathPatch(path, transform=to_px, facecolor="black", edgecolor="black",
                             linewidth=pen_px, joinstyle="round", capstyle="round", antialiased=True))
    canvas.draw()
    alpha = np.asarray(canvas.buffer_rgba())[..., 3].copy()
    return alpha, math.ceil(base)


def _rasterise(tex: str, size_px: float, dpr: float):
    """mathtext's alpha image of the formula and the true distance (device pixels) from its
    baseline to the image bottom.

    The depth that MathTextParser("agg").parse() reports is too small: it is measured from a
    wrong baseline row (1 device pixel off for plain formulas, 1.5-2 for subscripts and accents
    such as \\hat{x}), so inline formulas sat above the text line (2026-11-22). Here the image
    is made the same way (matplotlib's Output.to_raster) and the baseline row is computed from
    the layout box: the box top is drawn at row -ymin, the baseline box.height below it.
    Falls back to the public parse (old offset) if matplotlib's internals ever change."""
    global _parser
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import MathTextParser

    prop = FontProperties(size=size_px)
    s = f"${tex}$"
    try:
        from matplotlib import _mathtext
        from matplotlib.backends import backend_agg

        fontset = MathTextParser._font_type_mapping[prop.get_math_fontfamily()](
            prop, backend_agg.get_hinting_flag())
        import numpy as np

        box = _mathtext.Parser().parse(s, fontset, prop.get_size_in_points(), 72 * dpr)
        out = _mathtext.ship(box)
        xmin = min([*[ox + info.metrics.xmin for ox, _oy, info in out.glyphs],
                    *[x for x, _y, _w, _h in out.rects], 0]) - 1
        ymin = min([*[oy - info.metrics.ymax for _ox, oy, info in out.glyphs],
                    *[y for _x, y, _w, _h in out.rects], 0]) - 1
        xmax = max([*[ox + info.metrics.xmax for ox, _oy, info in out.glyphs],
                    *[x + w for x, _y, w, _h in out.rects], 0]) + 1
        ymax = max([*[oy - info.metrics.ymin for _ox, oy, info in out.glyphs],
                    *[y + h for _x, y, _w, h in out.rects], 0]) + 1
        # Like Output.to_raster, but shifted down by a fraction of a pixel so the baseline falls
        # exactly on a pixel row. to_raster puts it at a fractional row that differs from formula
        # to formula, and its int() rounding moved neighbouring formulas (e.g. the legend's words,
        # one formula each) up or down by a pixel (2026-11-22).
        base = box.height - ymin
        lift = math.ceil(base - 1e-6) - base
        image = np.zeros((math.ceil(ymax - ymin + lift), math.ceil(xmax - xmin)), np.uint8)
        shifted = _mathtext.ship(box, (-xmin, -ymin + lift))
        for ox, oy, info in shifted.glyphs:
            info.font.draw_glyph_to_bitmap(image, int(ox), int(oy - info.metrics.iceberg),
                                           info.glyph, antialiased=True)
        for x, y, bw, bh in shifted.rects:  # rules (fraction bars, ...), as in to_raster
            height = max(int(bh) - 1, 0)
            y = int(y + bh / 2 - (height + 1) / 2) if height == 0 else int(y)
            image[y:y + height + 1, math.floor(x):math.ceil(x + bw) + 1] = 0xFF
        return image, image.shape[0] - round(base + lift)
    except Exception:  # invalid math raises again below (the caller shows the plain text)
        pass
    if _parser is None:
        _parser = MathTextParser("agg")
    r = _parser.parse(s, dpi=72 * dpr, prop=prop)
    return r.image, r.depth


def _pad_bottom(img: QImage, rows: int) -> QImage:
    if rows <= 0:
        return img
    out = QImage(img.width(), img.height() + rows, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter

    out.setDevicePixelRatio(img.devicePixelRatio())  # same ratio: the copy is 1:1 in device pixels
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    return out


class MathText(QTextBrowser):
    """A label-like text block with inline math (see the module docstring)."""

    def __init__(self, text: str = "", role: str = "body", wrap: bool = True, bold: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._text, self._role, self._wrap, self._bold = text, role, wrap, bold
        self._dpr = 0.0
        self._top_pad = 0.0
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.document().setDocumentMargin(0)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred if wrap else QSizePolicy.Policy.Fixed,
                             QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(wrap)
        self.setSizePolicy(policy)
        self._build()

    # --- like QLabel ----------------------------------------------------------------------
    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._build()

    def setWordWrap(self, on: bool) -> None:  # QLabel compatibility
        self._wrap = on
        self._build()

    # --- building -------------------------------------------------------------------------
    def _style(self):
        size, weight, color, italic = ROLES.get(self._role, ROLES["body"])
        return size, (700 if self._bold else weight), color, italic

    def _build(self) -> None:
        dpr = self.devicePixelRatioF() or 1.0
        self._dpr = dpr
        size, weight, color, italic = self._style()
        font = theme.font(size)
        font.setWeight(_qt_weight(weight))
        font.setItalic(italic)
        doc = self.document()
        doc.setDefaultFont(font)
        descent = QFontMetricsF(font).descent()
        html, n, in_bold = [], 0, 0
        for i, part in enumerate(MATH.split(self._text)):
            if i % 2 == 0:
                html.append(part)
                for tag in _BOLD_TAG.finditer(part):  # is the next formula inside <b>...</b>?
                    in_bold = max(0, in_bold + (-1 if tag.group(1) else 1))
                continue
            # the formula takes the weight of the text around it (role, bold=True or <b>)
            got = inline_image(part, size * MATH_SCALE, color, dpr,
                               weight=max(weight, 700) if in_bold else weight)
            if got is None:
                html.append(to_plain(f"${part}$"))
                continue
            img, depth = got
            # bottom-aligned to the line: pad so the formula's baseline lands on the text's
            img = _pad_bottom(img, round(max(0.0, descent - depth) * dpr))
            url = f"cqmath://{id(self)}/{n}"
            n += 1
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(url), img)
            html.append(f'<img src="{url}" width="{img.width() / dpr:.2f}" '
                        f'height="{img.height() / dpr:.2f}" style="vertical-align: bottom">')
        css = (f"color: {color}; font-size: {size}px; font-weight: {weight};"
               + (" font-style: italic;" if italic else "")
               + ("" if self._wrap else " white-space: nowrap;"))
        self.setHtml(f'<div style="{css}">{"".join(html)}</div>')
        if self._top_pad:  # room above the text, to share a baseline with its row (align_baselines)
            fmt = doc.rootFrame().frameFormat()
            fmt.setTopMargin(self._top_pad)
            doc.rootFrame().setFrameFormat(fmt)
        self._relayout()

    def baseline(self) -> float:
        """y of the first line's baseline, in this widget's coordinates."""
        doc = self.document()
        block = doc.firstBlock()
        line = block.layout().lineAt(0) if block.layout().lineCount() else None
        top = doc.documentLayout().blockBoundingRect(block).top()
        return top + (line.y() + line.ascent() if line is not None else 0.0)

    def set_top_pad(self, pad: float) -> None:
        if abs(pad - self._top_pad) > 1e-3:
            self._top_pad = max(0.0, pad)
            self._build()

    def _relayout(self) -> None:
        doc = self.document()
        if self._wrap:
            doc.setTextWidth(max(1, self.viewport().width()))
        else:
            doc.setTextWidth(-1)
            ideal = doc.idealWidth()
            doc.setTextWidth(ideal)
            self.setFixedWidth(int(ideal) + 2)
        self.setFixedHeight(max(1, int(round(doc.size().height())) + 1))
        self.updateGeometry()

    # --- layout ---------------------------------------------------------------------------
    def hasHeightForWidth(self) -> bool:
        return self._wrap

    def heightForWidth(self, width: int) -> int:
        doc = self.document().clone()
        doc.setTextWidth(max(1, width))
        return int(round(doc.size().height())) + 1

    def sizeHint(self) -> QSize:
        doc = self.document()
        return QSize(int(doc.idealWidth()) + 2, int(round(doc.size().height())) + 1)

    def minimumSizeHint(self) -> QSize:
        return QSize(40 if self._wrap else self.sizeHint().width(), self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._wrap and event.size().width() != event.oldSize().width():
            self._relayout()

    # --- behave like a label ----------------------------------------------------------------
    def wheelEvent(self, event) -> None:
        event.ignore()  # let the scroll area around it scroll

    def event(self, e) -> bool:
        if e.type() in _DPR_EVENTS and abs(self.devicePixelRatioF() - self._dpr) > 1e-6:
            self._build()  # display scaling changed: re-render (never inside paintEvent)
        return super().event(e)


def _qt_weight(weight: int):
    from PySide6.QtGui import QFont

    return {400: QFont.Weight.Normal, 600: QFont.Weight.DemiBold, 700: QFont.Weight.Bold,
            800: QFont.Weight.ExtraBold}.get(weight, QFont.Weight.Normal)


def math_text(text: str, role: str = "body", wrap: bool = True, bold: bool = False) -> MathText:
    """Like widgets.label(), but $...$ parts are typeset in the LaTeX font."""
    return MathText(text, role, wrap, bold)


def align_baselines(grid) -> None:
    """Put the first lines of the MathText cells of each grid row on one baseline (cells in
    different roles, e.g. "Time" (body) · "26.8 s" (subheading) · "★★ ≤ 30 s" (caption)).
    Centring them vertically left the bigger value 2 px low (2026-11-22). Call it after the
    row's widgets are added; the cells are top-aligned and padded above."""
    rows: dict[int, list[MathText]] = {}
    for i in range(grid.count()):
        w = grid.itemAt(i).widget()
        if isinstance(w, MathText):
            rows.setdefault(grid.getItemPosition(i)[0], []).append(w)
    for cells in rows.values():
        for w in cells:
            w.set_top_pad(0.0)
        top = max(w.baseline() for w in cells)
        for w in cells:
            w.set_top_pad(top - w.baseline())
            grid.setAlignment(w, Qt.AlignmentFlag.AlignTop)


# --- plain Unicode for tooltips and the console ---------------------------------------------
_SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
_SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_SYMBOLS = {r"\star": "★", r"\leq": "≤", r"\geq": "≥", r"\Delta": "Δ", r"\sum": "Σ",
            r"\cdot": "·", r"\|": "‖", r"\ell": "ℓ", r"\to": "→", r"\approx": "≈",
            r"\ldots": "…", r"\quad": "  ", r"\,": " ", r"\;": " ", r"\ ": " ", r"\!": ""}


def _plain_math(tex: str) -> str:
    s = tex
    s = re.sub(r"\\hat\{(\w)\}", lambda m: m.group(1) + "\u0302", s)
    s = re.sub(r"\\(?:mathrm|mathbf|text)\{([^{}]*)\}", r"\1", s)
    for k, v in _SYMBOLS.items():
        s = s.replace(k, v)

    def script(m, table, mark):
        body = m.group(1) or m.group(2)
        out = body.translate(table)
        return out if all(ch not in out for ch in body if ch not in "★") else mark + body

    s = re.sub(r"_\{([^{}]*)\}|_(\S)", lambda m: script(m, _SUB, "_"), s)
    s = re.sub(r"\^\{([^{}]*)\}|\^(\S)", lambda m: script(m, _SUP, "^"), s)
    return s.replace("{", "").replace("}", "").replace("\\", "")


def to_plain(text: str) -> str:
    """The text with every $...$ part turned into readable Unicode (tooltips, console)."""
    return MATH.sub(lambda m: _plain_math(m.group(1)), text)
