"""Built-in 2D physics engine and optional backends.

A small, dependency-free rigid-body simulator (the default ``builtin`` backend)
providing:

* dynamic / static / kinematic bodies
* circle, box and convex-polygon colliders
* impulse-based collision response with restitution & friction
* a simple sequential-impulse solver with positional correction
* gravity, joints (distance / pin) and per-body physics materials

A second backend, ``pymunk``, is available for projects that need a more
precise / battle-tested solver.  It is selected per project via the
``physics_backend`` config key and requires ``pip install pymunk``; see
:mod:`engine.physics.pymunk_world`.  The node layer is backend-agnostic, so no
game code changes are needed when switching.

The simulation runs in *world space*; nodes (``RigidBody2D``) copy their world
transform into / out of a body each step.
"""
from __future__ import annotations

from engine.physics.body import RigidBody
from engine.physics.world import PhysicsWorld


__all__ = ["RigidBody", "PhysicsWorld", "create_physics_world"]


def create_physics_world(backend: str = "builtin", gravity=None):
    """Return a physics world for ``backend``.

    * ``"builtin"`` (default) -> :class:`PhysicsWorld`
    * ``"pymunk"``           -> :class:`PymunkWorld` (requires pymunk)

    Any other value falls back to the built-in world.
    """
    if backend == "pymunk":
        try:
            from engine.physics.pymunk_world import PymunkWorld
            return PymunkWorld(gravity=gravity)
        except ImportError:
            # The project asked for the optional pymunk backend but it is not
            # installed.  Never crash the runtime over a missing optional
            # dependency -- fall back to the built-in engine instead.
            import warnings
            warnings.warn(
                "physics backend 'pymunk' requested but not installed; "
                "falling back to the built-in physics engine. "
                "Install it with: pip install pymunk"
            )
            return PhysicsWorld(gravity=gravity)
    return PhysicsWorld(gravity=gravity)
