"""Abstract 2D renderer contract.

Both rendering backends (the Qt :class:`Renderer2D` used by the editor and the
Pygame backend used by the standalone / packaged builds) subclass
:class:`Renderer2DBase` and implement the *same* set of drawing primitives.  Node
``_draw`` code therefore runs unchanged regardless of the active backend, which
is what keeps the editor preview and the shipped game visually identical.

The base class owns the backend-agnostic state (resource base path, viewport
size, active camera, debug flags) and the shared camera-to-screen transform plus
the recursive ``render`` traversal.  Concrete subclasses fill in the actual
drawing calls for their surface type.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from engine.core.math2d import Vector2, Color


class Renderer2DBase(ABC):
    """Common state + draw-surface contract shared by every backend."""

    def __init__(self, resource_base: str = ""):
        self.resource_base = resource_base
        self.viewport_w = 0
        self.viewport_h = 0
        self.camera = None
        self.show_collision_shapes = True
        self.background = Color(0.12, 0.12, 0.16, 1.0)

    # ------------------------------------------------------------------
    # shared helpers
    # ------------------------------------------------------------------
    def set_resource_base(self, path: str) -> None:
        self.resource_base = path

    def _resolve(self, path: str) -> str:
        if not path:
            return ""
        if os.path.isabs(path) or not self.resource_base:
            return path
        return os.path.join(self.resource_base, path)

    def world_to_screen(self, world: Vector2) -> Vector2:
        """Map a world point to a screen point using the active camera."""
        if self.camera is not None:
            return self.camera.world_to_screen(world, self.viewport_w,
                                              self.viewport_h)
        return Vector2(world.x + self.viewport_w * 0.5,
                       world.y + self.viewport_h * 0.5)

    # ------------------------------------------------------------------
    # frame lifecycle (backend specific)
    # ------------------------------------------------------------------
    @abstractmethod
    def begin(self, surface, w: int, h: int, camera) -> None:
        """Start a frame: clear the surface and record viewport + camera."""

    @abstractmethod
    def end(self) -> None:
        """Finish a frame."""

    # ------------------------------------------------------------------
    # drawing primitives -- every backend MUST implement these
    # ------------------------------------------------------------------
    @abstractmethod
    def draw_sprite(self, sprite) -> None:
        ...

    @abstractmethod
    def draw_tiled_background(self, texture: str, parallax: Vector2 = None,
                             scroll: Vector2 = None) -> None:
        ...

    @abstractmethod
    def draw_rect(self, world_pos: Vector2, size: Vector2, color: Color,
                  rotation: float = 0.0) -> None:
        ...

    @abstractmethod
    def draw_texture_rect(self, world_pos: Vector2, size: Vector2, texture: str,
                          rotation: float = 0.0, modulate: Color = None) -> None:
        ...

    @abstractmethod
    def draw_nine_patch(self, world_pos: Vector2, size: Vector2, texture: str,
                        margins: tuple, rotation: float = 0.0) -> None:
        ...

    @abstractmethod
    def draw_rect_outline(self, world_pos: Vector2, size: Vector2, color: Color,
                         rotation: float = 0.0, width: float = 1.0) -> None:
        ...

    @abstractmethod
    def draw_circle(self, world_pos: Vector2, radius: float, color: Color) -> None:
        ...

    @abstractmethod
    def draw_polygon(self, world_verts, color: Color,
                     outline: Color = None) -> None:
        ...

    @abstractmethod
    def draw_line(self, a: Vector2, b: Vector2, color: Color,
                  width: float = 1.0) -> None:
        ...

    @abstractmethod
    def draw_text(self, world_pos: Vector2, text: str, color: Color,
                  font_size: int = 16, align: str = "left",
                  outline_color: Color = None, outline_size: int = 0) -> None:
        ...

    @abstractmethod
    def draw_collision_shape(self, node) -> None:
        ...

    @abstractmethod
    def draw_light(self, world_pos: Vector2, radius: float, color: Color,
                   energy: float = 1.0) -> None:
        """Draw an additive point light with a smooth radial falloff."""

    @abstractmethod
    def draw_vignette(self, strength: float, color: Color) -> None:
        ...

    # ------------------------------------------------------------------
    # tree traversal (shared, backend independent)
    #
    # Draw order is determined by (CanvasLayer.layer, z_index, tree order) so the
    # Inspector's ``z_index`` property and ``CanvasLayer.layer`` are actually
    # honoured.  Previously draw order was pure tree-traversal order, which made
    # those two properties purely decorative.  We collect every visible node's
    # draw call into a queue, sort it, then execute -- this keeps the order
    # correct regardless of subtree nesting while preserving script ``_draw``
    # hooks (which run inside the deferred node ``_draw`` call).
    # ------------------------------------------------------------------
    def render(self, tree) -> None:
        if tree.root is None:
            return
        self._render_tree(tree.root)

    def render_root(self, root) -> None:
        if root is not None:
            self._render_tree(root)

    def _layer_of(self, node) -> int:
        """Return the CanvasLayer layer the node belongs to (0 if none)."""
        n = node
        while n is not None:
            if type(n).__name__ == "CanvasLayer":
                return getattr(n, "layer", 0)
            n = n.parent
        return 0

    def _render_tree(self, root) -> None:
        queue = []
        counter = [0]  # a simple, stable tree-order index

        def walk(node):
            layer = self._layer_of(node)
            z = getattr(node, "z_index", 0) or 0
            order = counter[0]
            counter[0] += 1
            if getattr(node, "visible", True):
                # bind ``nd`` by value so the closure captures the right node
                queue.append((layer, z, order,
                              lambda nd=node: nd._draw(self, self.camera)))
            for c in node.children:
                walk(c)

        walk(root)
        queue.sort(key=lambda it: (it[0], it[1], it[2]))
        for _, _, _, fn in queue:
            try:
                fn()
            except Exception:
                import traceback
                traceback.print_exc()
