"""Placing waypoints on the map with the mouse (PRD 7, Level 3).

    editor = WaypointEditor(map_view, max_count=3)
    editor.changed.connect(...)     # list of (x, y) in metres, in route order
    editor.rejected.connect(...)    # short reason, e.g. "inside an obstacle ellipse"

Left click on the field: add a waypoint (appended to the route). Drag a waypoint to
move it, right-click it to delete it. Points inside an obstacle ellipse or off the
field are rejected (the engine checks again).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal

from .map_view import MapView

GRAB_PX = 1.4  # grab radius, in waypoint radii


class WaypointEditor(QObject):
    changed = Signal(list)
    rejected = Signal(str)

    def __init__(self, view: MapView, max_count: int):
        super().__init__(view)
        self.view, self.max_count = view, max_count
        self._points: list[tuple[float, float]] = []
        self._drag: int | None = None
        self._enabled = True
        view.setMouseTracking(True)
        view.installEventFilter(self)

    # --- API ------------------------------------------------------------------------------
    @property
    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def set_points(self, points) -> None:
        self._points = [(round(x, 1), round(y, 1)) for x, y in points][: self.max_count]
        self.view.set_waypoints(self._points)
        self.changed.emit(self.points)

    def clear(self) -> None:
        self.set_points([])

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._drag = None

    # --- mouse ----------------------------------------------------------------------------
    def _valid(self, w) -> str:
        if w is None:
            return "outside the field"
        if any(e.contains(*w) for e in self.view.ellipses):
            return "inside an obstacle ellipse (dashed): the solver could never reach it"
        return ""

    def _hit(self, pos: QPointF) -> int | None:
        r = self.view.ball_radius_px() * 0.8 * GRAB_PX
        for i in reversed(range(len(self._points))):
            d = self.view.to_screen(*self._points[i]) - pos
            if d.x() ** 2 + d.y() ** 2 <= r * r:
                return i
        return None

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if obj is not self.view or not self._enabled:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            pos = event.position()
            i = self._hit(pos)
            if event.button() == Qt.MouseButton.RightButton:
                if i is not None:
                    del self._points[i]
                    self.set_points(self._points)
                return True
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            if i is not None:
                self._drag = i
                return True
            w = self.view.to_world(pos)
            if len(self._points) >= self.max_count:
                self.rejected.emit(f"At most {self.max_count} waypoints: drag one or right-click to "
                                   "delete it.")
            elif reason := self._valid(w):
                self.rejected.emit(f"Can't place a waypoint there: {reason}.")
            else:
                self.set_points([*self._points, w])
            return True
        if kind == QEvent.Type.MouseMove:
            pos = event.position()
            if self._drag is not None:
                w = self.view.to_world(pos)
                if not self._valid(w):  # keep the last valid position while dragging
                    self._points[self._drag] = (round(w[0], 1), round(w[1], 1))
                    self.view.set_waypoints(self._points)
                return True
            hover = self._hit(pos) is not None
            self.view.setCursor(Qt.CursorShape.OpenHandCursor if hover else Qt.CursorShape.CrossCursor)
            return False
        if kind == QEvent.Type.MouseButtonRelease and self._drag is not None:
            self._drag = None
            self.set_points(self._points)
            return True
        return False
