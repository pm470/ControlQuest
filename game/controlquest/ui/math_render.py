"""LaTeX-style math in Qt widgets, rendered with matplotlib's mathtext
(no LaTeX installation needed; Computer Modern font, like a textbook).

    lab = MathLabel(r"\\min_{u}\\ \\sum_{k=0}^{N-1} \\ell(x_k, u_k)", size_px=15)

Supported syntax: matplotlib mathtext (a large LaTeX subset: sub/superscripts,
\\sum, \\min, \\|x\\|, \\hat{x}, \\mathrm{...}, \\quad, Greek letters, ...).
No environments (aligned, cases): build multi-line math from several MathLabels.
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


def _backend():
    global _mathtext
    if _mathtext is None:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import mathtext, rcParams

        rcParams["mathtext.fontset"] = "cm"
        _mathtext = mathtext
    return _mathtext


def render_tex(tex: str, size_px: float = 15, color: str = theme.INK, dpr: float = 1.0) -> QPixmap | None:
    """Render one line of math (without $...$) to a transparent QPixmap; None if impossible."""
    key = (tex, round(size_px, 1), color, round(dpr, 2))
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
        FigureCanvasAgg(fig)
        fig.text(0, 0, f"${tex}$", fontsize=size_px, color=color)
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
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._tex, self._size, self._color = tex, size_px, color
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
        self._natural = render_tex(self._tex, self._size, self._color, dpr) if self._tex else None
        self._pixmap = (self._natural if self._fit_size == self._size or self._natural is None
                        else render_tex(self._tex, self._fit_size, self._color, dpr))

    def _natural_size(self) -> QSize:
        if self._natural is None:
            return QSize(self.fontMetrics().horizontalAdvance(self._tex) + 4, self.fontMetrics().height() + 4)
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
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._tex)
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
