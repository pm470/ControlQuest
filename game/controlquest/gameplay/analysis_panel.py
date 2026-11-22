"""The "Analysis" tab of a playable level (2026-11-20): two time-series plots of the latest run,
with a cursor at the replay time. Optional: it changes nothing in the game.

    panel = AnalysisPanel()
    panel.set_plots(level_widget.analysis_plots(result))   # once per new RunResult
    panel.set_time(t)                                       # every playback tick (cheap)
    panel.clear()                                           # "run the simulation first"

A level describes its plots with PlotSpec (data only, built from RunResult.trajectory and the
level file; see the levels' `analysis_plots`). Every series carries its own times: states and
cumulative effort at t_k (n+1 samples), inputs at t_k for k < n, per-solve data at the solve's
sample time. All times are simulation time [s].

How it is drawn (agreed 2026-11-20): matplotlib (Agg, off-screen, like the formulas in
ui/math_render.py) renders each plot ONCE per new run (and on resize / display scaling) into
an image that is painted snapped to device pixels (sharp at 175 %). The time cursor is a line
painted on top with QPainter, so playback never re-renders a plot. Nothing is rendered while
the tab is hidden, and nothing is ever rendered inside paintEvent (that crashed the game on
monitors with different scaling, AGENTS.md section 9).
"""

from __future__ import annotations

import math
import traceback
from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import QPoint, QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

from ..ui import theme
from ..ui.math_render import _DPR_EVENTS
from ..ui.math_text import math_text
from ..ui.widgets import label, scrollable


# --- what a level provides ---------------------------------------------------------------------
@dataclass(frozen=True)
class Series:
    """One curve. style: "line"; "step" (staircase, value held until the next time);
    "segments" (NaN values break the line into segments; a segment of one sample is drawn
    as a dot, so it stays visible)."""

    t: Sequence[float]
    y: Sequence[float]
    label: str = ""
    color: str = theme.PLOT_1
    style: str = "line"
    dashed: bool = False


@dataclass(frozen=True)
class RefLine:
    """A horizontal reference line (budget, limit, star threshold), dashed and labelled."""

    y: float
    label: str
    color: str = theme.PLOT_LIMIT


@dataclass(frozen=True)
class Events:
    """Event times: full-height vertical lines, or small ticks at the bottom (rug=True) when
    there can be many (e.g. every re-plan)."""

    times: Sequence[float]
    label: str
    color: str = theme.PLOT_EVENT
    rug: bool = False


@dataclass(frozen=True)
class Shade:
    """Full-height band over the samples where mask is True (mask[k] belongs to t[k])."""

    t: Sequence[float]
    mask: Sequence[bool]
    label: str
    color: str = theme.PLOT_SHADE


@dataclass(frozen=True)
class PlotSpec:
    title: str  # game font; $...$ allowed
    description: str  # what to look at (1-3 short sentences); $...$ allowed
    y_label: str  # matplotlib mathtext allowed, with the unit, e.g. r"speed $\|v\|$ [m/s]"
    t_end: float  # the run's duration [s]: the x axis is [0, t_end]
    series: tuple[Series, ...]
    ref_lines: tuple[RefLine, ...] = ()
    events: tuple[Events, ...] = ()
    shades: tuple[Shade, ...] = ()
    x_label: str = r"time $t$ [s]"
    y_from_zero: bool = True  # y axis starts at 0 when all values are >= 0
    legend_above: bool = False  # legend in one row above the plot (busy plots), else inside


# --- helpers for the levels (state samples) -----------------------------------------------------
def state_times(tr) -> list[float]:
    """t_k of the n+1 state samples (x, energy, drift share these)."""
    return list(tr.t)


def speeds(tr) -> list[float]:
    """|v(t_k)| for the n+1 states."""
    return [math.hypot(x[2], x[3]) for x in tr.x]


def distances(tr, point) -> list[float]:
    """|p(t_k) - point| for the n+1 states."""
    return [math.hypot(x[0] - point[0], x[1] - point[1]) for x in tr.x]


# --- rendering (matplotlib Agg, off-screen) ------------------------------------------------------
_FONT: str | None = None


def _font_family() -> str:
    """The game's font if matplotlib has it (no "font not found" warnings), else DejaVu Sans."""
    global _FONT
    if _FONT is None:
        from matplotlib import font_manager

        names = {f.name for f in font_manager.fontManager.ttflist}
        _FONT = next((f for f in theme.FONT_FAMILIES if f in names), "DejaVu Sans")
    return _FONT


@dataclass
class Rendered:
    image: QImage  # device-pixel image with the device pixel ratio set
    axes: tuple[float, float, float, float]  # plot area in logical px: left, right, top, bottom
    xlim: tuple[float, float]


