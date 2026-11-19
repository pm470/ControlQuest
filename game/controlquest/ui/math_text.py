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
baseline sits on the text baseline (mathtext reports the formula's depth). Like MathLabel,
it re-renders on display-scaling changes in event(), never while painting (AGENTS.md
gotchas: two monitors).
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QSize, QSizeF, Qt, QUrl
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QTextDocument
from PySide6.QtWidgets import QFrame, QSizePolicy, QTextBrowser, QWidget

from . import theme
from .math_render import _DPR_EVENTS, _backend

MATH = re.compile(r"\$(.+?)\$")
MATH_SCALE = 1.12  # Computer Modern looks smaller than the game font at the same pixel size

# text roles (same sizes/colours as the QSS label roles in theme.stylesheet)
ROLES = {
    "body": (15, 400, theme.INK_SOFT, False),
    "caption": (13, 400, theme.MUTED, False),
    "goal": (15, 600, theme.INK, False),
    "subheading": (18, 800, theme.INK, False),
    "quote": (20, 400, theme.INK, True),
}

_cache: dict[tuple, tuple[QImage, float]] = {}
_parser = None


def inline_image(tex: str, size_px: float, color: str, dpr: float) -> tuple[QImage, float] | None:
    """The formula as an image (device pixels, with its pixel ratio set) and its depth below
    the baseline in logical pixels; None if mathtext cannot read it."""
    key = (tex, round(size_px, 1), color, round(dpr, 2))
    if key in _cache:
        return _cache[key]
    global _parser
    try:
        _backend()  # Computer Modern, Agg
        import numpy as np
        from matplotlib.font_manager import FontProperties
        from matplotlib.mathtext import MathTextParser

        if _parser is None:
            _parser = MathTextParser("agg")
        r = _parser.parse(f"${tex}$", dpi=72 * dpr, prop=FontProperties(size=size_px))
        alpha = np.ascontiguousarray(np.asarray(r.image, dtype=np.uint8))
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
    _cache[key] = (img, r.depth / dpr)
    return _cache[key]


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
        html, n = [], 0
        for i, part in enumerate(MATH.split(self._text)):
            if i % 2 == 0:
                html.append(part)
                continue
            got = inline_image(part, size * MATH_SCALE, color, dpr)
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
        self._relayout()

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
