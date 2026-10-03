"""Shared lighting model.

Both rendering backends use the *same* falloff function so a point light looks
identical whether it is drawn by the Qt renderer (editor) or the pygame
renderer (standalone / packaged build).  The light intensity is highest at the
centre and falls off quadratically to zero at the light radius, then the result
is composited **additively** on top of the scene.
"""
from __future__ import annotations

from typing import List, Tuple


def light_intensity(t: float) -> float:
    """Radial light intensity at normalised distance ``t`` (0 = centre, 1 = edge).

    A quadratic falloff ``(1 - t)^2`` gives a soft, natural gradient instead of a
    hard-edged disc.
    """
    if t <= 0.0:
        return 1.0
    if t >= 1.0:
        return 0.0
    k = 1.0 - t
    return k * k


def gradient_stops(samples: int = 16) -> List[Tuple[float, float]]:
    """Return ``(position, intensity)`` stops for ``t`` in [0, 1]."""
    out = []
    for i in range(samples + 1):
        t = i / samples
        out.append((t, light_intensity(t)))
    return out
