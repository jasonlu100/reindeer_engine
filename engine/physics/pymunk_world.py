"""Optional pymunk physics backend (drop-in alternative to the built-in solver).

The node layer (``RigidBody2D`` / ``Area2D``) only ever talks to the world
through the tiny surface the built-in :class:`~engine.physics.world.PhysicsWorld`
exposes -- ``create_body`` / ``add_body`` / ``remove_body`` / ``step`` and a
``body`` object exposing ``position`` / ``angle`` / ``velocity`` /
``sync_to_node`` / ``apply_impulse`` / ``set_body_type`` / ``get_aabb`` plus the
built-in ``shape`` collider used by :func:`engine.physics.collision.collide`.

:class:`PymunkWorld` and :class:`PymunkBody` implement exactly that surface on
top of `pymunk <https://pymunk.org>`_, so enabling "precise" physics is purely a
project-config flag (``physics_backend: "pymunk"``) and requires no changes to
game code.  pymunk is imported lazily so the default backend never depends on it.
"""
from __future__ import annotations

import math
from typing import List

from engine.core.math2d import Vector2, Rect2
from engine.physics.body import RigidBody          # body-type constants
from engine.physics.collider import (CircleShape, RectangleShape, PolygonShape)
from engine.physics.material import PhysicsMaterial


