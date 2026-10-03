"""UI / text nodes."""
from __future__ import annotations

from engine.core.math2d import Vector2, Color
from engine.core.node import (PropertyDef, PT_STRING, PT_INT, PT_COLOR,
                              PT_ENUM)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("UI")
class Label(Node2D):
    """Draws a line of text."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("text", PT_STRING, "Label", group="Label"),
        PropertyDef("font_size", PT_INT, 16, group="Label", min_value=6,
                    max_value=128),
        PropertyDef("color", PT_COLOR, Color(1, 1, 1, 1), group="Label"),
        PropertyDef("align", PT_ENUM, "left", group="Label",
                    options=["left", "center", "right"]),
        PropertyDef("outline_color", PT_COLOR, Color(0, 0, 0, 0), group="Label"),
        PropertyDef("outline_size", PT_INT, 0, group="Label", min_value=0,
                    max_value=16),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            renderer.draw_text(self.get_global_position(), self.text,
                               self.color, self.font_size, self.align,
                               self.outline_color, self.outline_size)
        super()._draw(renderer, camera)


@register_node("UI")
class Node2DHelper(Node2D):
    """Marker node (empty 2D transform helper). Useful as a pivot / spawner."""
    pass
