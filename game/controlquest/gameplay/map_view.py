"""The playing field: the world in metres, drawn with the same scale in x and y
and y pointing up (PRD 9.2). Shows start, target, blocks with the ellipses the
solver sees (dashed), waypoints, the ball, its trail, the current MPC plan
(dashed, one dot per stage), the applied acceleration and a crash marker.

    view.set_level(data)            # world size, start, target, blocks
    view.set_waypoints(points)      # [(x, y), ...] in metres (Level 3)
    view.set_margin(m)              # obstacle margin knob (Level 4): redraws the ellipses
    view.show_ghost = True          # Level 4: where the plan from M samples ago expected the ball
    view.show_wind = True           # Level 5: wind arrow (from the trajectory's disturbance)
    view.set_trajectory(traj)       # a RunResult.trajectory (or None to clear)
    view.set_time(t)                # replay position in seconds (interpolated)
    view.to_world(pos), view.to_screen(x, y)   # pixel <-> metre (e.g. for mouse editing)
    view.set_tour(focus, fan)       # Level 0's guided tour: what to highlight (see TOUR_FOCUS)
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..engine.protocol import Trajectory
from ..ui import painting, theme
from .level_data import LevelData
from .obstacles import Ellipse, level_ellipses

# room around the field: axis numbers left and below, a little air top and right
MARGIN_LEFT, MARGIN_BOTTOM, MARGIN_TOP, MARGIN_RIGHT = 30, 24, 10, 14
BALL_RADIUS_M = 0.9
# Level 0's guided tour: what the map shows and highlights in each step
#   start    ball and star only (no plan, no input yet)
#   measure  + a ring and a label on the ball (the measured state)
#   predict  + a faint fan of example predictions (set_tour(..., fan=paths))
#   plan     + the plan, its last point labelled (N steps ahead)
#   apply    the plan faint, its first step and the input arrow highlighted
#   repeat   the plan, with an earlier solve's plan faint behind it (set_tour(..., earlier=k))
TOUR_FOCUS = ("start", "measure", "predict", "plan", "apply", "repeat")
_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


class MapView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(320, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._data: LevelData | None = None
        self._traj: Trajectory | None = None
        self._t = 0.0
        self._ellipses: list[Ellipse] = []
        self._waypoints: list[tuple[float, float]] = []
        self.show_plan = True
        self.show_ellipses = True
        self.show_ghost = False
        self.show_wind = False
        self._tour: str | None = None  # Level 0: one of TOUR_FOCUS, None = normal map
        self._fan: list[list[tuple[float, float]]] = []
        self._earlier: int | None = None  # tour step "repeat": which earlier plan is drawn grey

    # --- data -------------------------------------------------------------------------
    def set_level(self, data: LevelData) -> None:
        self._data = data
        self._ellipses = level_ellipses(data.blocks, data.margin)
        self.update()

    def set_margin(self, margin: float) -> None:
        """Recompute the solver's ellipses for another obstacle margin (a knob in Level 4)."""
        if self._data is not None:
            self._ellipses = level_ellipses(self._data.blocks, margin)
            self.update()

    @property
    def ellipses(self) -> list[Ellipse]:
        return self._ellipses

    def set_waypoints(self, points) -> None:
        self._waypoints = [tuple(q) for q in points]
        self.update()

    def set_trajectory(self, traj: Trajectory | None) -> None:
        self._traj = traj
        self._t = 0.0
        self.update()

    def set_time(self, t: float) -> None:
        self._t = t
        self.update()

    def set_tour(self, focus: str | None, fan=None, earlier: int | None = None) -> None:
        """Level 0's guided tour: highlight one part of the MPC loop (TOUR_FOCUS), or None
        for the normal map. fan: example predicted paths [[(x, y), ...], ...] (step predict).
        earlier: the solve whose plan is drawn grey in step repeat (default: the previous one)."""
        self._tour = focus
        self._fan = [list(path) for path in (fan or [])]
        self._earlier = earlier
        self.update()

    # --- world <-> screen ----------------------------------------------------------------
    def _transform(self):
        (x0, y0), (x1, y1) = self._data.workspace
        w = self.width() - MARGIN_LEFT - MARGIN_RIGHT
        h = self.height() - MARGIN_TOP - MARGIN_BOTTOM
        s = max(1e-6, min(w / (x1 - x0), h / (y1 - y0)))  # px per metre, same in x and y
        ox = MARGIN_LEFT + (w - s * (x1 - x0)) / 2
        oy = MARGIN_TOP + (h + s * (y1 - y0)) / 2

        def to_px(px: float, py: float) -> QPointF:
            return QPointF(ox + s * (px - x0), oy - s * (py - y0))

        return to_px, s

    def to_screen(self, x: float, y: float) -> QPointF:
        return self._transform()[0](x, y)

    def to_world(self, pos: QPointF) -> tuple[float, float] | None:
        """Metres under a widget position, or None outside the field."""
        if self._data is None:
            return None
        (x0, y0), (x1, y1) = self._data.workspace
        origin, s = self._transform()[0](x0, y0), self._transform()[1]
        x, y = x0 + (pos.x() - origin.x()) / s, y0 - (pos.y() - origin.y()) / s
        return (x, y) if x0 <= x <= x1 and y0 <= y <= y1 else None

    def ball_radius_px(self) -> float:
        return max(9.0, min(18.0, self._transform()[1] * BALL_RADIUS_M))

    def _state_at(self, t: float):
        """Interpolated state at time t, the index of the current sample, and progress."""
        tr = self._traj
        k, a = tr.index_at(t)
        xa, xb = tr.x[k], tr.x[min(k + 1, len(tr.x) - 1)]
        x = [xa[i] + a * (xb[i] - xa[i]) for i in range(4)]
        return x, k

    # --- painting -----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        if self._data is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        to_px, s = self._transform()
        (x0, y0), (x1, y1) = self._data.workspace

        # field: a soft board, no outline
        field = QRectF(to_px(x0, y1), to_px(x1, y0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.FIELD))
        p.drawRoundedRect(field, 16, 16)

        # grid every 5 m (inner lines only), numbers every 10 m; one shared 0 at the corner
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(field, 16, 16)
        p.setClipPath(clip)
        p.setPen(QPen(QColor(theme.FIELD_GRID), 1.3))
        for gx in range(int(math.ceil(x0)), int(x1) + 1, 5):
            if x0 < gx < x1:
                p.drawLine(to_px(gx, y0), to_px(gx, y1))
        for gy in range(int(math.ceil(y0)), int(y1) + 1, 5):
            if y0 < gy < y1:
                p.drawLine(to_px(x0, gy), to_px(x1, gy))
        p.restore()
        p.setFont(theme.font(11, QFont.Weight.Bold))
        p.setPen(QColor(theme.MUTED))
        same_origin = x0 == y0
        for gx in range(int(math.ceil(x0)), int(x1) + 1, 10):
            if gx == x0 and same_origin:
                continue
            p.drawText(QRectF(to_px(gx, y0).x() - 20, field.bottom() + 4, 40, 18),
                       Qt.AlignmentFlag.AlignHCenter, f"{gx}")
        for gy in range(int(math.ceil(y0)), int(y1) + 1, 10):
            if gy == y0 and same_origin:
                continue
            p.drawText(QRectF(field.left() - 32, to_px(x0, gy).y() - 9, 26, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{gy}")
        if same_origin:  # the origin's 0 once, diagonally below-left of the corner
            p.drawText(QRectF(field.left() - 32, field.bottom() + 4, 26, 18),
                       Qt.AlignmentFlag.AlignRight, f"{x0:g}")

        r_px = max(9.0, min(18.0, s * BALL_RADIUS_M))
        start, target = to_px(*self._data.start), to_px(*self._data.target)

        # blocks (what the ball can hit) and the ellipses the solver avoids
        if self.show_ellipses:
            for e in self._ellipses:
                painting.draw_dashed_outline(p, [to_px(*q) for q in e.boundary()])
        for corners in self._data.blocks:
            painting.draw_block_polygon(p, [to_px(*c) for c in _ccw(corners)], depth=min(4.0, s * 0.3))

        # start ring and target star
        p.setPen(QPen(QColor(theme.BALL), 2.5, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(start, r_px * 0.9, r_px * 0.9)
        painting.draw_star(p, target, r_px * 1.2)

        tr = self._traj if self._traj is not None and self._traj.x else None
        x, k = self._state_at(self._t) if tr else (None, 0)
        active = None
        if tr and tr.ref_index:
            active = tr.ref_index[min(k, len(tr.ref_index) - 1)]
        self._draw_waypoints(p, to_px, start, target, r_px, active)

        if tr is None:
            painting.draw_ball(p, start, r_px, look=QPointF(1, 0))
            return

        ball = to_px(x[0], x[1])

        # trail
        trail = QPainterPath(to_px(*tr.x[0][:2]))
        for xi in tr.x[1:k + 1]:
            trail.lineTo(to_px(xi[0], xi[1]))
        trail.lineTo(ball)
        p.setPen(QPen(theme.qcolor(theme.BALL, 70), r_px * 0.7, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(trail)

        # current plan (receding horizon): the plan being executed. Normally it was computed at
        # this sample; with a re-plan interval > 1 it was computed earlier, and the ball runs
        # open-loop along it until the next solve: that open-loop part is drawn solid (PRD 5.3).
        tour = self._tour
        plan_pts: list[QPointF] = []
        if self.show_plan and tr.plans and tour not in ("start", "measure", "predict"):
            steps = tr.steps
            s = tr.solve_at(self._t)
            plan, m = tr.plans[s], k - steps[s]
            nxt = steps[s + 1] if s + 1 < len(steps) else len(tr.x) - 1
            at_end = k >= len(tr.x) - 1 and steps[s] != k
            width = max(2.0, r_px * 0.22)
            old = self._earlier if self._earlier is not None else s - 1
            if tour == "repeat" and 0 <= old < s:  # an earlier plan, faint, behind the new one
                p.save()
                p.setOpacity(0.45)
                painting.draw_plan(p, [to_px(q[0], q[1]) for q in tr.plans[old]],
                                   color=theme.MUTED, width=width)
                p.restore()
            if not at_end and 0 <= m < len(plan):
                plan_pts = [to_px(q[0], q[1]) for q in plan[m:]]
                p.save()
                if tour == "apply":
                    p.setOpacity(0.35)
                painting.draw_plan(p, plan_pts, width=width)
                p.restore()
                if nxt - steps[s] > 1:  # open-loop stretch until the next re-plan
                    seg = [to_px(q[0], q[1]) for q in plan[m:min(nxt - steps[s], len(plan) - 1) + 1]]
                    if len(seg) > 1:
                        p.setPen(QPen(QColor(theme.PRIMARY), width * 1.4, Qt.PenStyle.SolidLine,
                                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        path = QPainterPath(seg[0])
                        for q in seg[1:]:
                            path.lineTo(q)
                        p.drawPath(path)

        # ghost ball: where the plan computed M samples ago expected the ball now (Level 4)
        M = tr.prediction_lookahead
        if self.show_ghost and M and not tr.solve_steps and M <= k and k - M < len(tr.plans) and M < len(tr.plans[k - M]):
            q = tr.plans[k - M][M]
            ghost = to_px(q[0], q[1])
            p.setPen(QPen(theme.qcolor(theme.BALL_DARK, 170), 2, Qt.PenStyle.DashLine))
            p.setBrush(theme.qcolor(theme.BALL, 45))
            p.drawEllipse(ghost, r_px, r_px)

        # Level 0's tour: a faint fan of example predictions (step "predict")
        if tour == "predict":
            for path in self._fan:
                pts = [to_px(*q) for q in path]
                p.save()
                p.setOpacity(0.55)
                painting.draw_plan(p, pts, color=theme.INK_SOFT, width=max(1.6, r_px * 0.15))
                p.restore()
        # the applied input's first step (step "apply")
        if tour == "apply" and len(plan_pts) > 1:
            p.setPen(QPen(QColor(theme.PRIMARY), max(3.0, r_px * 0.32), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(plan_pts[0], plan_pts[1])

        # applied acceleration (arrow length ~ |a|); in the tour only once it is applied
        if k < len(tr.u) and tour not in ("start", "measure", "predict", "plan"):
            ax, ay = tr.u[k]
            mag = math.hypot(ax, ay)
            if mag > 1e-3:
                L = r_px * (0.9 + 1.4 * mag / max(self._data.a_max, 1e-6))
                d = QPointF(ax / mag, -ay / mag)
                a0, a1 = ball + d * (r_px * 1.15), ball + d * (r_px * 1.15 + L)
                pen = QPen(QColor(theme.BALL_DARK), max(2.0, r_px * 0.2), Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(a0, a1)
                n = QPointF(-d.y(), d.x())
                p.drawLine(a1, a1 - d * (r_px * 0.45) + n * (r_px * 0.3))
                p.drawLine(a1, a1 - d * (r_px * 0.45) - n * (r_px * 0.3))

        speed = math.hypot(x[2], x[3])
        look = QPointF(x[2], -x[3]) if speed > 0.05 else QPointF(0.4, 0.2)
        painting.draw_ball(p, ball, r_px, look=look)

        # Level 0's tour: ring + labels on what the current step is about
        if tour == "measure":
            p.setPen(QPen(QColor(theme.PRIMARY), 3, Qt.PenStyle.SolidLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(ball, r_px * 1.7, r_px * 1.7)
            self._tag(p, field, ball + QPointF(0, -r_px * 1.7 - 22), "measured: position & speed")
        elif tour == "plan" and plan_pts:
            n = len(plan_pts) - 1
            end = plan_pts[-1]
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.PRIMARY))
            p.drawEllipse(end, r_px * 0.35, r_px * 0.35)
            self._tag(p, field, end + QPointF(0, -r_px - 18),
                      f"x{str(n).translate(_SUBSCRIPT)}: {n * tr.dt:g} s ahead")
        elif tour == "repeat" and plan_pts and tr.plans:
            # receding horizon: the end of the first (grey) plan vs where the plan ends now
            old = self._earlier if self._earlier is not None else tr.solve_at(self._t) - 1
            if 0 <= old < tr.solve_at(self._t):
                q = tr.plans[old][-1]
                end_old, end_new = to_px(q[0], q[1]), plan_pts[-1]
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.MUTED))
                p.drawEllipse(end_old, r_px * 0.35, r_px * 0.35)
                p.setBrush(QColor(theme.PRIMARY))
                p.drawEllipse(end_new, r_px * 0.35, r_px * 0.35)
                self._tag(p, field, end_old + QPointF(0, r_px + 18), "first plan ended here")
                self._tag(p, field, end_new + QPointF(0, -r_px - 18), "now it reaches here")
        elif tour == "apply" and k < len(tr.u):
            self._tag(p, field, ball + QPointF(0, r_px * 1.6 + 20), f"u₀: applied for {tr.dt:g} s")

        # crash marker once the replay reaches the crash
        if tr.crash_point and self._t >= tr.duration - 1e-9:
            c = to_px(*tr.crash_point)
            p.setPen(QPen(QColor(theme.DANGER), max(2.5, r_px * 0.25), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            d = r_px * 0.6
            p.drawLine(c + QPointF(-d, -d), c + QPointF(d, d))
            p.drawLine(c + QPointF(-d, d), c + QPointF(d, -d))

        # wind arrow (top right), length ~ wind strength
        if self.show_wind and tr.disturbance:
            wx, wy = tr.disturbance[min(k, len(tr.disturbance) - 1)]
            mag = math.hypot(wx, wy)
            c = QPointF(field.right() - 44, field.top() + 44)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.qcolor(theme.SURFACE_ALT, 230))
            p.drawEllipse(c, 34, 34)
            if mag > 1e-3:
                d = QPointF(wx / mag, -wy / mag)
                L = 8 + 22 * min(1.0, mag / 1.0)
                a0, a1 = c - d * (L / 2), c + d * (L / 2)
                p.setPen(QPen(QColor(theme.BALL_DARK), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(a0, a1)
                n = QPointF(-d.y(), d.x())
                p.drawLine(a1, a1 - d * 7 + n * 5)
                p.drawLine(a1, a1 - d * 7 - n * 5)
            p.setPen(QColor(theme.INK_SOFT))
            p.setFont(theme.font(10, QFont.Weight.Bold))
            p.drawText(QRectF(c.x() - 34, c.y() + 18, 68, 14), Qt.AlignmentFlag.AlignHCenter,
                       f"wind {mag:.1f}")

        # HUD: the speed in a pill (the time is in the replay bar)
        text = f"|v| = {speed:.2f} m/s"
        p.setFont(theme.font(13, QFont.Weight.ExtraBold))
        tw = p.fontMetrics().horizontalAdvance(text) + 26
        painting.draw_pill(p, QRectF(field.left() + 12, field.top() + 12, tw, 28), text)

    @staticmethod
    def _tag(p: QPainter, field: QRectF, centre: QPointF, text: str) -> None:
        """A small label pill centred at `centre`, kept inside the field."""
        p.setFont(theme.font(12, QFont.Weight.ExtraBold))
        w, h = p.fontMetrics().horizontalAdvance(text) + 22, 26
        x = min(max(centre.x() - w / 2, field.left() + 6), field.right() - w - 6)
        y = min(max(centre.y() - h / 2, field.top() + 6), field.bottom() - h - 9)
        painting.draw_pill(p, QRectF(x, y, w, h), text, font_px=12)

    def _draw_waypoints(self, p: QPainter, to_px, start: QPointF, target: QPointF, r_px: float,
                        active: int | None) -> None:
        """Waypoints as numbered diamonds, with a faint line start -> 1 -> 2 -> ... -> target
        (the rough route the player gives the controller). During a replay the MPC's current
        reference is highlighted and reached waypoints are greyed."""
        if not self._waypoints:
            return
        pts = [to_px(*w) for w in self._waypoints]
        route = QPainterPath(start)
        for q in [*pts, target]:
            route.lineTo(q)
        pen = QPen(theme.qcolor(theme.WAYPOINT, 110), 2, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(route)
        for i, q in enumerate(pts):
            painting.draw_waypoint(p, q, r_px * 0.8, i + 1, active=active == i,
                                   done=active is not None and active > i)


def _ccw(corners):
    """Corners sorted counter-clockwise around their centroid (draws any 4-corner block)."""
    mx = sum(c[0] for c in corners) / len(corners)
    my = sum(c[1] for c in corners) / len(corners)
    return sorted(corners, key=lambda c: math.atan2(c[1] - my, c[0] - mx))
