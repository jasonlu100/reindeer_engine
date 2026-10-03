"""Example: enemy script demonstrating signals / events.

Shows how a script can declare a node signal, connect a handler to it and emit
it from the frame loop.  The enemy blinks on a timer and announces each blink.
"""
import math


class EnemyAI:
    def _ready(self):
        self.timer = 0.0
        self.interval = 0.8
        # declare + connect a signal (decoupled event mechanism)
        self.node.add_signal("enemy_blinked")
        self.connect("enemy_blinked", self._on_blink)
        self.print("[enemy] ready, will blink every", self.interval, "s")

    def _process(self, delta):
        self.timer += delta
        if self.timer >= self.interval:
            self.timer = 0.0
            self.node.visible = not self.node.visible
            self.emit("enemy_blinked", self.node.visible)

    def _on_blink(self, visible):
        self.print("[enemy] blinked -> visible =", visible)
