"""Rendering abstraction.

The engine is renderer-agnostic: nodes draw themselves by calling methods on
a :class:`Renderer2D` (passed in as ``renderer`` to ``_draw``).  The default
implementation renders to a Qt ``QPainter`` so it can be embedded directly in
the editor's viewport.  Swapping to another backend (e.g. OpenGL / pygame)
only requires implementing the same small method set.
"""
from __future__ import annotations

import math
import os
from typing import Dict, Optional

from engine.core.math2d import Vector2, Color
from engine.rendering.base import Renderer2DBase


class Renderer2D(Renderer2DBase):
    """Draws the scene tree into a Qt ``QPainter`` each frame."""

    def __init__(self, resource_base: str = ""):
        super().__init__(resource_base)
        self.painter = None
        self._pixmap_cache: Dict[str, object] = {}

    # ------------------------------------------------------------------
    def begin(self, painter, w: int, h: int, camera) -> None:
        self.painter = painter
        self.viewport_w = w
        self.viewport_h = h
        self.camera = camera
        # clear background
        from PySide6.QtGui import QColor
        bg = QColor.fromRgba(self.background.to_qrgba())
        painter.fillRect(0, 0, w, h, bg)

    def end(self) -> None:
        self.painter = None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _qcolor(self, c: Color):
        from PySide6.QtGui import QColor
        return QColor.fromRgba(c.to_qrgba())

    def _get_pixmap(self, path: str):
        from PySide6.QtGui import QPixmap
        if path in self._pixmap_cache:
            return self._pixmap_cache[path]
        pm = QPixmap(self._resolve(path))
        if pm.isNull():
            pm = None
        self._pixmap_cache[path] = pm
        return pm

    # ------------------------------------------------------------------
    def draw_sprite(self, sprite) -> None:
        p = self.painter
        gp = sprite.get_global_position()
        gr = sprite.get_global_rotation()
        gs = sprite.get_global_scale()
        sp = self.world_to_screen(gp)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0

        from PySide6.QtGui import QPen
        p.save()
        p.translate(sp.x, sp.y)
        p.rotate(math.degrees(gr))
        p.scale(zoom * gs.x, zoom * gs.y)

        tex = getattr(sprite, "texture", "")
        pm = self._get_pixmap(tex) if tex else None
        if pm is not None:
            w, h = pm.width(), pm.height()
            # spritesheet support: extract a single frame sub-rect
            hframes = max(1, int(getattr(sprite, "hframes", 1) or 1))
            vframes = max(1, int(getattr(sprite, "vframes", 1) or 1))
            if hframes > 1 or vframes > 1:
                fw, fh = max(1, w // hframes), max(1, h // vframes)
                frame = int(getattr(sprite, "frame", 0) or 0)
                fx = (frame % hframes) * fw
                fy = (frame // hframes % vframes) * fh
                pm = pm.copy(int(fx), int(fy), int(fw), int(fh))
                w, h = fw, fh
            sprite.set_texture_size(w, h)
            ox = -w / 2 if sprite.centered else 0
            oy = -h / 2 if sprite.centered else 0
            if sprite.flip_h:
                p.scale(-1, 1)
                ox = -ox - w if sprite.centered else ox
            if sprite.flip_v:
                p.scale(1, -1)
                oy = -oy - h if sprite.centered else oy
            p.drawPixmap(ox + sprite.offset.x, oy + sprite.offset.y, pm)
        else:
            # placeholder rectangle (so scenes are visible without assets)
            w, h = sprite.get_texture_size().x, sprite.get_texture_size().y
            ox = -w / 2 if sprite.centered else 0
            oy = -h / 2 if sprite.centered else 0
            col = sprite.modulate
            p.setBrush(self._qcolor(col))
            p.setPen(QPen(self._qcolor(Color(0, 0, 0, 0.6)), 1))
            p.drawRect(int(ox), int(oy), int(w), int(h))
        p.restore()

    def draw_tiled_background(self, texture: str, parallax: Vector2 = None,
                             scroll: Vector2 = None) -> None:
        """Draw ``texture`` tiled across the whole viewport in screen space,
        offset by the active camera's scroll * ``parallax`` to fake depth."""
        if not texture:
            return
        pm = self._get_pixmap(texture)
        if pm is None:
            return
        p = self.painter
        tw, th = pm.width(), pm.height()
        if tw == 0 or th == 0:
            return
        par = parallax or Vector2(0.5, 0.5)
        cam = self.camera
        cx, cy = 0.0, 0.0
        if cam is not None:
            # use the camera's *rendered* (smoothed + clamped) centre so the
            # parallax tracks camera easing instead of the raw (unsmoothed) move
            cp = cam._render_center() + cam.offset
            cx, cy = cp.x, cp.y
        sx = scroll.x if scroll is not None else 0.0
        sy = scroll.y if scroll is not None else 0.0
        offx = (-cx * par.x - sx) % tw
        offy = (-cy * par.y - sy) % th
        x = offx - tw
        while x < self.viewport_w + tw:
            y = offy - th
            while y < self.viewport_h + th:
                p.drawPixmap(int(x), int(y), pm)
                y += th
            x += tw

    def draw_rect(self, world_pos: Vector2, size: Vector2, color: Color,
                  rotation: float = 0.0) -> None:
        p = self.painter
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        p.save()
        p.translate(sp.x, sp.y)
        p.rotate(math.degrees(rotation))
        p.scale(zoom, zoom)
        p.setBrush(self._qcolor(color))
        p.setPen(self._qcolor(Color(0, 0, 0, 0)))
        p.drawRect(int(-size.x / 2), int(-size.y / 2), int(size.x), int(size.y))
        p.restore()

    def draw_texture_rect(self, world_pos: Vector2, size: Vector2, texture: str,
                          rotation: float = 0.0, modulate: Color = None) -> None:
        """Draw a texture filling a world-space rectangle of ``size`` centered
        on ``world_pos``."""
        if not texture:
            return
        pm = self._get_pixmap(texture)
        if pm is None:
            return
        p = self.painter
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        p.save()
        if modulate is not None and modulate.a < 1.0:
            p.setOpacity(max(0.0, min(1.0, modulate.a)))
        p.translate(sp.x, sp.y)
        p.rotate(math.degrees(rotation))
        p.scale(zoom, zoom)
        w, h = size.x, size.y
        p.drawPixmap(int(-w / 2), int(-h / 2), int(w), int(h), pm)
        p.restore()

    def draw_nine_patch(self, world_pos: Vector2, size: Vector2, texture: str,
                       margins: tuple, rotation: float = 0.0) -> None:
        """Draw a texture as a 9-slice (3x3) so the middle stretches while the
        corners/edges keep their size.  ``margins`` is
        ``(left, top, right, bottom)`` in source pixels."""
        if not texture:
            return
        pm = self._get_pixmap(texture)
        if pm is None or pm.width() == 0 or pm.height() == 0:
            return
        p = self.painter
        sw, sh = pm.width(), pm.height()
        ml, mt, mr, mb = (max(0, int(m)) for m in margins)
        ml, mr = min(ml, sw - 1), min(mr, sw - 1)
        mt, mb = min(mt, sh - 1), min(mb, sh - 1)
        dw, dh = size.x, size.y
        cw = max(0, dw - ml - mr)
        ch = max(0, dh - mt - mb)
        scw = max(0, sw - ml - mr)
        sch = max(0, sh - mt - mb)
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        p.save()
        p.translate(sp.x, sp.y)
        p.rotate(math.degrees(rotation))
        p.scale(zoom, zoom)
        ox, oy = -dw / 2.0, -dh / 2.0

        dx1, dx2 = ox + ml, ox + ml + cw
        dy1, dy2 = oy + mt, oy + mt + ch
        sx1, sx2 = ml, sw - mr
        sy1, sy2 = mt, sh - mb

        def blit(sx, sy, swc, shc, dx, dy, dwc, dhc):
            if dwc <= 0 or dhc <= 0 or swc <= 0 or shc <= 0:
                return
            p.drawPixmap(int(dx), int(dy), int(dwc), int(dhc), pm,
                        int(sx), int(sy), int(swc), int(shc))

        # row 0 (top)
        blit(0, 0, ml, mt, dx0 := ox, dy0 := oy, ml, mt)
        blit(sx1, 0, scw, mt, dx1, oy, cw, mt)
        blit(sx2, 0, mr, mt, dx2, oy, mr, mt)
        # row 1 (middle)
        blit(0, sy1, ml, sch, ox, dy1, ml, ch)
        blit(sx1, sy1, scw, sch, dx1, dy1, cw, ch)
        blit(sx2, sy1, mr, sch, dx2, dy1, mr, ch)
        # row 2 (bottom)
        blit(0, sy2, ml, mb, ox, dy2, ml, mb)
        blit(sx1, sy2, scw, mb, dx1, dy2, cw, mb)
        blit(sx2, sy2, mr, mb, dx2, dy2, mr, mb)
        p.restore()

    def draw_rect_outline(self, world_pos: Vector2, size: Vector2, color: Color,
                         rotation: float = 0.0, width: float = 1.0) -> None:
        """Draw the outline of a world-space rectangle (used as a placeholder
        for UI nodes without a texture)."""
        from PySide6.QtGui import QPen
        p = self.painter
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        p.save()
        p.translate(sp.x, sp.y)
        p.rotate(math.degrees(rotation))
        p.scale(zoom, zoom)
        p.setPen(QPen(self._qcolor(color), width))
        p.setBrush(self._qcolor(Color(0, 0, 0, 0)))
        hw, hh = size.x / 2.0, size.y / 2.0
        p.drawRect(int(-hw), int(-hh), int(size.x), int(size.y))
        p.restore()

    def draw_circle(self, world_pos: Vector2, radius: float, color: Color) -> None:
        p = self.painter
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        p.save()
        p.translate(sp.x, sp.y)
        p.scale(zoom, zoom)
        p.setBrush(self._qcolor(color))
        p.setPen(self._qcolor(Color(0, 0, 0, 0)))
        p.drawEllipse(int(-radius), int(-radius), int(radius * 2),
                      int(radius * 2))
        p.restore()

    def draw_polygon(self, world_verts, color: Color, outline: Color = None) -> None:
        from PySide6.QtGui import QPolygonF, QPointF, QPen
        p = self.painter
        poly = QPolygonF()
        for v in world_verts:
            s = self.world_to_screen(v)
            poly.append(QPointF(s.x, s.y))
        p.setBrush(self._qcolor(color))
        p.setPen(QPen(self._qcolor(outline or Color(0, 0, 0, 0)), 1))
        p.drawPolygon(poly)

    def draw_line(self, a: Vector2, b: Vector2, color: Color, width: float = 1.0) -> None:
        from PySide6.QtGui import QPen
        p = self.painter
        sa = self.world_to_screen(a)
        sb = self.world_to_screen(b)
        p.setPen(QPen(self._qcolor(color), width))
        p.drawLine(int(sa.x), int(sa.y), int(sb.x), int(sb.y))

    def draw_text(self, world_pos: Vector2, text: str, color: Color,
                  font_size: int = 16, align: str = "left",
                  outline_color: Color = None, outline_size: int = 0) -> None:
        from PySide6.QtGui import QFont, QPen
        p = self.painter
        sp = self.world_to_screen(world_pos)
        f = QFont("sans-serif")
        f.setPixelSize(font_size)
        p.setFont(f)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text)
        if align == "center":
            sp = Vector2(sp.x - tw / 2.0, sp.y)
        elif align == "right":
            sp = Vector2(sp.x - tw, sp.y)
        if outline_size > 0 and outline_color is not None:
            pen = QPen(self._qcolor(outline_color), 1)
            p.setPen(pen)
            for dx in range(-outline_size, outline_size + 1):
                for dy in range(-outline_size, outline_size + 1):
                    if dx == 0 and dy == 0:
                        continue
                    p.drawText(int(sp.x + dx), int(sp.y + dy), text)
        p.setPen(QPen(self._qcolor(color), 1))
        p.drawText(int(sp.x), int(sp.y), text)

    def draw_collision_shape(self, node) -> None:
        from PySide6.QtGui import QPen
        p = self.painter
        shape = node.build_shape()
        verts = shape.world_vertices(node.get_global_position(),
                                    math.radians(node.rotation), node.scale)
        if len(verts) == 1:  # circle
            c = verts[0]
            r = shape.scaled_radius(node.scale)
            sp = self.world_to_screen(c)
            zoom = self.camera.zoom if self.camera else 1.0
            p.save()
            p.translate(sp.x, sp.y)
            p.scale(zoom, zoom)
            p.setPen(QPen(self._qcolor(Color(0.2, 0.8, 1.0, 0.9)), 1))
            p.setBrush(self._qcolor(Color(0, 0, 0, 0)))
            p.drawEllipse(int(-r), int(-r), int(r * 2), int(r * 2))
            p.restore()
        else:
            p.setPen(QPen(self._qcolor(Color(0.2, 0.8, 1.0, 0.9)), 1))
            p.setBrush(self._qcolor(Color(0, 0, 0, 0)))
            for i in range(len(verts)):
                a = self.world_to_screen(verts[i])
                b = self.world_to_screen(verts[(i + 1) % len(verts)])
                p.drawLine(int(a.x), int(a.y), int(b.x), int(b.y))

    # ------------------------------------------------------------------
    def draw_light(self, world_pos: Vector2, radius: float, color: Color,
                   energy: float = 1.0) -> None:
        from PySide6.QtGui import QRadialGradient, QBrush, QPainter
        from engine.rendering.lighting import gradient_stops
        p = self.painter
        sp = self.world_to_screen(world_pos)
        zoom = self.camera.zoom if self.camera else 1.0
        r = radius * zoom
        if r <= 0:
            return
        grad = QRadialGradient(sp.x, sp.y, r)
        base = Color(color.r, color.g, color.b, color.a)
        for pos, intensity in gradient_stops():
            grad.setColorAt(pos, self._qcolor(
                Color(base.r, base.g, base.b, base.a * energy * intensity)))
        p.save()
        try:
            # additive blending so multiple lights accumulate
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setBrush(QBrush(grad))
            p.setPen(self._qcolor(Color(0, 0, 0, 0)))
            p.drawEllipse(int(sp.x - r), int(sp.y - r), int(r * 2), int(r * 2))
        finally:
            p.restore()

    def draw_vignette(self, strength: float, color: Color) -> None:
        from PySide6.QtGui import QRadialGradient, QBrush
        p = self.painter
        w, h = self.viewport_w, self.viewport_h
        cx, cy = w / 2.0, h / 2.0
        r = max(w, h) * 0.75
        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0.0, self._qcolor(Color(color.r, color.g, color.b, 0.0)))
        grad.setColorAt(1.0, self._qcolor(Color(color.r, color.g, color.b,
                                               min(1.0, strength))))
        p.save()
        p.setBrush(QBrush(grad))
        p.setPen(self._qcolor(Color(0, 0, 0, 0)))
        p.drawRect(0, 0, w, h)
        p.restore()

    # ------------------------------------------------------------------
    # render() / render_root() / _render_node() are inherited from Renderer2DBase

