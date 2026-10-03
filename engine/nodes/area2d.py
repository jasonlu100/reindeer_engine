"""Area2D: a region that detects overlaps (no physical response).

Emits ``body_entered`` / ``body_exited`` and ``area_entered`` / ``area_exited``
signals, which scripts use for triggers, hit-boxes, pickups and zones.  The
area collects colliders from child ``CollisionShape2D`` nodes and tests them
against the physics world each physics tick.
"""
from __future__ import annotations

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_BOOL
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D
from engine.physics.collision import collide


@register_node("Physics")
class Area2D(Node2D):
    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("monitoring", PT_BOOL, True, group="Area"),
        PropertyDef("monitorable", PT_BOOL, True, group="Area"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("body_entered")
        self.add_signal("body_exited")
        self.add_signal("area_entered")
        self.add_signal("area_exited")
        self._shapes = []
        self._overlapping = {}   # node_id -> node

    def _collect_shapes(self):
        self._shapes = []
        for child in self.children:
            if type(child).__name__ == "CollisionShape2D" and \
                    not getattr(child, "disabled", False):
                self._shapes.append((child, child.build_shape()))

    def _physics_process(self, delta: float) -> None:
        if not self.monitoring:
            return
        if not self._shapes:
            self._collect_shapes()
        if not self._shapes:
            return
        world = self.tree.physics if self.tree else None
        if world is None:
            return

        now = {}
        # test against every registered body
        for body in world.bodies:
            if body.shape is None or body.node is None:
                continue
            for cshape, shape in self._shapes:
                m = collide(shape, cshape.get_global_position(),
                            math_radians(cshape.rotation), cshape.scale,
                            body.shape, body.position, body.angle, body.scale)
                if m is not None:
                    now[id(body.node)] = body.node
                    break
        # test against other areas
        for node in self.tree.get_nodes_by_type(type(self)):
            if node is self or not node.monitorable:
                continue
            for cshape, shape in self._shapes:
                for ocshape, oshape in node._shapes:
                    m = collide(shape, cshape.get_global_position(),
                                math_radians(cshape.rotation), cshape.scale,
                                oshape, ocshape.get_global_position(),
                                math_radians(ocshape.rotation), ocshape.scale)
                    if m is not None:
                        now[id(node)] = node
                        break

        # emit enter/exit
        for nid, node in now.items():
            if nid not in self._overlapping:
                self._overlapping[nid] = node
                if type(node).__name__ == "RigidBody2D":
                    self.emit("body_entered", node)
                else:
                    self.emit("area_entered", node)
        for nid in list(self._overlapping.keys()):
            if nid not in now:
                node = self._overlapping.pop(nid)
                if type(node).__name__ == "RigidBody2D":
                    self.emit("body_exited", node)
                else:
                    self.emit("area_exited", node)


def math_radians(deg: float) -> float:
    import math
    return math.radians(deg)
