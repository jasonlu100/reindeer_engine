"""Time keeping for the engine loop.

Mirrors the small subset of Godot's ``Time``/``OS`` time helpers that the
engine and scripts rely on: delta time, frames-per-second and a global
elapsed clock.
"""
from __future__ import annotations

import time


class Time:
    def __init__(self):
        self._last = time.perf_counter()
        self.delta: float = 0.0
        self.physics_delta: float = 1.0 / 60.0
        self.elapsed: float = 0.0
        self.frame: int = 0
        self.fps: float = 0.0
        self._fps_acc = 0.0
        self._fps_frames = 0

    def tick(self) -> float:
        """Advance the clock and return the delta (in seconds)."""
        now = time.perf_counter()
        self.delta = max(0.0, now - self._last)
        # clamp to avoid spiral-of-death after a stall
        if self.delta > 0.1:
            self.delta = 0.1
        self._last = now
        self.elapsed += self.delta
        self.frame += 1

        self._fps_acc += self.delta
        self._fps_frames += 1
        if self._fps_acc >= 0.5:
            self.fps = self._fps_frames / self._fps_acc
            self._fps_acc = 0.0
            self._fps_frames = 0
        return self.delta

    def set_physics_delta(self, hz: float) -> None:
        self.physics_delta = 1.0 / max(1.0, hz)
