"""Camera2D: defines the view used by the renderer."""
from __future__ import annotations

import math

from engine.core.math2d import Vector2
from engine.core.node import PropertyDef, PT_FLOAT, PT_BOOL, PT_VECTOR2
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("Camera")
class Camera2D(Node2D):
    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("zoom", PT_FLOAT, 1.0, group="Camera", min_value=0.05),
        PropertyDef("offset", PT_VECTOR2, Vector2(0, 0), group="Camera"),
        PropertyDef("current", PT_BOOL, True, group="Camera"),
        PropertyDef("smoothing", PT_BOOL, False, group="Camera"),
        PropertyDef("smoothing_speed", PT_FLOAT, 5.0, group="Camera",
                    min_value=0.0),
        PropertyDef("limit_x", PT_FLOAT, 1e9, group="Camera"),
        PropertyDef("limit_y", PT_FLOAT, 1e9, group="Camera"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Smoothed world centre used for rendering.  ``None`` means "not
        # initialised yet" – the first ``_process`` (or the first render, via
        # ``_render_center``) snaps it to the camera's current world position.
        self._smooth_pos = None

    # ------------------------------------------------------------------
    # per-frame update
    # ------------------------------------------------------------------
    def _process(self, delta: float) -> None:
        # keep script-instance dispatch working
        super()._process(delta)
        target = self.get_global_position()
        if self._smooth_pos is None:
            self._smooth_pos = target
        elif self.smoothing and delta > 0:
            # frame-rate independent exponential smoothing toward the target
            t = 1.0 - math.exp(-max(self.smoothing_speed, 0.0) * delta)
            self._smooth_pos = self._smooth_pos + (target - self._smooth_pos) * t
        else:
            # smoothing disabled (or paused): snap to the target
            self._smooth_pos = target

    def _render_center(self) -> Vector2:
        """World point the camera is actually centred on for rendering.

        Falls back to the node's real global position when smoothing hasn't
        been initialised (e.g. the very first frame, or the editor preview
        before ``_process`` runs).  Also clamps to the configured world bounds
        so the view never leaves the rectangular region."""
        c = self._smooth_pos if self._smooth_pos is not None \
            else self.get_global_position()
        lx = getattr(self, "limit_x", 1e9)
        ly = getattr(self, "limit_y", 1e9)
        if lx < 1e8:
            c = Vector2(max(-lx, min(lx, c.x)), c.y)
        if ly < 1e8:
            c = Vector2(c.x, max(-ly, min(ly, c.y)))
        return c

    # ------------------------------------------------------------------
    # coordinate conversion (uses the smoothed centre)
    # ------------------------------------------------------------------
    def world_to_screen(self, world: Vector2, viewport_w: float,
                        viewport_h: float) -> Vector2:
        center = self._render_center() + self.offset
        z = self.zoom if self.zoom > 0 else 1.0
        sx = (world.x - center.x) * z + viewport_w * 0.5
        sy = (world.y - center.y) * z + viewport_h * 0.5
        return Vector2(sx, sy)

    def screen_to_world(self, screen: Vector2, viewport_w: float,
                       viewport_h: float) -> Vector2:
        center = self._render_center() + self.offset
        z = self.zoom if self.zoom > 0 else 1.0
        wx = (screen.x - viewport_w * 0.5) / z + center.x
        wy = (screen.y - viewport_h * 0.5) / z + center.y
        return Vector2(wx, wy)
