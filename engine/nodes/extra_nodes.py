"""Additional built-in nodes: tween, audio, visibility notifier and parallax.

These build on the existing core / rendering / scene APIs and register
themselves with the global node registry through ``@register_node``, so they
appear automatically in the editor's *Create Node* dialog and in the scene
loader without any further wiring.
"""
from __future__ import annotations

import math
import os

from engine.core.math2d import Vector2, Color, Rect2
from engine.core.node import (PropertyDef, PT_FLOAT, PT_BOOL, PT_COLOR,
                              PT_STRING, PT_INT, PT_ENUM, PT_RESOURCE,
                              PT_NODE_PATH, PT_VECTOR2, Node)
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D
from engine.nodes.sprite import Sprite2D


# ----------------------------------------------------------------------
# Tween
# ----------------------------------------------------------------------
_EASE = ["linear", "ease_in", "ease_out", "ease_in_out"]


def _ease(t: float, kind: str) -> float:
    if kind == "ease_in":
        return t * t
    if kind == "ease_out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if kind == "ease_in_out":
        return t * t * (3.0 - 2.0 * t)
    return t


@register_node("Misc")
class Tween(Node):
    """Interpolates a numeric property of a target node over ``duration``
    seconds and emits ``tween_completed`` when finished.

    ``target_path`` is a node path relative to this Tween.  ``property`` names
    the attribute to animate and may use dotted component access such as
    ``position.x``, ``modulate.a`` or ``rotation`` (so you can tween a single
    axis / colour channel directly).
    """

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("duration", PT_FLOAT, 1.0, group="Tween", min_value=0.01),
        PropertyDef("ease", PT_ENUM, "linear", group="Tween", options=_EASE),
        PropertyDef("repeat", PT_BOOL, False, group="Tween"),
        PropertyDef("autostart", PT_BOOL, False, group="Tween"),
        PropertyDef("target_path", PT_NODE_PATH, "", group="Tween",
                    hint="path to the node to animate"),
        PropertyDef("property", PT_STRING, "modulate.a", group="Tween"),
        PropertyDef("from", PT_FLOAT, 0.0, group="Tween"),
        PropertyDef("to", PT_FLOAT, 1.0, group="Tween"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("tween_started")
        self.add_signal("tween_completed")
        self._t = 0.0
        self._active = False

    def _ready(self) -> None:
        if self.autostart:
            self.start()

    # ----- control -----
    def start(self) -> None:
        self._t = 0.0
        self._active = True
        self.emit("tween_started")

    def stop(self) -> None:
        self._active = False

    def is_active(self) -> bool:
        return self._active

    # ----- internals -----
    def _target(self):
        if not self.target_path:
            return None
        return self.get_node(self.target_path)

    @staticmethod
    def _set(obj, path: str, value) -> None:
        parts = path.split(".")
        cur = obj
        for part in parts[:-1]:
            cur = getattr(cur, part)
        setattr(cur, parts[-1], value)

    def _process(self, delta: float) -> None:
        if not self._active:
            return
        target = self._target()
        if target is None:
            return
        self._t += delta
        raw = min(1.0, self._t / self.duration)
        k = _ease(raw, self.ease)
        value = self.get_property("from") + (
            self.get_property("to") - self.get_property("from")) * k
        try:
            Tween._set(target, self.property, value)
        except Exception:
            self._active = False
            return
        if raw >= 1.0:
            if self.repeat:
                self._t = 0.0
                self.emit("tween_started")
            else:
                self._active = False
                self.emit("tween_completed")


# ----------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------
try:
    from PySide6.QtMultimedia import QSoundEffect
    from PySide6.QtCore import QUrl
    _HAS_AUDIO = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_AUDIO = False


@register_node("Audio")
class AudioStreamPlayer(Node):
    """Plays a sound effect / music file.  Uses Qt's ``QSoundEffect`` when the
    multimedia module is available; otherwise it simply stores the path (so it
    is still useful as a data holder and from scripts)."""

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("stream", PT_RESOURCE, "", group="Audio",
                    hint="audio file", resource_ext="wav,ogg,mp3"),
        PropertyDef("volume_db", PT_FLOAT, 0.0, group="Audio",
                    min_value=-80.0, max_value=24.0),
        PropertyDef("pitch_scale", PT_FLOAT, 1.0, group="Audio",
                    min_value=0.01, max_value=16.0),
        PropertyDef("loop", PT_BOOL, False, group="Audio"),
        PropertyDef("autoplay", PT_BOOL, False, group="Audio"),
        PropertyDef("playing", PT_BOOL, False, group="Audio"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("finished")
        self._effect = None          # Qt QSoundEffect (editor)
        self._py_sound = None        # pygame Sound (standalone build)
        self._py_channel = None      # pygame Channel

    def _ready(self) -> None:
        if self.autoplay:
            self.play()

    def _resolve_path(self) -> str:
        engine = getattr(self.tree, "engine", None)
        base = getattr(engine, "project_dir", "") or ""
        if os.path.isabs(self.stream):
            return self.stream
        return os.path.join(base, self.stream) if base else self.stream

    def play(self) -> None:
        self.playing = True
        path = self._resolve_path()
        if not path:
            return
        if _HAS_AUDIO:
            try:
                if self._effect is None:
                    self._effect = QSoundEffect()
                self._effect.setSource(QUrl.fromLocalFile(path))
                self._effect.setLoopCount(-1 if self.loop else 1)
                vol = max(0.0, 10.0 ** (self.volume_db / 20.0))
                self._effect.setVolume(vol)
                self._effect.play()
                return
            except Exception as exc:  # pragma: no cover
                print(f"[AudioStreamPlayer] QSound play failed: {exc}")
        # standalone / pygame build: use pygame.mixer so audio is not a no-op
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            snd = pygame.mixer.Sound(path)
            snd.set_volume(max(0.0, min(1.0, 10.0 ** (self.volume_db / 20.0))))
            loops = -1 if self.loop else 0
            self._py_channel = snd.play(loops=loops)
            self._py_sound = snd
        except Exception as exc:
            print(f"[AudioStreamPlayer] pygame play failed: {exc}")

    def stop(self) -> None:
        self.playing = False
        if self._effect is not None:
            try:
                self._effect.stop()
            except Exception:
                pass
        if self._py_channel is not None:
            try:
                self._py_channel.stop()
            except Exception:
                pass
        self._py_channel = None


# ----------------------------------------------------------------------
# VisibilityNotifier2D
# ----------------------------------------------------------------------
@register_node("Node2D")
class VisibilityNotifier2D(Node2D):
    """Emits ``screen_entered`` / ``screen_exited`` when the node's origin
    enters or leaves the active camera's viewport."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("extents", PT_VECTOR2, Vector2(100, 100), group="Visibility"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("screen_entered")
        self.add_signal("screen_exited")
        self._inside = False

    def is_on_screen(self) -> bool:
        return self._inside

    def _process(self, delta: float) -> None:
        cam = self.tree.find_camera() if self.tree is not None else None
        engine = self.tree.engine if self.tree is not None else None
        renderer = getattr(engine, "renderer", None) if engine else None
        if cam is None or renderer is None:
            return
        z = cam.zoom if cam.zoom > 0 else 1.0
        c = cam.get_global_position() + cam.offset
        half_w = (renderer.viewport_w / 2.0) / z
        half_h = (renderer.viewport_h / 2.0) / z
        rect = Rect2(c.x - half_w, c.y - half_h, half_w * 2.0, half_h * 2.0)
        p = self.get_global_position()
        inside = (rect.x <= p.x <= rect.x + rect.w and
                  rect.y <= p.y <= rect.y + rect.h)
        if inside != self._inside:
            self._inside = inside
            self.emit("screen_entered" if inside else "screen_exited")


# ----------------------------------------------------------------------
# ParallaxBackground
# ----------------------------------------------------------------------
@register_node("Node2D")
class ParallaxBackground(Node2D):
    """A screen-space tiled background that scrolls slower than the camera to
    create a parallax effect.  It ignores its own transform and always fills the
    viewport, so it should be placed as a direct child of the scene root.

    ``parallax`` controls how much of the camera scroll is applied to the tiling
    (0 = fixed to the screen / infinitely far, 1 = scrolls exactly with the
    world).  ``scroll`` is an extra manual offset you can animate from a script
    (e.g. ``self.scroll = self.api.Vector2(t, 0)``) for things like flowing
    water or drifting clouds."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("texture", PT_RESOURCE, "", group="Parallax",
                    hint="background image", resource_ext="png,jpg,jpeg"),
        PropertyDef("parallax", PT_VECTOR2, Vector2(0.5, 0.5), group="Parallax"),
        PropertyDef("scroll", PT_VECTOR2, Vector2(0, 0), group="Parallax",
                    hint="manual scroll offset"),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            renderer.draw_tiled_background(self.texture, self.parallax,
                                          self.scroll)
        super()._draw(renderer, camera)


# ----------------------------------------------------------------------
# ParallaxObject
# ----------------------------------------------------------------------
@register_node("Node2D")
class ParallaxObject(Sprite2D):
    """A world object that participates in a parallax / perspective depth
    effect, producing a 3D *depth illusion* -- near objects move faster and look
    larger, far objects move slower and look smaller.

    Each frame it reads the active :class:`Camera2D` and, relative to the
    camera's *starting* position, shifts its drawn position by
    ``(cam_now - cam_start) * (1 - depth)``.  A distant object (``depth`` ~ 0)
    therefore barely moves on screen while a near object (``depth`` ~ 1) tracks
    the world normally -- the classic parallax trick.  When ``perspective`` is
    enabled its drawing is additionally scaled by ``lerp(scale_far, scale_near,
    depth)`` for the near-big / far-small look.

    This is a complete, self-contained node: it draws a texture (or a coloured
    placeholder when none is set), supports every Sprite2D feature (flip,
    offset, modulate, spritesheet) and works in both the editor preview and the
    shipped pygame build.  It is typically paired with a :class:`ParallaxBackground`
    (the far, screen-filling layer) to give a scene real sense of depth."""

    PROPERTIES = Sprite2D.PROPERTIES + [
        PropertyDef("depth", PT_FLOAT, 0.5, group="Parallax", min_value=0.0,
                    max_value=1.0, hint="0 = far, 1 = near"),
        PropertyDef("perspective", PT_BOOL, True, group="Parallax",
                    hint="near-big / far-small scaling"),
        PropertyDef("scale_near", PT_FLOAT, 1.5, group="Parallax",
                    min_value=0.01, hint="drawn scale at depth=1"),
        PropertyDef("scale_far", PT_FLOAT, 0.5, group="Parallax",
                    min_value=0.01, hint="drawn scale at depth=0"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._cam_start = None

    def _draw(self, renderer, camera) -> None:
        if not self.visible:
            super()._draw(renderer, camera)
            return
        cam = camera
        if cam is not None:
            # use the camera's *rendered* (smoothed + clamped) centre so the
            # parallax lags with camera easing instead of the raw movement
            cam_now = cam._render_center() + cam.offset
            if self._cam_start is None:
                self._cam_start = Vector2(cam_now.x, cam_now.y)
            q = 1.0 - self.depth
            shift = Vector2((cam_now.x - self._cam_start.x) * q,
                            (cam_now.y - self._cam_start.y) * q)
            authored = self.get_global_position()
            target = authored + shift
            # map the target world position back into this node's local space so
            # a rotated / scaled parent transform is respected
            parent = self.parent
            if parent is not None and isinstance(parent, Node2D):
                ppos, prot, pscale = parent._global_xform()
                d = target - ppos
                d = d.rotated(-prot)
                local = Vector2(d.x / pscale.x if pscale.x else d.x,
                                d.y / pscale.y if pscale.y else d.y)
            else:
                local = target
        else:
            local = self.position

        saved_pos = self.position
        saved_scale = self.scale
        self.position = local
        if self.perspective:
            mult = self.scale_far + (self.scale_near - self.scale_far) * self.depth
            self.scale = Vector2(saved_scale.x * mult, saved_scale.y * mult)
        try:
            super()._draw(renderer, camera)
        finally:
            self.position = saved_pos
            self.scale = saved_scale


# ----------------------------------------------------------------------
# UI: TextureRect & NinePatchRect
# ----------------------------------------------------------------------
@register_node("UI")
class TextureRect(Node2D):
    """Draws a texture inside a fixed rectangle.  Unlike :class:`Sprite2D` it is
    sized explicitly (great for HUD elements / backgrounds) and can tile or
    centre the image instead of following the node's texture aspect ratio."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("texture", PT_RESOURCE, "", group="TextureRect",
                    hint="image", resource_ext="png,jpg,jpeg"),
        PropertyDef("size", PT_VECTOR2, Vector2(120, 120), group="TextureRect",
                    min_value=1),
        PropertyDef("stretch_mode", PT_ENUM, "keep", group="TextureRect",
                    options=["keep", "tile", "center"]),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            if self.texture:
                renderer.draw_texture_rect(self.get_global_position(),
                                           self.size, self.texture,
                                           math.radians(self.rotation))
            else:
                renderer.draw_rect_outline(self.get_global_position(),
                                          self.size, Color(0.6, 0.6, 0.6, 1.0),
                                          math.radians(self.rotation))
        super()._draw(renderer, camera)


@register_node("UI")
class NinePatchRect(Node2D):
    """A 9-slice scalable panel: the texture's corners/edges keep their size
    while the centre stretches, so the panel can be resized without distortion.
    Margins are in source-pixel units."""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("texture", PT_RESOURCE, "", group="9Patch",
                    hint="image", resource_ext="png,jpg,jpeg"),
        PropertyDef("size", PT_VECTOR2, Vector2(200, 100), group="9Patch",
                    min_value=1),
        PropertyDef("margin_left", PT_INT, 10, group="9Patch", min_value=0),
        PropertyDef("margin_top", PT_INT, 10, group="9Patch", min_value=0),
        PropertyDef("margin_right", PT_INT, 10, group="9Patch", min_value=0),
        PropertyDef("margin_bottom", PT_INT, 10, group="9Patch", min_value=0),
    ]

    def _draw(self, renderer, camera) -> None:
        if self.visible:
            if self.texture:
                renderer.draw_nine_patch(
                    self.get_global_position(), self.size, self.texture,
                    (self.margin_left, self.margin_top,
                     self.margin_right, self.margin_bottom),
                    math.radians(self.rotation))
            else:
                renderer.draw_rect_outline(self.get_global_position(),
                                          self.size, Color(0.6, 0.6, 0.6, 1.0),
                                          math.radians(self.rotation))
        super()._draw(renderer, camera)


# ----------------------------------------------------------------------
# RemoteTransform2D
# ----------------------------------------------------------------------
@register_node("Node2D")
class RemoteTransform2D(Node2D):
    """把本节点的**全局变换**实时“推送”给另一个节点，实现节点之间的变换联动。

    典型配合：让一个影子 Sprite2D 跟随玩家（把它设为 ``remote``）、让多个物体
    共享同一条移动轨迹、做“镜像”效果。目标节点必须拥有
    ``position`` / ``rotation`` / ``scale``（即 Node2D 或其子类）。可分别用
    ``use_position`` / ``use_rotation`` / ``use_scale`` 开关要同步的轴。"""

    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("remote_path", PT_NODE_PATH, "", group="Remote",
                    hint="要同步到的目标节点路径"),
        PropertyDef("use_position", PT_BOOL, True, group="Remote"),
        PropertyDef("use_rotation", PT_BOOL, True, group="Remote"),
        PropertyDef("use_scale", PT_BOOL, True, group="Remote"),
    ]

    def _process(self, delta: float) -> None:
        super()._process(delta)
        if not self.remote_path:
            return
        target = self.get_node(self.remote_path)
        if target is not None:
            self._apply_to(target)

    def _apply_to(self, target) -> None:
        if not (hasattr(target, "position") and hasattr(target, "rotation")
                and hasattr(target, "scale")):
            return
        gp = self.get_global_position()
        gr = self.get_global_rotation()
        gs = self.get_global_scale()
        parent = target.parent
        p_is_xform = parent is not None and isinstance(parent, Node2D)
        if self.use_position:
            if p_is_xform:
                pp = parent.get_global_position()
                target.position = Vector2(gp.x - pp.x, gp.y - pp.y)
            else:
                target.position = Vector2(gp.x, gp.y)
        if self.use_rotation:
            if p_is_xform:
                target.rotation = math.degrees(
                    gr - parent.get_global_rotation())
            else:
                target.rotation = math.degrees(gr)
        if self.use_scale:
            if p_is_xform:
                ps = parent.get_global_scale()
                target.scale = Vector2(gs.x / ps.x if ps.x else gs.x,
                                      gs.y / ps.y if ps.y else gs.y)
            else:
                target.scale = Vector2(gs.x, gs.y)


# ----------------------------------------------------------------------
# Spawner
# ----------------------------------------------------------------------
@register_node("Node")
class Spawner(Node):
    """按固定间隔实例化一个场景（.tscn），把生成物作为自己的子节点；超过
    ``max_instances`` 时自动释放最旧的实例（轻量对象池）。

    生成物会被自动加入 ``group``（若设置），方便用
    ``get_nodes_in_group`` / ``call_group`` 统一控制——例如成批生成敌人、子弹、
    粒子化的小物体。``spawned`` 信号会带回刚生成的节点，便于写初始化脚本。可与
    RigidBody2D、分组系统、Timer 风格的逻辑配合。"""

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("scene", PT_RESOURCE, "", group="Spawner",
                    hint="要实例化的场景文件", resource_ext="tscn"),
        PropertyDef("interval", PT_FLOAT, 1.0, group="Spawner",
                    min_value=0.01),
        PropertyDef("max_instances", PT_INT, 10, group="Spawner",
                    min_value=0),
        PropertyDef("auto_start", PT_BOOL, False, group="Spawner"),
        PropertyDef("active", PT_BOOL, True, group="Spawner"),
        PropertyDef("group", PT_STRING, "", group="Spawner",
                    hint="生成物自动加入的分组名（可选）"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self.add_signal("spawned")
        self._timer = 0.0
        self._spawned = []

    def _ready(self) -> None:
        if self.auto_start:
            self.active = True

    def _process(self, delta: float) -> None:
        if not self.active or not self.scene:
            return
        self._timer += delta
        while self._timer >= self.interval:
            self._timer -= self.interval
            self.spawn_now()

    def _resolve(self, path: str) -> str:
        import os
        if os.path.isabs(path):
            return path
        base = getattr(getattr(self.tree, "engine", None), "project_dir", "") or ""
        return os.path.join(base, path) if base else path

    def spawn_now(self) -> None:
        """Instance the scene immediately and add it as a child."""
        if not self.scene or self.tree is None:
            return
        eng = getattr(self.tree, "engine", None)
        if eng is None:
            return
        from engine.core.scene_format import SceneLoader
        inst = SceneLoader(eng).load(self._resolve(self.scene))
        if inst is None:
            return
        self.add_child(inst)
        self._spawned.append(inst)
        if self.group:
            self.tree.add_to_group(inst, self.group)
        self.emit("spawned", inst)
        # drop any freed / invalid references
        self._spawned = [n for n in self._spawned
                         if n is not None
                         and getattr(n, "tree", None) is not None]
        while self.max_instances and len(self._spawned) > self.max_instances:
            old = self._spawned.pop(0)
            if old is not None:
                old.free()

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False


# ----------------------------------------------------------------------
# Joint2D (cooperative physics constraint between two RigidBody2D)
# ----------------------------------------------------------------------
@register_node("Physics")
class Joint2D(Node):
    """把两个 RigidBody2D 用约束连起来，让它们像被“钉在一起”或“用弹簧连着”一样
    协同运动。

    * ``joint_type = "pin"``    ：把两个刚体钉在同一个世界锚点（RevoluteJoint），
      围绕该点相对旋转（链条、摆锤）。
    * ``joint_type = "spring"`` ：保持两刚体间一段距离（DistanceJoint），像弹簧 /
      绳子（可拉伸的连接、破坏式结构）。

    通过 ``node_a_path`` / ``node_b_path`` 指向两个 RigidBody2D；引擎会自动取它们
    的物理体并在物理世界建立约束。``stiffness`` / ``damping`` 实时可调。"""

    PROPERTIES = Node.PROPERTIES + [
        PropertyDef("joint_type", PT_ENUM, "spring", group="Joint",
                    options=["spring", "pin"]),
        PropertyDef("node_a_path", PT_NODE_PATH, "", group="Joint",
                    hint="刚体 A 节点路径"),
        PropertyDef("node_b_path", PT_NODE_PATH, "", group="Joint",
                    hint="刚体 B 节点路径"),
        PropertyDef("rest_length", PT_FLOAT, 0.0, group="Joint",
                    min_value=0.0, hint="spring: 静止长度 (0=用初始距离)"),
        PropertyDef("stiffness", PT_FLOAT, 0.9, group="Joint",
                    min_value=0.0, max_value=1.0),
        PropertyDef("damping", PT_FLOAT, 0.1, group="Joint", min_value=0.0),
        PropertyDef("anchor", PT_VECTOR2, Vector2(0, 0), group="Joint",
                    hint="pin: 世界锚点 (0,0=自动取中点)"),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)
        self._joint = None

    def _physics_process(self, delta: float) -> None:
        if self._joint is not None:
            self._joint.stiffness = self.stiffness
            if hasattr(self._joint, "damping"):
                self._joint.damping = self.damping
            return
        if not self.node_a_path or not self.node_b_path \
                or self.tree is None or self.tree.physics is None:
            return
        a = self.get_node(self.node_a_path)
        b = self.get_node(self.node_b_path)
        if a is None or b is None:
            return
        ba = a.get_body() if hasattr(a, "get_body") else None
        bb = b.get_body() if hasattr(b, "get_body") else None
        if ba is None or bb is None:
            return  # 物理体尚未初始化，下一帧再试
        from engine.physics.joint import RevoluteJoint, DistanceJoint
        if self.joint_type == "pin":
            anc = self.anchor if (self.anchor.x or self.anchor.y) else None
            self._joint = RevoluteJoint(ba, bb, anchor=anc)
        else:
            rl = self.rest_length if self.rest_length > 0 else None
            self._joint = DistanceJoint(ba, bb, rest_length=rl)
        self._joint.stiffness = self.stiffness
        if hasattr(self._joint, "damping"):
            self._joint.damping = self.damping
        self.tree.physics.add_joint(self._joint)

    def _exit_tree(self) -> None:
        if self._joint is not None and self.tree is not None \
                and self.tree.physics is not None:
            self.tree.physics.remove_joint(self._joint)
        self._joint = None
        super()._exit_tree()
