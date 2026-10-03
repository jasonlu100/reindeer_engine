"""Physics world.

Owns all :class:`RigidBody` and :class:`Joint` instances, applies gravity,
detects collisions (broad-phase AABB, narrow-phase :mod:`collision`) and
resolves them with a sequential-impulse solver plus Baumgarte positional
stabilisation.  After stepping, each body copies its world transform back to
the node it is attached to.
"""
from __future__ import annotations

from typing import List, Tuple

from engine.core.math2d import Vector2
from engine.physics.collision import collide
from engine.physics.joint import Joint


def _cross_vs(w: float, r: Vector2) -> Vector2:
    # scalar (angular velocity) cross vector
    return Vector2(-w * r.y, w * r.x)


class PhysicsWorld:
    def __init__(self, gravity: Vector2 = None):
        self.bodies: List = []
        self.joints: List[Joint] = []
        self.gravity = gravity if gravity is not None else Vector2(0.0, 980.0)
        self.velocity_iterations = 8
        self.position_iterations = 3
        self.slop = 0.5            # allowed penetration (px)
        self.baumgarte = 0.2

    # ------------------------------------------------------------------
    def create_body(self, shape=None, position=None, body_type=0, node=None):
        """Factory used by ``RigidBody2D`` so the node layer is backend-agnostic."""
        from engine.physics.body import RigidBody
        return RigidBody(shape=shape, position=position, body_type=body_type,
                         node=node)

    def add_body(self, body) -> None:
        if body not in self.bodies:
            self.bodies.append(body)

    def remove_body(self, body) -> None:
        if body in self.bodies:
            self.bodies.remove(body)

    def add_joint(self, joint: Joint) -> None:
        self.joints.append(joint)

    def remove_joint(self, joint: Joint) -> None:
        if joint in self.joints:
            self.joints.remove(joint)

    def clear(self) -> None:
        self.bodies.clear()
        self.joints.clear()

    # ------------------------------------------------------------------
    def step(self, dt: float) -> None:
        if dt <= 0:
            return
        dynamic = [b for b in self.bodies
                   if b.body_type == b.DYNAMIC and not b.sleeping]

        # integrate gravity + damping into velocity
        for b in dynamic:
            b.velocity += self.gravity * (dt * b.gravity_scale)
            b.velocity *= max(0.0, 1.0 - b.linear_damping * dt)
            b.angular_velocity *= max(0.0, 1.0 - b.angular_damping * dt)

        # broad phase + narrow phase
        pairs: List[Tuple] = []
        n = len(self.bodies)
        for i in range(n):
            a = self.bodies[i]
            if a.shape is None:
                continue
            for j in range(i + 1, n):
                b = self.bodies[j]
                if b.shape is None:
                    continue
                if a.inv_mass == 0 and b.inv_mass == 0:
                    continue
                if not a.get_aabb(a.scale).intersects(b.get_aabb(b.scale)):
                    continue
                m = collide(a.shape, a.position, a.angle, a.scale,
                            b.shape, b.position, b.angle, b.scale)
                if m is not None:
                    pairs.append((a, b, m))

        # resolve velocities
        for _ in range(self.velocity_iterations):
            for a, b, m in pairs:
                self._resolve(a, b, m)

        # integrate positions
        for b in dynamic:
            b.position += b.velocity * dt
            b.angle += b.angular_velocity * dt
            b._aabb_dirty = True

        # joints
        for j in self.joints:
            j.solve(dt)

        # copy transforms back to nodes
        for b in self.bodies:
            b.sync_to_node()

    # ------------------------------------------------------------------
    def _resolve(self, a, b, m: "Manifold") -> None:
        normal = m.normal  # A -> B
        num = len(m.contacts)
        if num == 0:
            return
        e = a.material.combine_restitution(b.material)
        mu = a.material.combine_friction(b.material)

        for contact in m.contacts:
            rA = contact - a.position
            rB = contact - b.position
            rel = (_cross_vs(b.angular_velocity, rB) + b.velocity) - \
                  (_cross_vs(a.angular_velocity, rA) + a.velocity)
            vel_along = rel.dot(normal)
            if vel_along > 0:
                continue  # separating
            rAcn = rA.cross(normal)
            rBcn = rB.cross(normal)
            inv_sum = (a.inv_mass + b.inv_mass
                       + rAcn * rAcn * a.inv_inertia
                       + rBcn * rBcn * b.inv_inertia)
            if inv_sum == 0:
                continue
            jn = -(1.0 + e) * vel_along / inv_sum / num

            impulse = normal * jn
            a.velocity -= impulse * a.inv_mass
            a.angular_velocity -= a.inv_inertia * rA.cross(impulse)
            b.velocity += impulse * b.inv_mass
            b.angular_velocity += b.inv_inertia * rB.cross(impulse)

            # friction
            rel = (_cross_vs(b.angular_velocity, rB) + b.velocity) - \
                  (_cross_vs(a.angular_velocity, rA) + a.velocity)
            tangent = rel - normal * rel.dot(normal)
            if tangent.length_squared() < 1e-9:
                continue
            tangent = tangent.normalized()
            jt = -rel.dot(tangent) / inv_sum / num
            if abs(jt) < jn * mu:
                f_imp = tangent * jt
            else:
                f_imp = tangent * (-jn * mu)
            a.velocity -= f_imp * a.inv_mass
            a.angular_velocity -= a.inv_inertia * rA.cross(f_imp)
            b.velocity += f_imp * b.inv_mass
            b.angular_velocity += b.inv_inertia * rB.cross(f_imp)
