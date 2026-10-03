"""Collision shapes (colliders).

A :class:`Shape` knows how to produce its world-space geometry given a
transform so the narrow-phase collision code can work purely with world
coordinates.  Supported primitives: circles, axis-aligned-ish boxes and
arbitrary *convex* polygons.  (Concave shapes should be built from several
convex polygons in user code.)
"""
from __future__ import annotations

from typing import List

from engine.core.math2d import Vector2, Rect2


class Shape:
    """Base collider."""

    def aabb(self, pos: Vector2, angle: float, scale: Vector2) -> Rect2:
        raise NotImplementedError

    def world_vertices(self, pos: Vector2, angle: float, scale: Vector2) -> List[Vector2]:
        raise NotImplementedError

    def world_center(self, pos: Vector2, angle: float, scale: Vector2) -> Vector2:
        return Vector2(pos.x, pos.y)


class CircleShape(Shape):
    def __init__(self, radius: float = 16.0):
        self.radius = float(radius)

    def aabb(self, pos, angle, scale):
        r = self.radius * max(scale.x, scale.y)
        return Rect2(pos.x - r, pos.y - r, r * 2, r * 2)

    def world_vertices(self, pos, angle, scale):
        return [Vector2(pos.x, pos.y)]  # point-less for circle; solver handles it

    def scaled_radius(self, scale: Vector2) -> float:
        return self.radius * max(scale.x, scale.y)


class RectangleShape(Shape):
    """Box centered on the origin (width x height)."""

    def __init__(self, width: float = 32.0, height: float = 32.0):
        self.width = float(width)
        self.height = float(height)

    def aabb(self, pos, angle, scale):
        hw = self.width * scale.x * 0.5
        hh = self.height * scale.y * 0.5
        c, s = pos.x, pos.y
        # axis-aligned bound of rotated box
        ext = abs(hw * abs_cos(angle)) + abs(hh * abs_sin(angle))
        return Rect2(c - ext, s - ext, ext * 2, ext * 2)

    def world_vertices(self, pos, angle, scale):
        hw = self.width * scale.x * 0.5
        hh = self.height * scale.y * 0.5
        local = [Vector2(-hw, -hh), Vector2(hw, -hh),
                 Vector2(hw, hh), Vector2(-hw, hh)]
        return [v.rotated(angle) + pos for v in local]


class PolygonShape(Shape):
    """Convex polygon described by local-space points."""

    def __init__(self, points: List[Vector2] = None):
        self.points = points or [Vector2(-16, -16), Vector2(16, -16),
                                 Vector2(16, 16), Vector2(-16, 16)]

    def aabb(self, pos, angle, scale):
        verts = self.world_vertices(pos, angle, scale)
        r = Rect2(verts[0].x, verts[0].y, 0, 0)
        for v in verts[1:]:
            r = r.expanded(v)
        return r

    def world_vertices(self, pos, angle, scale):
        return [v * scale for v in [p.rotated(angle) + pos for p in self.points]]


def abs_cos(a: float) -> float:
    import math
    return abs(math.cos(a))


def abs_sin(a: float) -> float:
    import math
    return abs(math.sin(a))
