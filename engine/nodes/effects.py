"""Engine-level effect nodes: post-processing and tile maps.

These used to live in the optional plugin packages; they are now first-class
engine nodes so the same scene works whether it is previewed in the editor
(Qt renderer) or shipped with the pygame backend -- no plugin system required.
"""
from __future__ import annotations

from engine.core.math2d import Vector2, Color
from engine.core.node import (Node, PropertyDef, PT_ENUM, PT_FLOAT,
                             PT_COLOR, PT_VECTOR2, PT_STRING)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D


@register_node("PostFX")
class PostProcess(Node):
    """A full-viewport post effect applied after the scene is drawn.

    Currently supports a ``vignette`` (darkened corners).  Because it is a plain
    :class:`Node` it is drawn in screen space and ignores the camera transform.
    """

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("effect", PT_ENUM, "vignette", group="PostFX",
                    options=["none", "vignette"]),
        PropertyDef("strength", PT_FLOAT, 0.5, group="PostFX", min_value=0.0,
                    max_value=1.0),
        PropertyDef("tint", PT_COLOR, Color(0.0, 0.0, 0.0, 1.0), group="PostFX"),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible and self.effect == "vignette":
            renderer.draw_vignette(self.strength, self.tint)
        super()._draw(renderer, camera)


@register_node("TileMap")
class TileMap(Node2D):
    """Renders a grid of coloured tiles from a compact ``cell_data`` string.

    Tiles outside the current viewport are culled for speed.  Each tile id maps
    to a colour from ``palette`` (comma separated hex colours; id 0 = empty).
    """

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("tile_size", PT_VECTOR2, Vector2(32, 32), group="TileMap"),
        PropertyDef("cell_data", PT_STRING, "", group="TileMap",
                    hint="rows separated by ';', cells by ',' (0=empty)"),
        PropertyDef("palette", PT_STRING, "#5a8,#3a5,#888,#c33",
                    group="TileMap", hint="comma separated hex colors"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._cells = {}

    # ------------------------------------------------------------------
    def _ensure_parsed(self) -> None:
        if self._cells:
            return
        rows = [r for r in self.cell_data.split(";") if r.strip()]
        for ry, row in enumerate(rows):
            for cx, val in enumerate(row.split(",")):
                val = val.strip()
                if val and val != "0":
                    try:
                        self._cells[(cx, ry)] = int(val)
                    except ValueError:
                        pass

    def get_cell(self, x: int, y: int) -> int:
        self._ensure_parsed()
        return self._cells.get((x, y), 0)

    def set_cell(self, x: int, y: int, id: int) -> None:
        self._ensure_parsed()
        if id == 0:
            self._cells.pop((x, y), None)
        else:
            self._cells[(x, y)] = id
        self._serialize()

    def _serialize(self) -> None:
        if not self._cells:
            self.set_property("cell_data", "")
            return
        max_x = max(c[0] for c in self._cells)
        max_y = max(c[1] for c in self._cells)
        rows = []
        for y in range(max_y + 1):
            row = []
            for x in range(max_x + 1):
                row.append(str(self._cells.get((x, y), 0)))
            rows.append(",".join(row))
        self.set_property("cell_data", ";".join(rows))

    def _palette_color(self, id: int) -> Color:
        cols = [c.strip() for c in self.palette.split(",") if c.strip()]
        if not cols:
            return Color(1, 1, 1, 1)
        return Color.from_hex(cols[(id - 1) % len(cols)])

    def _draw(self, renderer, camera) -> None:
        if not self.visible:
            super()._draw(renderer, camera)
            return
        self._ensure_parsed()
        if not self._cells:
            super()._draw(renderer, camera)
            return

        # visible world rectangle (cull tiles outside the viewport for speed)
        w, h = renderer.viewport_w, renderer.viewport_h
        if camera is not None:
            tl = camera.screen_to_world(Vector2(0, 0), w, h)
            br = camera.screen_to_world(Vector2(w, h), w, h)
        else:
            tl = Vector2(-w / 2.0, -h / 2.0)
            br = Vector2(w / 2.0, h / 2.0)
        left = min(tl.x, br.x) - self.tile_size.x
        right = max(tl.x, br.x) + self.tile_size.x
        top = min(tl.y, br.y) - self.tile_size.y
        bottom = max(tl.y, br.y) + self.tile_size.y

        ts = self.tile_size
        base = self.get_global_position()
        for (cx, cy), id in self._cells.items():
            center = base + Vector2((cx + 0.5) * ts.x, (cy + 0.5) * ts.y)
            if center.x < left or center.x > right or \
               center.y < top or center.y > bottom:
                continue
            renderer.draw_rect(center, ts, self._palette_color(id))
        super()._draw(renderer, camera)
