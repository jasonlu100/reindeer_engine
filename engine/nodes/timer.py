"""Timer node: counts down and emits ``timeout``."""
from __future__ import annotations

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_FLOAT, PT_BOOL
from engine.core.registry import register_node
from engine.core.node import Node


@register_node("Node")
class Timer(Node):
    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("wait_time", PT_FLOAT, 1.0, group="Timer", min_value=0.01),
        PropertyDef("one_shot", PT_BOOL, False, group="Timer"),
        PropertyDef("autostart", PT_BOOL, False, group="Timer"),
        PropertyDef("paused", PT_BOOL, False, group="Timer"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("timeout")
        self._elapsed = 0.0
        self._running = False

    def _ready(self) -> None:
        if self.autostart:
            self.start()

    def _process(self, delta: float) -> None:
        if not self._running or self.paused:
            return
        self._elapsed += delta
        if self._elapsed >= self.wait_time:
            self._elapsed = 0.0
            self.emit("timeout")
            if self.one_shot:
                self._running = False

    def start(self) -> None:
        self._running = True
        self._elapsed = 0.0

    def stop(self) -> None:
        self._running = False

    def is_stopped(self) -> bool:
        return not self._running

    def get_time_left(self) -> float:
        return max(0.0, self.wait_time - self._elapsed)
