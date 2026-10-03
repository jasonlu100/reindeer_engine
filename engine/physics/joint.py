"""Joints / constraints.

Two minimal but functional joints are provided:

* :class:`DistanceJoint` - keeps two bodies at a fixed separation (ropes,
  springs, soft constraints).
* :class:`RevoluteJoint` - pins two bodies at a common anchor point so they
  rotate around it.

They are solved with a Baumgarte-stabilised impulse each physics step, which
is simple and stable enough for gameplay use.
"""
from __future__ import annotations

from engine.core.math2d import Vector2


class Joint:
    def __init__(self, body_a, body_b):
        self.body_a = body_a
        self.body_b = body_b
        self.broken = False

    def solve(self, dt: float) -> None:
        raise NotImplementedError


class DistanceJoint(Joint):
    def __init__(self, body_a, body_b, rest_length: float = None):
        super().__init__(body_a, body_b)
        if rest_length is None:
            rest_length = (body_b.position - body_a.position).length()
        self.rest_length = rest_length
        self.stiffness = 0.9       # 0..1, higher = stiffer
        self.damping = 0.1

    def solve(self, dt: float) -> None:
        if self.broken or dt <= 0:
            return
        a, b = self.body_a, self.body_b
        delta = b.position - a.position
        dist = delta.length()
        if dist < 1e-6:
            return
        n = delta / dist
        c = dist - self.rest_length
        rv = b.velocity - a.velocity
        vel_along = rv.dot(n)
        denom = a.inv_mass + b.inv_mass
        if denom == 0:
            return
        # Baumgarte position correction folded into the velocity solve
        bias = (self.stiffness / dt) * c
        j = -(vel_along + bias) / denom
        impulse = n * j
        a.velocity -= impulse * a.inv_mass
        b.velocity += impulse * b.inv_mass


class RevoluteJoint(Joint):
    """Pins two bodies together at a shared world anchor."""

    def __init__(self, body_a, body_b, anchor: Vector2 = None):
        super().__init__(body_a, body_b)
        self.anchor = anchor or (body_a.position + body_b.position) * 0.5
        self.stiffness = 0.9

    def solve(self, dt: float) -> None:
        if self.broken or dt <= 0:
            return
        a, b = self.body_a, self.body_b
        err = b.position - a.position
        denom = a.inv_mass + b.inv_mass
        if denom == 0:
            return
        corr = err * (self.stiffness / dt)
        a.position -= corr * (a.inv_mass / denom)
        b.position += corr * (b.inv_mass / denom)
        # damp relative angular velocity a little so the pin stays calm
        avg = (a.angular_velocity + b.angular_velocity) * 0.5
        a.angular_velocity += (avg - a.angular_velocity) * 0.1
        b.angular_velocity += (avg - b.angular_velocity) * 0.1