class PymunkBody:
    """A pymunk-backed physics body presented through the built-in body API."""

    DYNAMIC = RigidBody.DYNAMIC
    STATIC = RigidBody.STATIC
    KINEMATIC = RigidBody.KINEMATIC

    def __init__(self, shape, position, body_type, node, world):
        import pymunk
        self._pymunk = pymunk
        self.world = world
        self.node = node
        self.shape = shape                      # built-in collider (Area2D/collide)
        self.body_type = body_type
        self.scale = Vector2(1, 1)
        self.material = PhysicsMaterial(0.2, 0.5)
        self.gravity_scale = 1.0
        self.linear_damping = 0.1
        self.angular_damping = 0.1
        self.sleeping = False

        self._pos = Vector2(position.x if position is not None else 0.0,
                            position.y if position is not None else 0.0)
        self._angle = 0.0
        self._vel = Vector2(0.0, 0.0)
        self._av = 0.0
        self._mass = 1.0
        self._aabb = None

        bt = self._pm_body_type(body_type)
        if bt == pymunk.Body.STATIC:
            self._pmbody = pymunk.Body(body_type=bt)
        else:
            moment = self._moment_for(shape, self._mass, self.scale)
            self._pmbody = pymunk.Body(self._mass, moment, body_type=bt)
        self._pmbody.position = (self._pos.x, self._pos.y)
        self._pmshape = self._build_pm_shape(shape, self.scale)
        self._pmshape.friction = self.material.friction
        self._pmshape.elasticity = self.material.restitution

    # ------------------------------------------------------------------
    # pymunk construction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _pm_body_type(bt: int):
        import pymunk
        if bt == RigidBody.STATIC:
            return pymunk.Body.STATIC
        if bt == RigidBody.KINEMATIC:
            return pymunk.Body.KINEMATIC
        return pymunk.Body.DYNAMIC

    def _moment_for(self, shape, mass, scale):
        import pymunk
        m = mass if mass > 0 else 1.0
        if isinstance(shape, CircleShape):
            return pymunk.moment_for_circle(m, 0,
                                           shape.radius * max(scale.x, scale.y))
        if isinstance(shape, RectangleShape):
            return pymunk.moment_for_box(m, (shape.width * scale.x,
                                            shape.height * scale.y))
        if isinstance(shape, PolygonShape):
            pts = [(p.x * scale.x, p.y * scale.y) for p in shape.points]
            return pymunk.moment_for_poly(m, pts)
        return m

    def _build_pm_shape(self, shape, scale):
        import pymunk
        if isinstance(shape, CircleShape):
            return pymunk.Circle(self._pmbody,
                                shape.radius * max(scale.x, scale.y))
        if isinstance(shape, RectangleShape):
            return pymunk.Poly.create_box(
                self._pmbody, (shape.width * scale.x, shape.height * scale.y))
        if isinstance(shape, PolygonShape):
            pts = [(p.x * scale.x, p.y * scale.y) for p in shape.points]
            return pymunk.Poly(self._pmbody, pts)
        return pymunk.Poly.create_box(self._pmbody, (1.0, 1.0))

    # ------------------------------------------------------------------
    # transform / velocity proxies
    # ------------------------------------------------------------------
    @property
    def position(self) -> Vector2:
        if self._pmbody is not None:
            return Vector2(self._pmbody.position.x, self._pmbody.position.y)
        return self._pos

    @position.setter
    def position(self, v: Vector2) -> None:
        self._pos = Vector2(v.x, v.y)
        if self._pmbody is not None:
            self._pmbody.position = (v.x, v.y)

    @property
    def angle(self) -> float:
        return self._pmbody.angle if self._pmbody is not None else self._angle

    @angle.setter
    def angle(self, a: float) -> None:
        self._angle = a
        if self._pmbody is not None:
            self._pmbody.angle = a

    @property
    def velocity(self) -> Vector2:
        if self._pmbody is not None:
            return Vector2(self._pmbody.velocity.x, self._pmbody.velocity.y)
        return self._vel

    @velocity.setter
    def velocity(self, v: Vector2) -> None:
        self._vel = Vector2(v.x, v.y)
        if self._pmbody is not None:
            self._pmbody.velocity = (v.x, v.y)

    @property
    def angular_velocity(self) -> float:
        return self._pmbody.angular_velocity if self._pmbody is not None else self._av

    @angular_velocity.setter
    def angular_velocity(self, w: float) -> None:
        self._av = w
        if self._pmbody is not None:
            self._pmbody.angular_velocity = w

    @property
    def mass(self) -> float:
        return self._pmbody.mass if self._pmbody is not None else self._mass

    @mass.setter
    def mass(self, m: float) -> None:
        self._mass = m
        if self._pmbody is not None and self.body_type != self.STATIC:
            self._pmbody.mass = m
            self._pmbody.moment = self._moment_for(self.shape, m, self.scale)

    @property
    def inv_mass(self) -> float:
        m = self._pmbody.mass if self._pmbody is not None else self._mass
        return 1.0 / m if m > 0 else 0.0

    @property
    def inertia(self) -> float:
        return self._pmbody.moment if self._pmbody is not None else 1.0

    @property
    def inv_inertia(self) -> float:
        I = self._pmbody.moment if self._pmbody is not None else 1.0
        return 1.0 / I if I > 0 else 0.0

    # ------------------------------------------------------------------
    def set_body_type(self, t: int) -> None:
        self.body_type = t
        if self._pmbody is None:
            return
        self._pmbody.body_type = self._pm_body_type(t)
        if t == self.STATIC:
            self._pmbody.velocity = (0.0, 0.0)
            self._pmbody.angular_velocity = 0.0

    def set_mass(self, m: float) -> None:
        self.mass = m

    def get_aabb(self, scale: Vector2 = None) -> Rect2:
        sc = scale if scale is not None else self.scale
        if self.shape is None:
            p = self.position
            return Rect2(p.x, p.y, 0, 0)
        return self.shape.aabb(self.position, self.angle, sc)

    def apply_impulse(self, impulse: Vector2, contact: Vector2) -> None:
        if self._pmbody is None:
            return
        if self._pmbody.body_type == self._pymunk.Body.STATIC:
            return
        off = (contact.x - self._pmbody.position.x,
               contact.y - self._pmbody.position.y)
        self._pmbody.apply_impulse((impulse.x, impulse.y), off)

    def apply_force(self, force: Vector2) -> None:
        if self._pmbody is None:
            return
        if self._pmbody.body_type == self._pymunk.Body.STATIC:
            return
        self._pmbody.force = (self._pmbody.force.x + force.x,
                              self._pmbody.force.y + force.y)

    # ------------------------------------------------------------------
    # transform sync with the owning node
    # ------------------------------------------------------------------
    def sync_from_node(self, pos: Vector2, rotation_deg: float, scale: Vector2,
                       shape) -> None:
        self.scale = Vector2(scale.x, scale.y) if scale is not None else self.scale
        if shape is not None:
            self.shape = shape
        if self._pmbody is not None:
            self._pmbody.position = (pos.x, pos.y)
            self._pmbody.angle = math.radians(rotation_deg)

    def sync_to_node(self) -> None:
        if self.node is None or self._pmbody is None:
            return
        self.node.position = Vector2(self._pmbody.position.x,
                                    self._pmbody.position.y)
        self.node.rotation = math.degrees(self._pmbody.angle)


