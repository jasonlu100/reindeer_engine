"""Extra 2D visual nodes: lights, filled rectangles, polygons and lines.

These build on top of the existing :class:`Renderer2D` draw primitives
(``draw_light`` / ``draw_rect`` / ``draw_polygon`` / ``draw_line``) and are
discovered automatically by the editor's *Create Node* dialog because they
use the ``@register_node`` decorator.
"""
from __future__ import annotations

import math

from engine.core.math2d import Vector2, Color
from engine.core.node import (PropertyDef, PT_FLOAT, PT_BOOL, PT_COLOR,
                              PT_STRING)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("Visual")
class Light2D(Node2D):
    """An additive light source.  Draws a soft radial glow that accumulates
    with other lights (using ``QPainter``'s additive composition mode)."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("enabled", PT_BOOL, True, group="Light"),
        PropertyDef("radius", PT_FLOAT, 220.0, group="Light", min_value=1),
        PropertyDef("color", PT_COLOR, Color(1.0, 0.95, 0.8, 1.0), group="Light"),
        PropertyDef("energy", PT_FLOAT, 1.0, group="Light", min_value=0.0),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible and self.enabled:
            renderer.draw_light(self.get_global_position(), self.radius,
                               self.color, self.energy)
        super()._draw(renderer, camera)


@register_node("UI")
class ColorRect2D(Node2D):
    """A filled rectangle in world space - handy for backgrounds, panels and
    coloured UI elements."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("width", PT_FLOAT, 100.0, group="Rect", min_value=1),
        PropertyDef("height", PT_FLOAT, 100.0, group="Rect", min_value=1),
        PropertyDef("color", PT_COLOR, Color(0.2, 0.6, 0.9, 1.0), group="Rect"),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            renderer.draw_rect(self.get_global_position(),
                               Vector2(self.width, self.height), self.color,
                               math.radians(self.rotation))
        super()._draw(renderer, camera)


@register_node("Visual")
class Polygon2D(Node2D):
    """Draws a filled polygon from a list of local points.

    ``points`` is a newline/space separated list of ``x,y`` pairs in the
    node's local space.  If left empty a default triangle is used."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("points", PT_STRING, "0,-40 40,40 -40,40", group="Polygon",
                   hint="x,y per line"),
        PropertyDef("color", PT_COLOR, Color(0.9, 0.4, 0.5, 1.0), group="Polygon"),
        PropertyDef("outline", PT_COLOR, Color(1.0, 1.0, 1.0, 0.0),
                   group="Polygon"),
    ]

    def _local_points(self):
        pts = []
        for line in self.points.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            nums = []
            for p in parts:
                try:
                    nums.append(float(p))
                except ValueError:
                    pass
            for i in range(0, len(nums) - 1, 2):
                pts.append(Vector2(nums[i], nums[i + 1]))
        if not pts:
            pts = [Vector2(0, -40), Vector2(40, 40), Vector2(-40, 40)]
        return pts

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            gp = self.get_global_position()
            rot = math.radians(self.rotation)
            sc = self.get_global_scale()
            world = [gp + Vector2(p.x * sc.x, p.y * sc.y).rotated(rot)
                     for p in self._local_points()]
            renderer.draw_polygon(world, self.color, self.outline)
        super()._draw(renderer, camera)


@register_node("Visual")
class Line2D(Node2D):
    """Draws a straight line from the node origin to ``end`` (local space)."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("end", PT_STRING, "100,0", group="Line", hint="x,y"),
        PropertyDef("width", PT_FLOAT, 2.0, group="Line", min_value=1),
        PropertyDef("color", PT_COLOR, Color(1.0, 1.0, 1.0, 1.0), group="Line"),
    ]

    def _end_point(self):
        parts = self.end.replace(",", " ").split()
        try:
            return Vector2(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            return Vector2(100, 0)

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            gp = self.get_global_position()
            rot = math.radians(self.rotation)
            sc = self.get_global_scale()
            e = self._end_point()
            b = gp + Vector2(e.x * sc.x, e.y * sc.y).rotated(rot)
            renderer.draw_line(gp, b, self.color, self.width)
        super()._draw(renderer, camera)