def render_plot(spec: PlotSpec, width: int, height: int, dpr: float) -> Rendered:
    """Draw the plot into an image of width x height logical pixels at the given scaling."""
    import matplotlib
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    rc = {
        # the game's font, falling back per glyph to DejaVu Sans (bundled with matplotlib), e.g.
        # for the rating star "★" that Segoe UI does not have
        # sizes from the type scale (px at dpi 100: pt = px * 0.72): labels FS_SMALL, ticks and
        # legend FS_MICRO, like the captions and small labels around the plots (2026-11-22)
        "font.family": [_font_family(), "DejaVu Sans"], "font.size": theme.FS_SMALL * 0.72,
        "mathtext.fontset": "cm",
        "axes.edgecolor": theme.PLOT_GRID, "axes.labelcolor": theme.INK_SOFT,
        "xtick.color": theme.INK_SOFT, "ytick.color": theme.INK_SOFT,
        "xtick.labelsize": theme.FS_MICRO * 0.72, "ytick.labelsize": theme.FS_MICRO * 0.72,
        "axes.labelsize": theme.FS_SMALL * 0.72, "legend.fontsize": theme.FS_MICRO * 0.72,
        "lines.solid_capstyle": "round",
    }
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=(width / 100, height / 100), dpi=100 * dpr, facecolor=theme.SURFACE)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor(theme.SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(color=theme.FIELD_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=3, color=theme.PLOT_GRID)

        for sh in spec.shades:
            ax.fill_between(list(sh.t), 0, 1, where=list(sh.mask), step="post", color=sh.color,
                            alpha=0.16, linewidth=0, transform=ax.get_xaxis_transform(),
                            label=sh.label)
        for ev in spec.events:
            times = list(ev.times)
            if not times:
                continue
            if ev.rug:
                ax.plot(times, [0.0] * len(times), linestyle="none", marker="|", markersize=7,
                        markeredgewidth=1.2, color=ev.color, transform=ax.get_xaxis_transform(),
                        clip_on=False, label=ev.label)
            else:
                for i, t in enumerate(times):
                    ax.axvline(t, color=ev.color, linewidth=1.3, alpha=0.9,
                               label=ev.label if i == 0 else None)
        for ref in spec.ref_lines:
            ax.axhline(ref.y, color=ref.color, linewidth=1.3, linestyle=(0, (5, 3)), label=ref.label)
        for s in spec.series:
            t, y = np.asarray(s.t, float), np.asarray(s.y, float)
            ls = (0, (4, 2.5)) if s.dashed else "-"
            if s.style == "step":
                ax.step(t, y, where="post", color=s.color, linewidth=2.0, linestyle=ls, label=s.label or None)
            elif s.style == "segments":
                ax.plot(t, y, color=s.color, linewidth=1.6, linestyle=ls, label=s.label or None)
                ok = np.isfinite(t) & np.isfinite(y)
                prev = np.concatenate([[False], ok[:-1]])
                nxt = np.concatenate([ok[1:], [False]])
                lone = ok & ~prev & ~nxt  # one-sample segments: a dot
                if lone.any():
                    ax.plot(t[lone], y[lone], linestyle="none", marker="o", markersize=2.8, color=s.color)
            else:
                ax.plot(t, y, color=s.color, linewidth=2.0, linestyle=ls, label=s.label or None)

        ax.set_xlim(0.0, max(spec.t_end, 1e-6))
        if spec.y_from_zero:
            ys = [v for s in spec.series for v in s.y if v is not None and math.isfinite(v)]
            if not ys or min(ys) >= 0:
                ax.set_ylim(bottom=0.0)
        ax.set_xlabel(spec.x_label)
        ax.set_ylabel(spec.y_label)
        if any(s.label for s in spec.series) or spec.ref_lines or spec.events or spec.shades:
            if spec.legend_above:
                n = len(ax.get_legend_handles_labels()[0])
                ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=n, frameon=False,
                          borderaxespad=0.3, labelcolor=theme.INK_SOFT, handlelength=1.6,
                          columnspacing=1.2)
            else:
                leg = ax.legend(loc="best", frameon=True, framealpha=0.88, facecolor=theme.SURFACE,
                                edgecolor="none", labelcolor=theme.INK_SOFT, handlelength=1.8)
                leg.set_zorder(5)
        try:
            fig.tight_layout(pad=0.5)
        except Exception:  # noqa: BLE001 (tiny sizes): keep the default layout
            pass
        canvas.draw()
        w_px, h_px = canvas.get_width_height(physical=True)
        buf = np.asarray(canvas.buffer_rgba())
        image = QImage(buf.data, w_px, h_px, 4 * w_px, QImage.Format.Format_RGBA8888).copy()
        image.setDevicePixelRatio(dpr)
        bb = ax.get_window_extent()
        axes = (bb.x0 / dpr, bb.x1 / dpr, (h_px - bb.y1) / dpr, (h_px - bb.y0) / dpr)
        return Rendered(image=image, axes=axes, xlim=tuple(ax.get_xlim()))


