"""A simple 2D particle emitter node.

:class:`Particles2D` maintains a small pool of particles that are spawned
around the node origin, move under an optional gravity vector and fade out
over their lifetime.  It is rendered entirely with ``draw_circle`` so it
needs no external assets and animates during play (and live preview).
"""
from __future__ import annotations

import math
import random

from engine.core.math2d import Vector2, Color
from engine.core.node import (PropertyDef, PT_FLOAT, PT_BOOL, PT_COLOR,
                              PT_INT, PT_VECTOR2)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("Visual")
class Particles2D(Node2D):
    """Emits short-lived particles in a cone defined by ``direction``/``spread``."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("emitting", PT_BOOL, True, group="Particles"),
        PropertyDef("amount", PT_INT, 32, group="Particles", min_value=1,
                   max_value=2000),
        PropertyDef("lifetime", PT_FLOAT, 1.0, group="Particles", min_value=0.05),
        PropertyDef("speed", PT_FLOAT, 60.0, group="Particles"),
        PropertyDef("spread", PT_FLOAT, 360.0, group="Particles", hint="degrees"),
        PropertyDef("direction", PT_FLOAT, -90.0, group="Particles",
                   hint="degrees"),
        PropertyDef("gravity", PT_VECTOR2, Vector2(0, 0), group="Particles"),
        PropertyDef("color", PT_COLOR, Color(1.0, 0.8, 0.3, 1.0),
                   group="Particles"),
        PropertyDef("size", PT_FLOAT, 4.0, group="Particles", min_value=1),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._particles = []   # list of dict(pos, vel, life)
        self._spawn_acc = 0.0

    def _process(self, delta: float) -> None:
        if self.emitting:
            rate = self.amount / max(0.05, self.lifetime)
            self._spawn_acc += delta * rate
            while self._spawn_acc >= 1.0 and len(self._particles) < self.amount:
                self._spawn_acc -= 1.0
                self._spawn_particle()
        g = self.gravity
        alive = []
        for p in self._particles:
            p["life"] -= delta
            if p["life"] <= 0.0:
                continue
            p["vel"] = p["vel"] + g * delta
            p["pos"] = p["pos"] + p["vel"] * delta
            alive.append(p)
        self._particles = alive

    def _spawn_particle(self) -> None:
        angle = self.direction + random.uniform(-self.spread / 2.0,
                                                self.spread / 2.0)
        a = math.radians(angle)
        vel = Vector2(math.cos(a), math.sin(a)) * self.speed
        self._particles.append({"pos": Vector2(0, 0), "vel": vel,
                                "life": self.lifetime})

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            base = self.get_global_position()
            for p in self._particles:
                t = max(0.0, min(1.0, p["life"] / self.lifetime))
                col = Color(self.color.r, self.color.g, self.color.b,
                            self.color.a * t)
                renderer.draw_circle(base + p["pos"], self.size * 0.5, col)
        super()._draw(renderer, camera)
