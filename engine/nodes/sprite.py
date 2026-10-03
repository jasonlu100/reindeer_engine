"""Sprite node: draws a texture (or placeholder) at its transform."""
from __future__ import annotations

from engine.core.math2d import Vector2, Color
from engine.core.node import (PropertyDef, PT_STRING, PT_BOOL, PT_VECTOR2,
                              PT_INT, PT_RESOURCE)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("Node2D")
class Sprite2D(Node2D):
    """Draws an image.  When no texture is set a coloured rectangle is drawn
    so scenes remain visible without external assets.  ``texture`` is a
    :data:`PT_RESOURCE` so the editor shows a file picker, and the sprite
    supports a spritesheet via ``hframes``/``vframes``/``frame``."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("texture", PT_RESOURCE, "", group="Sprite",
                   hint="texture image", resource_ext="png,jpg,jpeg"),
        PropertyDef("centered", PT_BOOL, True, group="Sprite"),
        PropertyDef("offset", PT_VECTOR2, Vector2(0, 0), group="Sprite"),
        PropertyDef("flip_h", PT_BOOL, False, group="Sprite"),
        PropertyDef("flip_v", PT_BOOL, False, group="Sprite"),
        PropertyDef("hframes", PT_INT, 1, group="Sprite", min_value=1,
                   max_value=256, hint="spritesheet columns"),
        PropertyDef("vframes", PT_INT, 1, group="Sprite", min_value=1,
                   max_value=256, hint="spritesheet rows"),
        PropertyDef("frame", PT_INT, 0, group="Sprite", min_value=0,
                   max_value=65535, hint="frame index"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._texture_size = Vector2(32, 32)  # updated by the renderer

    def set_texture_size(self, w: float, h: float) -> None:
        self._texture_size = Vector2(w, h)

    def get_texture_size(self) -> Vector2:
        return self._texture_size

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            renderer.draw_sprite(self)
        super()._draw(renderer, camera)
