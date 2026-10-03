"""Animated sprite node.

:class:`AnimatedSprite2D` subclasses :class:`Sprite2D` and cycles through a
list of texture paths (one per line in the ``frames`` property) at ``fps``.
It reuses the full sprite drawing / placeholder logic, so it works with or
without image assets loaded.
"""
from __future__ import annotations

from engine.core.node import PropertyDef, PT_STRING, PT_FLOAT, PT_BOOL
from engine.core.registry import register_node
from engine.nodes.sprite import Sprite2D


@register_node("Node2D")
class AnimatedSprite2D(Sprite2D):
    """Plays through a list of frames (texture paths) at a fixed rate."""

    PROPERTIES = Sprite2D.PROPERTIES + [
        PropertyDef("frames", PT_STRING, "", group="Animation",
                   hint="texture path, one per line"),
        PropertyDef("fps", PT_FLOAT, 8.0, group="Animation", min_value=0.1),
        PropertyDef("playing", PT_BOOL, True, group="Animation"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._frame_list = []
        self._idx = 0
        self._time = 0.0

    def _sync_frames(self) -> None:
        if not self._frame_list:
            self._frame_list = [f.strip() for f in self.frames.splitlines()
                               if f.strip()]
            if self._frame_list:
                self.texture = self._frame_list[0]
                self._idx = 0

    def _process(self, delta: float) -> None:
        if self.playing and self.fps > 0:
            self._sync_frames()
            if self._frame_list:
                self._time += delta
                if self._time >= 1.0 / self.fps:
                    self._time = 0.0
                    self._idx = (self._idx + 1) % len(self._frame_list)
                    self.texture = self._frame_list[self._idx]

    def _draw(self, renderer, camera) -> None:
        self._sync_frames()
        super()._draw(renderer, camera)