class PymunkWorld:
    """pymunk-backed :class:`PhysicsWorld` replacement."""

    def __init__(self, gravity=None):
        import pymunk
        self._pymunk = pymunk
        self.gravity = gravity if gravity is not None else Vector2(0.0, 980.0)
        self.bodies: List[PymunkBody] = []
        self.joints = []
        self.space = pymunk.Space()
        # gravity is applied per-body (respecting gravity_scale), so the space
        # gravity stays zero.
        self.space.gravity = (0.0, 0.0)
        # Higher solver iteration counts resolve resting contacts more cleanly
        # (less penetration), which is what keeps a body from visibly jittering
        # or micro-bouncing when it lands on the ground.  The pymunk defaults are
        # 10 / 10; bumping both to 20 is cheap and markedly steadier here.
        self.space.position_iterations = 20
        self.space.velocity_iterations = 20

    # ------------------------------------------------------------------
    def create_body(self, shape=None, position: Vector2 = None,
                    body_type: int = RigidBody.DYNAMIC, node=None) -> PymunkBody:
        return PymunkBody(shape=shape, position=position, body_type=body_type,
                          node=node, world=self)

    def add_body(self, body: PymunkBody) -> None:
        if body in self.bodies:
            return
        self.bodies.append(body)
        if body._pmbody is not None and body._pmshape is not None:
            try:
                self.space.add(body._pmbody, body._pmshape)
            except Exception:
                pass

    def remove_body(self, body: PymunkBody) -> None:
        if body in self.bodies:
            self.bodies.remove(body)
        try:
            if body._pmshape is not None:
                self.space.remove(body._pmshape)
            if body._pmbody is not None:
                self.space.remove(body._pmbody)
        except Exception:
            pass

    def add_joint(self, joint) -> None:
        self.joints.append(joint)

    def remove_joint(self, joint) -> None:
        if joint in self.joints:
            self.joints.remove(joint)

    def clear(self) -> None:
        self.bodies.clear()
        self.joints.clear()
        self.space = self._pymunk.Space()
        self.space.gravity = (0.0, 0.0)

    # ------------------------------------------------------------------
    def step(self, dt: float) -> None:
        if dt <= 0:
            return
        pymunk = self._pymunk
        g = self.gravity
        for b in self.bodies:
            p = b._pmbody
            if p is None or p.body_type in (pymunk.Body.STATIC,
                                            pymunk.Body.KINEMATIC):
                continue
            # linear / angular damping (matches built-in v *= (1 - d*dt))
            if b.linear_damping:
                f = max(0.0, 1.0 - b.linear_damping * dt)
                p.velocity = (p.velocity.x * f, p.velocity.y * f)
            if b.angular_damping:
                f = max(0.0, 1.0 - b.angular_damping * dt)
                p.angular_velocity *= f
            # per-body gravity * mass * gravity_scale (force is reset each step)
            if b.gravity_scale:
                p.force = (p.force.x + g.x * p.mass * b.gravity_scale,
                           p.force.y + g.y * p.mass * b.gravity_scale)
        # pymunk integrates; clamp dt to keep the solver stable
        self.space.step(min(dt, 0.1))
        # pymunk routinely leaves tiny residual velocities on resting bodies
        # (a gentle wobble plus small hops).  Snap near-zero linear / angular
        # velocities to zero so a body that is effectively at rest stays
        # perfectly still instead of micro-bouncing on the floor.  The threshold
        # (3 px/s, 0.03 rad/s) is far below any meaningful movement, so gameplay
        # motion is unaffected.
        for b in self.bodies:
            p = b._pmbody
            if p is None or p.body_type != pymunk.Body.DYNAMIC:
                continue
            vx, vy = p.velocity
            if vx * vx + vy * vy < 9.0:
                p.velocity = (0.0, 0.0)
            if abs(p.angular_velocity) < 0.03:
                p.angular_velocity = 0.0
        # copy transforms back to nodes
        for b in self.bodies:
            b.sync_to_node()
