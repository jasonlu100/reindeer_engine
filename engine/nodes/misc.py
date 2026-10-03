"""Misc helper nodes: Position2D marker and CanvasLayer container."""
from __future__ import annotations

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_INT
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D
from engine.core.node import Node


@register_node("Node2D")
class Position2D(Node2D):
    """An empty transform marker (spawn points, pivots, waypoints)."""
    pass


@register_node("Node")
class CanvasLayer(Node):
    """A container that groups 2D content into a separate rendering layer.

    Children added under a CanvasLayer are rendered with the layer's
    ``layer`` offset applied, letting the editor/renderer put HUD content
    above the world regardless of scene hierarchy depth.
    """
    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("layer", PT_INT, 1, group="CanvasLayer", min_value=-32,
                    max_value=32),
    ]