# --- widgets -------------------------------------------------------------------------------------
class PlotView(QWidget):
    """One plot: the rendered image, painted pixel-snapped, plus the time cursor."""

    MIN_HEIGHT = 140
    RENDER_DELAY_MS = 60  # coalesce resizes before re-rendering

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._spec: PlotSpec | None = None
        self._rendered: Rendered | None = None
        self._rendered_for: tuple[int, int, float] | None = None  # (w, h, dpr) of _rendered
        self._t = 0.0
        self.renders = 0  # how often a plot was rendered (tests: no rendering per frame)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(400, self.MIN_HEIGHT)  # grows into the free space; both plots fit at 1280x800

    def set_spec(self, spec: PlotSpec | None) -> None:
        self._spec, self._rendered, self._rendered_for = spec, None, None
        self._schedule(now=True)
        self.update()

    def set_time(self, t: float) -> None:
        self._t = t
        if self._rendered is not None and self.isVisible():
            self.update()  # only the cursor moves: no re-render

    def cursor_x(self) -> float | None:
        """Logical x of the time cursor (tests), None before rendering."""
        if self._rendered is None:
            return None
        left, right, _top, _bottom = self._rendered.axes
        x0, x1 = self._rendered.xlim
        t = min(max(self._t, x0), x1)
        return left + (t - x0) / (x1 - x0) * (right - left) if x1 > x0 else left

    # --- when to render (never while painting) ---------------------------------------------
    def _wanted(self) -> tuple[int, int, float]:
        return self.width(), self.height(), round(self.devicePixelRatioF(), 4)

    def _schedule(self, now: bool = False) -> None:
        if self._spec is None or not self.isVisible():
            return  # rendered when shown
        if self._rendered_for != self._wanted():
            self._timer.start(0 if now else self.RENDER_DELAY_MS)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule(now=True)

    def event(self, e) -> bool:
        if e.type() in _DPR_EVENTS:
            self._schedule(now=True)
        return super().event(e)

    def _render(self) -> None:
        if self._spec is None or not self.isVisible() or self.width() < 60 or self.height() < 60:
            return
        w, h, dpr = self._wanted()
        try:
            self._rendered = render_plot(self._spec, w, h, dpr)
        except Exception:  # noqa: BLE001: a broken plot must never break the game
            traceback.print_exc()
            self._rendered = None
        self._rendered_for = (w, h, dpr)
        self.renders += 1
        self.update()

    # --- painting ---------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        if self._rendered_for is not None and self._rendered_for != self._wanted():
            QTimer.singleShot(0, self, self._schedule)  # stale size/scaling: re-render after this paint
        p = QPainter(self)
        r = self._rendered
        if r is None:
            return
        dpr = self.devicePixelRatioF()
        origin = self.mapTo(self.window(), QPoint(0, 0))
        gx, gy = origin.x() * dpr, origin.y() * dpr  # snap to whole device pixels (sharp at 175 %)
        p.drawImage(QPointF((round(gx) - gx) / dpr, (round(gy) - gy) / dpr), r.image)
        x = self.cursor_x()
        if x is not None:
            _left, _right, top, bottom = r.axes
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor(theme.PLOT_CURSOR), 1.6))
            p.drawLine(QPointF(x, top), QPointF(x, bottom))


class AnalysisPanel(QWidget):
    """The Analysis tab: a message before the first run, then the level's plots (each with a
    title above and a short description below), scrolling when the window is small."""

    EMPTY = "The plots of this run appear here after you run the simulation."

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._stack = QStackedLayout(self)
        self._message = label(self.EMPTY, "caption", wrap=True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_page = QWidget()
        msg_lay = QVBoxLayout(msg_page)
        msg_lay.addStretch(1)
        msg_lay.addWidget(self._message)
        msg_lay.addStretch(1)
        self._stack.addWidget(msg_page)
        self._content = QWidget()
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(0, 0, 4, 0)
        self._lay.setSpacing(6)
        self._scroll = scrollable(self._content)
        self._stack.addWidget(self._scroll)
        self.views: list[PlotView] = []
        self.specs: list[PlotSpec] = []
        self._t = 0.0

    def has_plots(self) -> bool:
        return bool(self.specs)

    def set_plots(self, specs: list[PlotSpec]) -> None:
        """Replace the plots with the ones of a new run."""
        self._clear_content()
        self.specs = list(specs)
        if not self.specs:
            self.clear("No plots for this level.")
            return
        for i, spec in enumerate(self.specs):
            if i:
                self._lay.addSpacing(10)
            self._lay.addWidget(math_text(spec.title, "goal"))
            view = PlotView()
            view.set_time(self._t)
            self._lay.addWidget(view, 1)
            self._lay.addWidget(math_text(spec.description, "caption"))
            view.set_spec(spec)
            self.views.append(view)
        self._stack.setCurrentWidget(self._scroll)

    def clear(self, message: str | None = None) -> None:
        """Back to the message page (no run yet, or the plots could not be built)."""
        self._clear_content()
        self.specs = []
        self._message.setText(message or self.EMPTY)
        self._stack.setCurrentIndex(0)

    def set_time(self, t: float) -> None:
        self._t = t
        for v in self.views:
            v.set_time(t)

    def _clear_content(self) -> None:
        self.views = []
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
