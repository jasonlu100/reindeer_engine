"""Base 2D node: transform + global-transform composition."""
from __future__ import annotations

import math

from engine.core.math2d import Vector2, Color
from engine.core.node import Node, PropertyDef, PT_VECTOR2, PT_FLOAT, PT_INT, \
    PT_COLOR
from engine.core.registry import register_node


@register_node("Node2D")
class Node2D(Node):
    """Base class for everything positioned in 2D space."""

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("position", PT_VECTOR2, Vector2(0, 0), group="Transform"),
        PropertyDef("rotation", PT_FLOAT, 0.0, group="Transform",
                    hint="degrees"),
        PropertyDef("scale", PT_VECTOR2, Vector2(1, 1), group="Transform"),
        PropertyDef("modulate", PT_COLOR, Color(1, 1, 1, 1), group="Material"),
        PropertyDef("z_index", PT_INT, 0, group="Material", min_value=-128,
                    max_value=127),
    ]

    # ------------------------------------------------------------------
    def _global_xform(self):
        if self.parent is None or not isinstance(self.parent, Node2D):
            return (Vector2(self.position.x, self.position.y),
                    math.radians(self.rotation),
                    Vector2(self.scale.x, self.scale.y))
        ppos, prot, pscale = self.parent._global_xform()
        local = Vector2(self.position.x * pscale.x,
                        self.position.y * pscale.y).rotated(prot) + ppos
        rot = prot + math.radians(self.rotation)
        scale = Vector2(pscale.x * self.scale.x, pscale.y * self.scale.y)
        return local, rot, scale

    def get_global_position(self) -> Vector2:
        return self._global_xform()[0]

    def get_global_rotation(self) -> float:
        return self._global_xform()[1]

    def get_global_scale(self) -> Vector2:
        return self._global_xform()[2]

    def get_global_transform_matrix(self):
        return self._global_xform()

    def move_local(self, delta: Vector2) -> None:
        self.position = self.position + delta

    def _draw(self, renderer, camera) -> None:
        for inst in self._script_instances:
            fn = getattr(inst, "_draw", None)
            if fn is not None:
                fn(renderer, camera)
