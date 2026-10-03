"""Rigid bodies.

A :class:`RigidBody` is the pure-simulation counterpart of a
``RigidBody2D`` node.  It stores position / orientation / velocity / mass and
the collider shape, and knows how to copy its transform to and from the
owning node.  The :class:`~engine.physics.world.PhysicsWorld` steps every
body and resolves their contacts.
"""
from __future__ import annotations

import math
from typing import Optional

from engine.core.math2d import Vector2, Rect2
from engine.physics.collider import CircleShape, RectangleShape, PolygonShape
from engine.physics.material import PhysicsMaterial, DEFAULT_MATERIAL


class RigidBody:
    DYNAMIC = 0
    STATIC = 1
    KINEMATIC = 2

    def __init__(self, shape=None, position: Vector2 = None,
                 body_type: int = DYNAMIC, node=None):
        self.shape = shape
        self.position = position or Vector2(0, 0)
        self.angle = 0.0          # radians
        self.velocity = Vector2(0, 0)
        self.angular_velocity = 0.0
        self.linear_damping = 0.1
        self.angular_damping = 0.1
        self.gravity_scale = 1.0
        self.body_type = body_type
        self.scale = Vector2(1, 1)
        self.material: PhysicsMaterial = DEFAULT_MATERIAL
        self.node = node
        self.mass = 1.0
        self.inv_mass = 1.0
        self.inertia = 1.0
        self.inv_inertia = 1.0
        self._aabb: Optional[Rect2] = None
        self._aabb_dirty = True
        self.sleeping = False
        self._recompute_mass()

    # ------------------------------------------------------------------
    def set_body_type(self, t: int) -> None:
        self.body_type = t
        if t == self.STATIC:
            self.inv_mass = 0.0
            self.inv_inertia = 0.0
            self.velocity = Vector2(0, 0)
            self.angular_velocity = 0.0

    def set_mass(self, m: float) -> None:
        self.mass = m
        self._recompute_mass()

    def _recompute_mass(self) -> None:
        if self.body_type == self.STATIC:
            self.inv_mass = 0.0
            self.inv_inertia = 0.0
            return
        m = self.mass if self.mass > 0 else 1.0
        self.inv_mass = 1.0 / m
        s = self.shape
        if isinstance(s, CircleShape):
            I = 0.5 * m * s.radius * s.radius
        elif isinstance(s, RectangleShape):
            I = m * (s.width * s.width + s.height * s.height) / 12.0
        elif isinstance(s, PolygonShape):
            # approximate with bounding box of the polygon
            r = s.aabb(self.position, 0, Vector2(1, 1))
            I = m * (r.w * r.w + r.h * r.h) / 12.0
        else:
            I = m
        self.inertia = I
        self.inv_inertia = 1.0 / I if I > 0 else 0.0

    # ------------------------------------------------------------------
    def get_aabb(self, scale: Vector2 = None) -> Rect2:
        if self.shape is None:
            return Rect2(self.position.x, self.position.y, 0, 0)
        sc = scale or Vector2(1, 1)
        if self._aabb_dirty or scale is not None:
            self._aabb = self.shape.aabb(self.position, self.angle, sc)
            self._aabb_dirty = False
        return self._aabb

    def apply_impulse(self, impulse: Vector2, contact: Vector2) -> None:
        if self.inv_mass == 0.0:
            return
        self.velocity += impulse * self.inv_mass
        r = contact - self.position
        self.angular_velocity += self.inv_inertia * r.cross(impulse)

    def apply_force(self, force: Vector2) -> None:
        # accumulates into velocity during the step
        if self.inv_mass == 0.0:
            return
        self.velocity += force * self.inv_mass

    # ------------------------------------------------------------------
    # transform sync with the owning node
    # ------------------------------------------------------------------
    def sync_from_node(self, pos: Vector2, rotation_deg: float, scale: Vector2,
                       shape) -> None:
        self.position = Vector2(pos.x, pos.y)
        self.angle = math.radians(rotation_deg)
        self.scale = scale
        if shape is not None:
            self.shape = shape
            self._aabb_dirty = True
            self._recompute_mass()

    def sync_to_node(self) -> None:
        if self.node is None:
            return
        self.node.position = Vector2(self.position.x, self.position.y)
        self.node.rotation = math.degrees(self.angle)
