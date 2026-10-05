"""Pygame rendering backend.

Mirrors the public surface of :class:`engine.rendering.Renderer2D` so the very
same node ``_draw`` code runs unchanged in the editor (Qt) or in a standalone
*pygame release* window.  This is the renderer used by the "Run (pygame)" button
in the editor and, later, by the packaged game executable.
"""
from __future__ import annotations

import math
import os
from typing import Dict, Optional, Tuple

import pygame

from engine.core.math2d import Vector2, Color
from engine.rendering.base import Renderer2DBase


class PygameRenderer(Renderer2DBase):
    """Draws the scene tree into a pygame surface each frame."""

    def __init__(self, resource_base: str = ""):
        super().__init__(resource_base)
        self.surface = None
        self._img_cache: Dict[str, Optional[pygame.Surface]] = {}
        self._light_grad = None  # cached unit radial-gradient sprite
        self._vig_ramp = None    # cached low-res vignette alpha ramp
        self._vig_ramp_key = None
        self._vig_final = None   # cached tinted/strength-scaled overlay
        self._vig_final_key = None

    # ------------------------------------------------------------------
    def begin(self, surface, w: int, h: int, camera) -> None:
        self.surface = surface
        self.viewport_w = w
        self.viewport_h = h
        self.camera = camera
        surface.fill(self._rgba(self.background))

    def end(self) -> None:
        self.surface = None

    # ------------------------------------------------------------------
    def _rgba(self, c: Color) -> Tuple[int, int, int, int]:
        return (int(max(0.0, min(1.0, c.r)) * 255),
                int(max(0.0, min(1.0, c.g)) * 255),
                int(max(0.0, min(1.0, c.b)) * 255),
                int(max(0.0, min(1.0, c.a)) * 255))

    def _load_image(self, path: str) -> Optional[pygame.Surface]:
        if not path:
            return None
        if path in self._img_cache:
            return self._img_cache[path]
        full = self._resolve(path)
        try:
            img = pygame.image.load(full).convert_alpha()
        except Exception:
            img = None
        self._img_cache[path] = img
        return img

    # ------------------------------------------------------------------
    def _blit(self, surf, center: Vector2, scale_x: float = 1.0,
              scale_y: float = 1.0, rotation_deg: float = 0.0,
              alpha: float = 1.0) -> None:
        if surf is None or self.surface is None:
            return
        s = surf
        if scale_x != 1.0 or scale_y != 1.0:
            w = max(1, int(s.get_width() * scale_x))
            h = max(1, int(s.get_height() * scale_y))
            s = pygame.transform.scale(s, (w, h))
        if rotation_deg != 0.0:
            s = pygame.transform.rotate(s, rotation_deg)
        if alpha < 1.0:
            s = s.copy()
            s.set_alpha(int(max(0.0, min(1.0, alpha)) * 255))
        rect = s.get_rect(center=(int(center.x), int(center.y)))
        self.surface.blit(s, rect)

    # ------------------------------------------------------------------
    def draw_sprite(self, sprite) -> None:
        gp = sprite.get_global_position()
        gr = sprite.get_global_rotation()
        gs = sprite.get_global_scale()
        sp = self.world_to_screen(gp)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0

        tex = getattr(sprite, "texture", "")
        img = self._load_image(tex) if tex else None
        if img is not None:
            hframes = max(1, int(getattr(sprite, "hframes", 1) or 1))
            vframes = max(1, int(getattr(sprite, "vframes", 1) or 1))
            if hframes > 1 or vframes > 1:
                fw = max(1, img.get_width() // hframes)
                fh = max(1, img.get_height() // vframes)
                frame = int(getattr(sprite, "frame", 0) or 0)
                fx = (frame % hframes) * fw
                fy = (frame // hframes % vframes) * fh
                img = img.subsurface((fx, fy, fw, fh))
            sprite.set_texture_size(img.get_width(), img.get_height())
            if getattr(sprite, "flip_h", False):
                img = pygame.transform.flip(img, True, False)
            if getattr(sprite, "flip_v", False):
                img = pygame.transform.flip(img, False, True)
            offset = getattr(sprite, "offset", Vector2(0, 0))
            centered = getattr(sprite, "centered", True)
            scale_x = gs.x * zoom
            scale_y = gs.y * zoom
            if centered:
                center = Vector2(sp.x + offset.x * zoom, sp.y + offset.y * zoom)
            else:
                w = img.get_width() * scale_x
                h = img.get_height() * scale_y
                center = Vector2(sp.x + offset.x * zoom + w / 2.0,
                                sp.y + offset.y * zoom + h / 2.0)
            mod = getattr(sprite, "modulate", None)
            alpha = mod.a if mod is not None else 1.0
            self._blit(img, center, scale_x, scale_y,
                       math.degrees(gr), alpha)
        else:
            # No texture: draw the editor-style placeholder rectangle so the
            # scene stays visible without assets.  It is routed through the same
            # ``_blit`` transform path as a textured sprite, so scale / rotation /
            # offset are honoured identically.  Previously this branch ignored the
            # node's global scale and only applied the camera zoom, so placeholder
            # (untextured) sprites never scaled in the pygame build.
            w, h = sprite.get_texture_size().x, sprite.get_texture_size().y
            if w <= 0:
                w = 32
            if h <= 0:
                h = 32
            col = getattr(sprite, "modulate", Color(1, 1, 1, 1))
            alpha = col.a
            surf = pygame.Surface((max(1, int(w)), max(1, int(h))), pygame.SRCALPHA)
            surf.fill(self._rgba(col))
            pygame.draw.rect(surf, (0, 0, 0, 153), surf.get_rect(), 1)
            sprite.set_texture_size(w, h)
            offset = getattr(sprite, "offset", Vector2(0, 0))
            centered = getattr(sprite, "centered", True)
            scale_x = gs.x * zoom
            scale_y = gs.y * zoom
            if centered:
                center = Vector2(sp.x + offset.x * zoom, sp.y + offset.y * zoom)
            else:
                cw = w * scale_x
                ch = h * scale_y
                center = Vector2(sp.x + offset.x * zoom + cw / 2.0,
                                sp.y + offset.y * zoom + ch / 2.0)
            self._blit(surf, center, scale_x, scale_y, math.degrees(gr), alpha)

    def draw_tiled_background(self, texture: str, parallax: Vector2 = None,
                             scroll: Vector2 = None) -> None:
        if not texture:
            return
        img = self._load_image(texture)
        if img is None:
            return
        tw, th = img.get_width(), img.get_height()
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
                self.surface.blit(img, (int(x), int(y)))
                y += th
            x += tw

    def draw_rect(self, world_pos: Vector2, size: Vector2, color: Color,
                  rotation: float = 0.0) -> None:
        sp = self.world_to_screen(world_pos)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        w, h = size.x * zoom, size.y * zoom
        if rotation == 0.0:
            rect = pygame.Rect(int(sp.x - w / 2), int(sp.y - h / 2),
                               int(w), int(h))
            self.surface.fill(self._rgba(color), rect)
        else:
            surf = pygame.Surface((max(1, int(w)), max(1, int(h))),
                                 pygame.SRCALPHA)
            surf.fill(self._rgba(color))
            self._blit(surf, sp, 1.0, 1.0, math.degrees(rotation), 1.0)

    def draw_texture_rect(self, world_pos: Vector2, size: Vector2, texture: str,
                          rotation: float = 0.0, modulate: Color = None) -> None:
        if not texture:
            return
        img = self._load_image(texture)
        if img is None:
            return
        sp = self.world_to_screen(world_pos)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        sw, sh = img.get_width(), img.get_height()
        scale_x = (size.x * zoom / sw) if sw else 1.0
        scale_y = (size.y * zoom / sh) if sh else 1.0
        alpha = modulate.a if modulate is not None else 1.0
        self._blit(img, sp, scale_x, scale_y, math.degrees(rotation), alpha)

    def draw_nine_patch(self, world_pos: Vector2, size: Vector2, texture: str,
                       margins: tuple, rotation: float = 0.0) -> None:
        if not texture:
            return
        img = self._load_image(texture)
        if img is None or img.get_width() == 0 or img.get_height() == 0:
            return
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        sw, sh = img.get_width(), img.get_height()
        ml, mt, mr, mb = (max(0, int(m)) for m in margins)
        ml, mr = min(ml, sw - 1), min(mr, sw - 1)
        mt, mb = min(mt, sh - 1), min(mb, sh - 1)
        dw, dh = int(size.x * zoom), int(size.y * zoom)
        cw = max(0, dw - ml - mr)
        ch = max(0, dh - mt - mb)
        scw = max(0, sw - ml - mr)
        sch = max(0, sh - mt - mb)

        dest = pygame.Surface((max(1, dw), max(1, dh)), pygame.SRCALPHA)
        dx1, dx2 = ml, ml + cw
        dy1, dy2 = mt, mt + ch
        sx1, sx2 = ml, sw - mr
        sy1, sy2 = mt, sh - mb

        def blit(sx, sy, swc, shc, dx, dy, dwc, dhc):
            if dwc <= 0 or dhc <= 0 or swc <= 0 or shc <= 0:
                return
            sub = img.subsurface((int(sx), int(sy), int(swc), int(shc)))
            if dwc != swc or dhc != shc:
                sub = pygame.transform.scale(sub, (max(1, int(dwc)),
                                                  max(1, int(dhc))))
            dest.blit(sub, (int(dx), int(dy)))

        blit(0, 0, ml, mt, 0, 0, ml, mt)
        blit(sx1, 0, scw, mt, dx1, 0, cw, mt)
        blit(sx2, 0, mr, mt, dx2, 0, mr, mt)
        blit(0, sy1, ml, sch, 0, dy1, ml, ch)
        blit(sx1, sy1, scw, sch, dx1, dy1, cw, ch)
        blit(sx2, sy1, mr, sch, dx2, dy1, mr, ch)
        blit(0, sy2, ml, mb, 0, dy2, ml, mb)
        blit(sx1, sy2, scw, mb, dx1, dy2, cw, mb)
        blit(sx2, sy2, mr, mb, dx2, dy2, mr, mb)

        sp = self.world_to_screen(world_pos)
        self._blit(dest, sp, 1.0, 1.0, math.degrees(rotation), 1.0)

    def draw_rect_outline(self, world_pos: Vector2, size: Vector2, color: Color,
                         rotation: float = 0.0, width: float = 1.0) -> None:
        sp = self.world_to_screen(world_pos)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        w, h = size.x * zoom, size.y * zoom
        lw = max(1, int(width))
        if rotation == 0.0:
            rect = pygame.Rect(int(sp.x - w / 2), int(sp.y - h / 2),
                               int(w), int(h))
            pygame.draw.rect(self.surface, self._rgba(color), rect, lw)
        else:
            surf = pygame.Surface((max(1, int(w)), max(1, int(h))),
                                 pygame.SRCALPHA)
            pygame.draw.rect(surf, self._rgba(color), surf.get_rect(), lw)
            self._blit(surf, sp, 1.0, 1.0, math.degrees(rotation), 1.0)

    def draw_circle(self, world_pos: Vector2, radius: float, color: Color) -> None:
        sp = self.world_to_screen(world_pos)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        pygame.draw.circle(self.surface, self._rgba(color),
                           (int(sp.x), int(sp.y)), int(radius * zoom))

    def draw_polygon(self, world_verts, color: Color, outline: Color = None) -> None:
        pts = [(int(self.world_to_screen(v).x), int(self.world_to_screen(v).y))
               for v in world_verts]
        if len(pts) >= 3:
            pygame.draw.polygon(self.surface, self._rgba(color), pts)
        if outline is not None and len(pts) >= 2:
            pygame.draw.polygon(self.surface, self._rgba(outline), pts, 1)

    def draw_line(self, a: Vector2, b: Vector2, color: Color,
                  width: float = 1.0) -> None:
        sa = self.world_to_screen(a)
        sb = self.world_to_screen(b)
        pygame.draw.line(self.surface, self._rgba(color),
                        (int(sa.x), int(sa.y)), (int(sb.x), int(sb.y)),
                        max(1, int(width)))

    def draw_text(self, world_pos: Vector2, text: str, color: Color,
                  font_size: int = 16, align: str = "left",
                  outline_color: Color = None, outline_size: int = 0) -> None:
        sp = self.world_to_screen(world_pos)
        try:
            font = pygame.font.Font(None, int(font_size))
        except Exception:
            font = pygame.font.SysFont("sans", int(font_size))
        surf = font.render(str(text), True, self._rgba(color))
        tw = surf.get_width()
        if align == "center":
            x = sp.x - tw / 2.0
        elif align == "right":
            x = sp.x - tw
        else:
            x = sp.x
        pos = (int(x), int(sp.y))
        if outline_size > 0 and outline_color is not None:
            for dx in range(-outline_size, outline_size + 1):
                for dy in range(-outline_size, outline_size + 1):
                    if dx == 0 and dy == 0:
                        continue
                    self.surface.blit(surf, (pos[0] + dx, pos[1] + dy))
        self.surface.blit(surf, pos)

    def draw_collision_shape(self, node) -> None:
        shape = node.build_shape()
        verts = shape.world_vertices(node.get_global_position(),
                                    math.radians(node.rotation), node.scale)
        col = (51, 204, 255, 230)
        if len(verts) == 1:  # circle
            c = verts[0]
            r = shape.scaled_radius(node.scale)
            sp = self.world_to_screen(c)
            cam = self.camera
            zoom = cam.zoom if cam else 1.0
            pygame.draw.circle(self.surface, col, (int(sp.x), int(sp.y)),
                               int(r * zoom), 1)
        else:
            pts = [(int(self.world_to_screen(v).x), int(self.world_to_screen(v).y))
                   for v in verts]
            pygame.draw.lines(self.surface, col, True, pts, 1)

    def _build_light_grad(self):
        if self._light_grad is not None:
            return self._light_grad
        from engine.rendering.lighting import light_intensity
        s = 256
        half = s // 2
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        # The gradient is composited additively, and additive blending adds the
        # sprite's *RGB* -- alpha is ignored.  So we bake the falloff into RGB
        # (grey ramp: intensity -> RGB) instead of into alpha; the tint/energy
        # are applied later with a multiply.  Centre = bright, rim = black=off.
        px = pygame.PixelArray(surf)
        try:
            for y in range(s):
                for x in range(s):
                    dx = x - half
                    dy = y - half
                    d = math.hypot(dx, dy) / half
                    if d >= 1.0:
                        continue  # leave fully transparent (RGB 0) outside
                    v = int(light_intensity(d) * 255)
                    px[x, y] = (v, v, v, 255)
        finally:
            del px
        self._light_grad = surf
        return surf

    def draw_light(self, world_pos: Vector2, radius: float, color: Color,
                   energy: float = 1.0) -> None:
        sp = self.world_to_screen(world_pos)
        cam = self.camera
        zoom = cam.zoom if cam else 1.0
        r = int(radius * zoom)
        if r <= 0 or self.surface is None:
            return
        grad = self._build_light_grad()
        # scale the unit gradient sprite to the light radius
        size = (max(1, r * 2), max(1, r * 2))
        light = pygame.transform.scale(grad, size)
        # tint + energy: the grey falloff ramp (RGB) is multiplied by
        # colour * energy, then added to the scene -> a soft coloured glow.
        e = max(0.0, min(1.0, energy)) * max(0.0, min(1.0, color.a))
        tint = (int(max(0.0, min(1.0, color.r * e)) * 255),
                int(max(0.0, min(1.0, color.g * e)) * 255),
                int(max(0.0, min(1.0, color.b * e)) * 255), 255)
        light.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
        # composite additively so overlapping lights accumulate (matches Qt)
        self.surface.blit(light, (int(sp.x - r), int(sp.y - r)),
                          special_flags=pygame.BLEND_RGB_ADD)

    def _build_vignette_ramp(self, w: int, h: int) -> pygame.Surface:
        """Low-res radial alpha ramp (clear centre -> opaque corners)."""
        if self._vig_ramp is not None and self._vig_ramp_key == (w, h):
            return self._vig_ramp
        rs = 256
        rw = rs
        rh = max(1, int(rs * h / max(1, w)))
        surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
        cx, cy = rw / 2.0, rh / 2.0
        maxd = math.hypot(cx, cy)
        px = pygame.PixelArray(surf)
        try:
            for y in range(rh):
                for x in range(rw):
                    d = math.hypot(x - cx, y - cy) / maxd  # 0 centre .. 1 corner
                    t = max(0.0, min(1.0, (d - 0.25) / 0.75))
                    px[x, y] = (255, 255, 255, int(t * 255))
        finally:
            del px
        ramp = pygame.transform.smoothscale(surf, (w, h))
        self._vig_ramp = ramp
        self._vig_ramp_key = (w, h)
        return ramp

    def draw_vignette(self, strength: float, color: Color) -> None:
        w, h = self.viewport_w, self.viewport_h
        if w <= 0 or h <= 0 or self.surface is None:
            return
        s = max(0.0, min(1.0, strength))
        if s <= 0.0:
            return
        key = (w, h, round(s, 3), round(color.r, 3), round(color.g, 3),
               round(color.b, 3))
        if self._vig_final is None or self._vig_final_key != key:
            vig = self._build_vignette_ramp(w, h).copy()
            # tint the white ramp with the vignette colour ...
            vig.fill((int(color.r * 255), int(color.g * 255),
                      int(color.b * 255), 255),
                     special_flags=pygame.BLEND_RGB_MULT)
            # ... then scale the whole alpha ramp by the strength
            vig.fill((255, 255, 255, int(s * 255)),
                     special_flags=pygame.BLEND_RGBA_MULT)
            self._vig_final = vig
            self._vig_final_key = key
        self.surface.blit(self._vig_final, (0, 0))

    # ------------------------------------------------------------------
    # render() / render_root() / _render_tree() are inherited from
    # Renderer2DBase, which implements z_index + CanvasLayer.layer aware
    # draw ordering.
