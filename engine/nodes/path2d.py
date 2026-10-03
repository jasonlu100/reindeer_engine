"""Path nodes: a polyline the editor/renderer can draw, and a follower that
moves a node along it.

:class:`Path2D` stores a list of points (local space) and draws a connected
line.  :class:`PathFollow2D` is typically added as a *child* of a Path2D and
advances its own ``position`` along the parent's points at ``speed`` (looping
or clamping at the ends).
"""
from __future__ import annotations

import math

from engine.core.math2d import Vector2, Color
from engine.core.node import PropertyDef, PT_STRING, PT_FLOAT, PT_BOOL
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


def _parse_points(text: str):
    pts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.replace(",", " ").split()
        if len(parts) >= 2:
            try:
                pts.append(Vector2(float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    if len(pts) < 2:
        pts = [Vector2(0, 0), Vector2(100, 0)]
    return pts


@register_node("Node2D")
class Path2D(Node2D):
    """Holds a polyline of points and renders it as a guide curve."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("points", PT_STRING, "0,0 100,0 100,100 0,100",
                   group="Path", hint="x,y per line"),
    ]

    def get_points(self):
        return _parse_points(self.points)

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            pts = self.get_points()
            base = self.get_global_position()
            for i in range(len(pts) - 1):
                a = base + pts[i]
                b = base + pts[i + 1]
                renderer.draw_line(a, b, Color(0.4, 0.7, 1.0, 0.85), 2.0)
        super()._draw(renderer, camera)


@register_node("Node2D")
class PathFollow2D(Node2D):
    """Moves along the points of a parent (or ancestor) :class:`Path2D`."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("speed", PT_FLOAT, 60.0, group="Path", min_value=0.0),
        PropertyDef("loop", PT_BOOL, True, group="Path"),
        PropertyDef("rotates", PT_BOOL, False, group="Path"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._dist = 0.0

    def _find_path(self):
        node = self.parent
        while node is not None:
            if type(node).__name__ == "Path2D":
                return node
            node = node.parent
        return None

    @staticmethod
    def _path_length(pts):
        total = 0.0
        for i in range(len(pts) - 1):
            total += (pts[i + 1] - pts[i]).length()
        return total

    @staticmethod
    def _point_at(pts, total, dist):
        rem = dist
        for i in range(len(pts) - 1):
            seg = pts[i + 1] - pts[i]
            length = seg.length()
            if rem <= length or i == len(pts) - 2:
                t = (rem / length) if length > 0 else 0.0
                return pts[i] + seg * t, math.atan2(seg.y, seg.x)
            rem -= length
        return pts[-1], 0.0

    def _process(self, delta: float) -> None:
        path = self._find_path()
        if path is None:
            return
        pts = path.get_points()
        total = self._path_length(pts)
        if total <= 0:
            return
        self._dist += self.speed * delta
        if self.loop:
            self._dist %= total
        else:
            self._dist = min(self._dist, total)
        pos, angle = self._point_at(pts, total, self._dist)
        # PathFollow2D lives in the Path2D's local space, so the point itself
        # is already the correct local position.
        self.position = pos
        if self.rotates:
            self.rotation = math.degrees(angle)
