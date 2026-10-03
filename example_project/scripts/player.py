"""Example: player controller script.

Demonstrates lifecycle callbacks (_ready / _process), input handling,
node property access and the math types available through the scripting API.
Attach this script to a Sprite2D (or any 2D node) via the Inspector.
"""
import math


class PlayerController:
    def _ready(self):
        # lifecycle: called once when the node enters the scene
        self.speed = 240.0
        self.print("[player] ready -> use arrow keys / WASD to move")

    def _process(self, delta):
        # called every render frame
        dx, dy = 0.0, 0.0
        if self.is_action_pressed("ui_left"):
            dx -= 1
        if self.is_action_pressed("ui_right"):
            dx += 1
        if self.is_action_pressed("ui_up"):
            dy -= 1
        if self.is_action_pressed("ui_down"):
            dy += 1

        if dx != 0.0 or dy != 0.0:
            length = math.sqrt(dx * dx + dy * dy)
            dx /= length
            dy /= length
            p = self.node.position
            self.node.position = self.api.Vector2(
                p.x + dx * self.speed * delta,
                p.y + dy * self.speed * delta,
            )

        # simple world bounds
        p = self.node.position
        #p.x = max(0.0, min(800.0, p.x))
        #p.y = max(0.0, min(600.0, p.y))
        self.node.position = p
