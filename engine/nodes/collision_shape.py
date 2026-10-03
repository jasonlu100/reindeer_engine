"""CollisionShape2D: defines a collider attached to a physics body."""
from __future__ import annotations

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_ENUM, PT_FLOAT, PT_BOOL
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D
from engine.physics.collider import CircleShape, RectangleShape, PolygonShape


@register_node("Physics")
class CollisionShape2D(Node2D):
    """Holds a collision primitive.  A :class:`RigidBody2D` or
    :class:`Area2D` collects its child ``CollisionShape2D`` nodes to build
    its physics colliders."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("shape_type", PT_ENUM, "rect", group="Shape",
                    options=["rect", "circle", "polygon"]),
        PropertyDef("width", PT_FLOAT, 32.0, group="Shape", min_value=1),
        PropertyDef("height", PT_FLOAT, 32.0, group="Shape", min_value=1),
        PropertyDef("radius", PT_FLOAT, 16.0, group="Shape", min_value=1),
        PropertyDef("disabled", PT_BOOL, False, group="Shape"),
    ]

    def build_shape(self):
        t = self.shape_type
        if t == "circle":
            return CircleShape(self.radius)
        if t == "polygon":
            hw, hh = self.width * 0.5, self.height * 0.5
            return PolygonShape([Vector2(-hw, -hh), Vector2(hw, -hh),
                                 Vector2(hw, hh), Vector2(-hw, hh)])
        return RectangleShape(self.width, self.height)

    def _draw(self, renderer, camera) -> None:
        if getattr(renderer, "show_collision_shapes", False) and not self.disabled:
            renderer.draw_collision_shape(self)
        super()._draw(renderer, camera)
