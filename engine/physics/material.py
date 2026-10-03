"""Physics materials.

A :class:`PhysicsMaterial` describes how a body reacts in collisions: its
bounciness (restitution) and surface friction.  Materials can be shared
between many bodies via the resource system.
"""
from __future__ import annotations

from typing import Optional


class PhysicsMaterial:
    def __init__(self, restitution: float = 0.2, friction: float = 0.5,
                 name: str = "Default"):
        self.name = name
        self.restitution = restitution
        self.friction = friction

    def combine_restitution(self, other: "PhysicsMaterial") -> float:
        # average combination (Godot uses "average" by default)
        return (self.restitution + other.restitution) * 0.5

    def combine_friction(self, other: "PhysicsMaterial") -> float:
        return (self.friction + other.friction) * 0.5

    def __repr__(self):
        return f"<PhysicsMaterial {self.name} e={self.restitution} f={self.friction}>"


# shared default material
DEFAULT_MATERIAL = PhysicsMaterial()
