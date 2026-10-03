"""RigidBody2D: a dynamic/static/kinematic physics body.

The node owns a :class:`engine.physics.body.RigidBody`.  On its first
physics tick it gathers colliders from any child ``CollisionShape2D`` nodes,
creates the simulation body and registers it with the world.  For dynamic
bodies the simulation drives the node's transform; for static/kinematic
bodies the node's transform drives the simulation.
"""
from __future__ import annotations

import math

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_ENUM, PT_FLOAT, PT_BOOL
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D
from engine.physics.body import RigidBody
from engine.physics.material import PhysicsMaterial


@register_node("Physics")
class RigidBody2D(Node2D):
    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("body_type", PT_ENUM, "dynamic", group="Physics",
                    options=["dynamic", "static", "kinematic"]),
        PropertyDef("mass", PT_FLOAT, 1.0, group="Physics", min_value=0.001),
        PropertyDef("gravity_scale", PT_FLOAT, 1.0, group="Physics"),
        PropertyDef("linear_damping", PT_FLOAT, 0.1, group="Physics"),
        PropertyDef("angular_damping", PT_FLOAT, 0.1, group="Physics"),
        PropertyDef("restitution", PT_FLOAT, 0.2, group="Physics"),
        PropertyDef("friction", PT_FLOAT, 0.5, group="Physics"),
        PropertyDef("can_sleep", PT_BOOL, True, group="Physics"),
    ]

    # body type name -> RigidBody constant
    _TYPE_MAP = {"dynamic": RigidBody.DYNAMIC,
                 "static": RigidBody.STATIC,
                 "kinematic": RigidBody.KINEMATIC}

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._body = None
        self._initialized = False

    # ------------------------------------------------------------------
    def _init_body(self) -> None:
        # collect a collider from child CollisionShape2D nodes
        shape = None
        for child in self.children:
            cs = child
            t = type(cs).__name__
            if t == "CollisionShape2D" and not getattr(cs, "disabled", False):
                shape = cs.build_shape()
                break
        if shape is None:
            from engine.physics.collider import RectangleShape
            shape = RectangleShape(32, 32)

        bt = self._TYPE_MAP.get(self.body_type, RigidBody.DYNAMIC)

        # The physics world is supplied by the engine's SceneTree.  Some
        # contexts (notably the editor's edit-mode preview) run node callbacks
        # on scenes that are NOT attached to an Engine/SceneTree, so no physics
        # world exists.  In that case we skip body creation instead of crashing
        # and simply mark the node initialised with no body.
        if self.tree is None or self.tree.physics is None:
            self._body = None
            self._initialized = True
            return

        world = self.tree.physics
        body = world.create_body(shape=shape,
                                 position=self.get_global_position(),
                                 body_type=bt,
                                 node=self)
        body.mass = self.mass
        body.linear_damping = self.linear_damping
        body.angular_damping = self.angular_damping
        body.gravity_scale = self.gravity_scale
        body.material = PhysicsMaterial(self.restitution, self.friction,
                                        name=self.name)
        body.set_body_type(bt)
        self._body = body
        world.add_body(body)
        self._initialized = True

    def _physics_process(self, delta: float) -> None:
        if not self._initialized:
            self._init_body()
            return
        body = self._body
        if body is None:
            # no physics world available (e.g. editor preview) -> nothing to do
            return
        if body.body_type == RigidBody.DYNAMIC:
            # the world already integrated this body this frame -> read it back
            self.position = Vector2(body.position.x, body.position.y)
            self.rotation = math.degrees(body.angle)
        else:
            # static/kinematic: drive the simulation from the node transform
            body.sync_from_node(self.get_global_position(), self.rotation,
                                self.scale, body.shape)

    def _exit_tree(self) -> None:
        if self._body is not None and self.tree is not None \
                and self.tree.physics is not None:
            self.tree.physics.remove_body(self._body)
        self._body = None
        self._initialized = False
        super()._exit_tree()

    # ------------------------------------------------------------------
    # physics API for scripts
    # ------------------------------------------------------------------
    def get_body(self):
        return self._body

    def apply_central_impulse(self, impulse: Vector2) -> None:
        if self._body:
            self._body.apply_impulse(impulse, self._body.position)

    def apply_impulse(self, impulse: Vector2, point: Vector2) -> None:
        if self._body:
            self._body.apply_impulse(impulse, point)

    def set_linear_velocity(self, v: Vector2) -> None:
        if self._body:
            self._body.velocity = Vector2(v.x, v.y)

    def get_linear_velocity(self) -> Vector2:
        if self._body:
            return Vector2(self._body.velocity.x, self._body.velocity.y)
        return Vector2(0, 0)

    def set_angular_velocity(self, w: float) -> None:
        if self._body:
            self._body.angular_velocity = w

    def get_angular_velocity(self) -> float:
        return self._body.angular_velocity if self._body else 0.0

    def set_position(self, p: Vector2) -> None:
        self.position = Vector2(p.x, p.y)
        if self._body:
            self._body.position = Vector2(p.x, p.y)
