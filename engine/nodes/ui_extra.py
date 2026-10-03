"""Extra UI nodes: clickable buttons and progress bars.

These are 2D control nodes rendered with the shared :class:`Renderer2D`
primitives.  ``Button2D`` performs hit-testing in play mode using the active
camera and the renderer's viewport size (both available through the engine),
emitting a ``pressed`` signal that scripts can connect to.
"""
from __future__ import annotations

import math

from engine.core.math2d import Vector2, Color
from engine.core.node import (PropertyDef, PT_FLOAT, PT_BOOL, PT_COLOR,
                              PT_STRING)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("UI")
class Button2D(Node2D):
    """A clickable rectangle button with a centred label."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("text", PT_STRING, "Button", group="Button"),
        PropertyDef("width", PT_FLOAT, 120.0, group="Button", min_value=1),
        PropertyDef("height", PT_FLOAT, 40.0, group="Button", min_value=1),
        PropertyDef("color", PT_COLOR, Color(0.2, 0.5, 0.85, 1.0), group="Button"),
        PropertyDef("text_color", PT_COLOR, Color(1.0, 1.0, 1.0, 1.0),
                   group="Button"),
        PropertyDef("disabled", PT_BOOL, False, group="Button"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("pressed")

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            renderer.draw_rect(self.get_global_position(),
                               Vector2(self.width, self.height), self.color,
                               math.radians(self.rotation))
            # approximate centred label
            label_pos = self.get_global_position() + Vector2(0, -6)
            renderer.draw_text(label_pos, self.text, self.text_color, 16)
        super()._draw(renderer, camera)

    def _input(self, event: dict) -> None:
        if self.disabled or not self.visible:
            return
        # left mouse button released -> trigger if the pointer is inside
        if event.get("type") == "mouse" and not event.get("pressed") \
                and event.get("button") == 1:
            pos = event.get("pos")
            if pos is not None and self._hit_test(pos):
                self.emit("pressed")

    def _hit_test(self, screen_pos) -> bool:
        engine = self.tree.engine if self.tree is not None else None
        renderer = getattr(engine, "renderer", None) if engine else None
        camera = self.tree.find_camera() if self.tree is not None else None
        if renderer is None or camera is None:
            return False
        world = camera.screen_to_world(screen_pos, renderer.viewport_w,
                                       renderer.viewport_h)
        gp = self.get_global_position()
        hw, hh = self.width / 2.0, self.height / 2.0
        return (gp.x - hw <= world.x <= gp.x + hw and
                gp.y - hh <= world.y <= gp.y + hh)


@register_node("UI")
class ProgressBar(Node2D):
    """A horizontal progress bar rendered from ``value`` / ``max_value``."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("value", PT_FLOAT, 50.0, group="Progress", min_value=0.0),
        PropertyDef("max_value", PT_FLOAT, 100.0, group="Progress",
                   min_value=0.001),
        PropertyDef("width", PT_FLOAT, 200.0, group="Progress", min_value=1),
        PropertyDef("height", PT_FLOAT, 20.0, group="Progress", min_value=1),
        PropertyDef("bg_color", PT_COLOR, Color(0.15, 0.15, 0.18, 1.0),
                   group="Progress"),
        PropertyDef("fill_color", PT_COLOR, Color(0.3, 0.8, 0.4, 1.0),
                   group="Progress"),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            gp = self.get_global_position()
            renderer.draw_rect(gp, Vector2(self.width, self.height),
                               self.bg_color, 0.0)
            ratio = max(0.0, min(1.0, self.value / self.max_value))
            fill_w = self.width * ratio
            if fill_w > 0:
                fill_center = gp + Vector2(-self.width / 2.0 + fill_w / 2.0, 0)
                renderer.draw_rect(fill_center,
                                   Vector2(fill_w, self.height),
                                   self.fill_color, 0.0)
        super()._draw(renderer, camera)
