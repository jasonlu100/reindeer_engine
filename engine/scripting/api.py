"""Scripting API exposed to user scripts.

When a script is attached to a node, the engine injects a
:class:`ScriptAPI` instance (and a number of convenience methods) onto the
script object.  This is the documented surface that user code programs
against -- it deliberately mirrors Godot's scripting API so behaviour is
familiar: lifecycle callbacks, node access, input, signals, resources and
time/utilities are all reachable from ``self`` inside a script.
"""
from __future__ import annotations

import math
import random
from typing import Any, Optional

from engine.core.math2d import Vector2, Color, Rect2


class ScriptAPI:
    """The bridge object handed to every attached user script.

    Inside a script you typically access these through ``self`` (they are
    injected as bound methods), e.g. ``self.get_node("Player")`` or
    ``self.is_action_pressed("ui_right")``.
    """

    def __init__(self, node, engine):
        self.node = node
        self.engine = engine

    # ------------------------------------------------------------------
    # node operations
    # ------------------------------------------------------------------
    def get_node(self, path: str):
        """Return the node at ``path`` (relative or absolute like Godot)."""
        return self.node.get_node(path)

    def get_node_or_null(self, path: str):
        try:
            return self.node.get_node(path)
        except Exception:
            return None

    def get_tree(self):
        """Return the :class:`SceneTree` (the "world")."""
        return self.node.tree

    def free(self) -> None:
        """Free the owning node."""
        self.node.free()

    def queue_free(self) -> None:
        """Free the owning node (alias of :meth:`free`)."""
        self.node.free()

    def get_parent(self):
        """Return the node's parent (or None)."""
        return self.node.get_parent()

    def get_children(self):
        """Return a list of the node's children."""
        return self.node.get_children()

    def add_child(self, node) -> None:
        """Add ``node`` as a child of this node."""
        self.node.add_child(node)

    def remove_child(self, node) -> None:
        """Remove ``node`` from this node's children."""
        self.node.remove_child(node)

    def find_node(self, name: str, recursive: bool = True):
        """Search this node's subtree (or the whole tree) for a node by name."""
        return self.node.find_node(name, recursive)

    def has_node(self, path: str) -> bool:
        """True if a node exists at ``path``."""
        return self.node.has_node(path)

    def get_child(self, index: int):
        """Return the direct child at ``index``."""
        return self.node.get_child(index)

    def get_child_count(self) -> int:
        """Number of direct children."""
        return self.node.get_child_count()

    def get_index(self) -> int:
        """Index of this node among its parent's children."""
        return self.node.get_index()

    def get_path(self) -> str:
        """Absolute path of this node within the tree."""
        return self.node.get_path()

    def reparent(self, new_parent) -> None:
        """Move this node to become a child of ``new_parent``."""
        node = self.node
        if node.parent is not None:
            node.parent.remove_child(node)
        new_parent.add_child(node)

    # ----- transform helpers (Node2D-like) -----
    def get_position(self) -> Vector2:
        p = getattr(self.node, "position", None)
        return Vector2(p.x, p.y) if p is not None else Vector2(0, 0)

    def set_position(self, p: Vector2) -> None:
        if hasattr(self.node, "position"):
            self.node.position = Vector2(p.x, p.y)

    def get_rotation(self) -> float:
        """Rotation in radians (the node stores it in degrees)."""
        return math.radians(getattr(self.node, "rotation", 0.0) or 0.0)

    def set_rotation(self, rad: float) -> None:
        if hasattr(self.node, "rotation"):
            self.node.rotation = math.degrees(rad)

    def get_rotation_degrees(self) -> float:
        return float(getattr(self.node, "rotation", 0.0) or 0.0)

    def set_rotation_degrees(self, deg: float) -> None:
        if hasattr(self.node, "rotation"):
            self.node.rotation = deg

    def get_scale(self) -> Vector2:
        s = getattr(self.node, "scale", None)
        return Vector2(s.x, s.y) if s is not None else Vector2(1, 1)

    def set_scale(self, s: Vector2) -> None:
        if hasattr(self.node, "scale"):
            self.node.scale = Vector2(s.x, s.y)

    def get_global_position(self) -> Vector2:
        g = getattr(self.node, "get_global_position", None)
        return g() if g else Vector2(0, 0)

    def set_global_position(self, p: Vector2) -> None:
        node = self.node
        if hasattr(node, "position"):
            parent = node.parent
            if parent is not None and hasattr(parent, "get_global_position"):
                pp = parent.get_global_position()
                node.position = Vector2(p.x - pp.x, p.y - pp.y)
            else:
                node.position = Vector2(p.x, p.y)

    def get_global_rotation(self) -> float:
        g = getattr(self.node, "get_global_rotation", None)
        return g() if g else 0.0

    def set_global_rotation(self, rad: float) -> None:
        node = self.node
        if hasattr(node, "rotation"):
            parent = node.parent
            if parent is not None and hasattr(parent, "get_global_rotation"):
                node.rotation = math.degrees(rad - parent.get_global_rotation())
            else:
                node.rotation = math.degrees(rad)

    def get_global_scale(self) -> Vector2:
        g = getattr(self.node, "get_global_scale", None)
        return g() if g else Vector2(1, 1)

    def set_global_scale(self, s: Vector2) -> None:
        node = self.node
        if hasattr(node, "scale"):
            parent = node.parent
            if parent is not None and hasattr(parent, "get_global_scale"):
                ps = parent.get_global_scale()
                node.scale = Vector2(s.x / ps.x if ps.x else 1.0,
                                    s.y / ps.y if ps.y else 1.0)
            else:
                node.scale = Vector2(s.x, s.y)

    def set_visible(self, v: bool) -> None:
        if hasattr(self.node, "visible"):
            self.node.visible = bool(v)

    def is_visible(self) -> bool:
        return bool(getattr(self.node, "visible", True))

    # ------------------------------------------------------------------
    # input handling
    # ------------------------------------------------------------------
    def _input(self):
        return self.engine.input if self.engine else None

    def is_action_pressed(self, action: str) -> bool:
        """True while ``action`` is held down."""
        inp = self._input()
        return inp.is_action_pressed(action) if inp else False

    def is_action_just_pressed(self, action: str) -> bool:
        """True only on the frame ``action`` was pressed."""
        inp = self._input()
        return inp.is_action_just_pressed(action) if inp else False

    def is_action_just_released(self, action: str) -> bool:
        inp = self._input()
        return inp.is_action_just_released(action) if inp else False

    def is_key_pressed(self, key: str) -> bool:
        inp = self._input()
        return inp.is_key_pressed(key) if inp else False

    def is_mouse_button_pressed(self, button: int) -> bool:
        inp = self._input()
        return inp.is_mouse_button_pressed(button) if inp else False

    def is_mouse_button_just_pressed(self, button: int) -> bool:
        inp = self._input()
        return inp.is_mouse_button_just_pressed(button) if inp else False

    def get_mouse_position(self) -> Vector2:
        """Mouse position in *screen* space."""
        inp = self._input()
        return inp.get_mouse_position() if inp else Vector2(0, 0)

    def get_mouse_world_position(self) -> Vector2:
        """Mouse position converted to world space using the active camera."""
        inp = self._input()
        if not inp or not self.engine:
            return Vector2(0, 0)
        cam = self.engine.tree.find_camera()
        if cam is None:
            return inp.get_mouse_position()
        return cam.screen_to_world(inp.get_mouse_position(),
                                   *self.get_viewport_size())

    def get_viewport_size(self):
        r = self.engine.renderer if self.engine else None
        if r is not None:
            return (r.viewport_w, r.viewport_h)
        return (800, 600)

    # ------------------------------------------------------------------
    # signals / events
    # ------------------------------------------------------------------
    def connect(self, signal_name: str, callable_) -> None:
        """Connect a node signal to ``callable_``."""
        self.node.connect(signal_name, callable_)

    def emit(self, signal_name: str, *args) -> None:
        """Emit one of the node's signals."""
        self.node.emit(signal_name, *args)

    # ------------------------------------------------------------------
    # resources
    # ------------------------------------------------------------------
    def preload(self, path: str):
        """Load (and cache) a resource such as a texture or sub-scene."""
        if self.engine is None:
            return None
        return self.engine.resources.load(self._resolve(path))

    def load_scene(self, path: str):
        """Load a scene resource (returns the root node)."""
        if self.engine is None:
            return None
        from engine.core.scene_format import SceneLoader
        return SceneLoader(self.engine).load(self._resolve(path))

    def _resolve(self, path: str) -> str:
        import os
        if os.path.isabs(path):
            return path
        base = getattr(self.engine, "project_dir", "") or ""
        return os.path.join(base, path) if base else path

    # ------------------------------------------------------------------
    # time & utilities
    # ------------------------------------------------------------------
    @property
    def delta(self) -> float:
        """Seconds elapsed since the previous frame."""
        return self.engine.time.delta if self.engine else 0.0

    @property
    def time(self):
        return self.engine.time if self.engine else None

    def randf(self, a: float = 0.0, b: float = 1.0) -> float:
        return random.uniform(a, b)

    def randi(self, a: int, b: int) -> int:
        return random.randint(a, b)

    def clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def lerp(self, a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def print(self, *args) -> None:
        print("[script]", *args)

    def create_timer(self, interval: float, callback, oneshot: bool = True):
        """Schedule ``callback`` to run every ``interval`` seconds.

        If ``oneshot`` is True (default) it fires a single time, otherwise it
        repeats.  Returns a handle that can be passed to :meth:`remove_timer`.
        """
        if self.engine is None:
            return None
        return self.engine.add_timer(interval, callback, oneshot)

    def remove_timer(self, handle) -> None:
        """Cancel a timer previously created with :meth:`create_timer`."""
        if self.engine is not None:
            self.engine.remove_timer(handle)

    # ------------------------------------------------------------------
    # node helpers (aiming / geometry)
    # ------------------------------------------------------------------
    def look_at(self, target: "Vector2") -> None:
        """Rotate this node so its +X axis points at world point ``target``."""
        gp = self.get_global_position()
        ang = math.atan2(target.y - gp.y, target.x - gp.x)
        parent = self.node.parent
        if parent is not None and hasattr(parent, "get_global_rotation"):
            ang -= parent.get_global_rotation()
        self.set_rotation(ang)

    def distance_to(self, target: "Vector2") -> float:
        """Distance (world units) from this node to world point ``target``."""
        gp = self.get_global_position()
        return math.hypot(target.x - gp.x, target.y - gp.y)

    def angle_to(self, target: "Vector2") -> float:
        """Angle (radians, world space) from this node to ``target``."""
        gp = self.get_global_position()
        return math.atan2(target.y - gp.y, target.x - gp.x)

    def get_global_mouse_position(self) -> "Vector2":
        """Convenience alias for :meth:`get_mouse_world_position`."""
        return self.get_mouse_world_position()

    # ------------------------------------------------------------------
    # groups (tag nodes and address them collectively)
    # ------------------------------------------------------------------
    def add_to_group(self, name: str) -> None:
        tree = self.node.tree
        if tree is not None:
            tree.add_to_group(self.node, name)

    def is_in_group(self, name: str) -> bool:
        tree = self.node.tree
        return bool(tree is not None and tree.is_in_group(self.node, name))

    def remove_from_group(self, name: str) -> None:
        tree = self.node.tree
        if tree is not None:
            tree.remove_from_group(self.node, name)

    def instance(self, path: str):
        """Load ``path`` and return a *fresh* scene instance (a new root node).

        Equivalent to :meth:`load_scene` but named to read like Godot's
        ``instance()``; call it, then ``self.add_child(instance)`` to spawn it.
        """
        return self.load_scene(path)

    def is_instance_valid(self, obj) -> bool:
        """True if ``obj`` is still a live node (has not been freed)."""
        if obj is None:
            return False
        if type(obj).__name__ == "Node" or hasattr(obj, "tree"):
            return getattr(obj, "tree", None) is not None or \
                getattr(obj, "_in_tree", False)
        return True

    # ------------------------------------------------------------------
    # scene-wide helpers
    # ------------------------------------------------------------------
    def get_nodes_in_group(self, name: str) -> list:
        """All nodes tagged with ``name`` (see :meth:`add_to_group`)."""
        tree = self.node.tree
        return tree.get_nodes_in_group(name) if tree is not None else []

    def call_group(self, name: str, method: str, *args) -> None:
        """Call ``method(*args)`` on every node in group ``name``."""
        tree = self.node.tree
        if tree is not None:
            tree.call_group(name, method, *args)

    def set_pause(self, v: bool) -> None:
        """Pause / resume the whole scene tree (``SceneTree.paused``)."""
        tree = self.node.tree
        if tree is not None:
            tree.paused = bool(v)

    def is_paused(self) -> bool:
        tree = self.node.tree
        return bool(tree.paused) if tree is not None else False

    # ------------------------------------------------------------------
    # coordinate conversion (relative to this node)
    # ------------------------------------------------------------------
    def local_to_global(self, local: "Vector2") -> "Vector2":
        """Map a point in *this node's* local space to world coordinates."""
        gp = self.get_global_position()
        gr = self.get_global_rotation()
        gs = self.get_global_scale()
        return Vector2(local.x * gs.x, local.y * gs.y).rotated(gr) + gp

    def global_to_local(self, world: "Vector2") -> "Vector2":
        """Map a world point into *this node's* local space."""
        gp = self.get_global_position()
        gr = self.get_global_rotation()
        gs = self.get_global_scale()
        d = (world - gp).rotated(-gr)
        return Vector2(d.x / gs.x if gs.x else d.x,
                       d.y / gs.y if gs.y else d.y)

    # ------------------------------------------------------------------
    # math / motion helpers
    # ------------------------------------------------------------------
    def move_toward(self, current: "Vector2", target: "Vector2",
                    max_delta: float) -> "Vector2":
        """Move ``current`` toward ``target`` by at most ``max_delta`` units."""
        dx = target.x - current.x
        dy = target.y - current.y
        d = math.hypot(dx, dy)
        if d <= max_delta or d == 0:
            return Vector2(target.x, target.y)
        k = max_delta / d
        return Vector2(current.x + dx * k, current.y + dy * k)

    def angle_difference(self, a: float, b: float) -> float:
        """Smallest signed difference ``b - a`` wrapped to [-pi, pi]."""
        d = (b - a) % (2.0 * math.pi)
        if d > math.pi:
            d -= 2.0 * math.pi
        return d

    def rand_range(self, a: float, b: float) -> float:
        """Alias of :meth:`randf` for a random float in ``[a, b]``."""
        return random.uniform(a, b)

    # math types available to scripts
    Vector2 = Vector2
    Color = Color
    Rect2 = Rect2

    # ------------------------------------------------------------------
    def help(self) -> str:
        """Return a textual summary of the scripting API."""
        return SCRIPTING_API_DOCS


SCRIPTING_API_DOCS = """\
Reindeer Scripting API (Python)
==============================
Lifecycle callbacks you can define in your script class:
  def _ready(self):              # called once when the node enters the scene
  def _process(self, delta):     # called every render frame
  def _physics_process(self, dt):# called every physics step
  def _input(self, event):       # called for each input event
  def _draw(self, renderer, cam):# custom drawing
  def _exit(self):               # called when the node is removed

Everything on `self` that the API provides is forwarded automatically, so you
can call any of the following directly (e.g. self.get_node(\"Player\"),
self.Vector2(1, 2), self.delta, self.time, self.help()) -- no need to go
through self.api unless you prefer to.

Methods available on `self`:
  # node tree
  get_node(path), get_node_or_null(path), get_parent(), get_tree(),
  get_children(), find_node(name), has_node(path), get_child(i),
  get_child_count(), get_index(), get_path(), reparent(node),
  add_child(node), remove_child(node), queue_free(), free()
  # transforms (Node2D)
  get_position(), set_position(v), get_global_position(), set_global_position(v)
  get_rotation(), set_rotation(rad), get_rotation_degrees(), set_rotation_degrees(d)
  get_scale(), set_scale(v), get_global_rotation(), set_global_rotation(rad)
  get_global_scale(), set_global_scale(v)
  set_visible(v), is_visible()
  look_at(target), distance_to(target), angle_to(target)
  # input
  is_action_pressed(a), is_action_just_pressed(a), is_action_just_released(a)
  is_key_pressed(key), is_mouse_button_pressed(b), is_mouse_button_just_pressed(b)
  get_mouse_position(), get_mouse_world_position(), get_viewport_size()

Actions used with is_action_* are defined in the project's Input Map (menu
Settings -> Project Settings -> Input Map). The built-in actions ui_left /
ui_right / ui_up / ui_down / ui_accept / ui_cancel / ui_jump / ui_run are always
available, and you can add your own (e.g. "fire", "interact") bound to any key.
  # signals / events
  connect(signal, cb), emit(signal, *args)
  # resources / instancing
  preload(path), load_scene(path), instance(path)
  # groups (tag & address nodes collectively)
  add_to_group(name), is_in_group(name), remove_from_group(name)
  get_nodes_in_group(name) -> list, call_group(name, method, *args)
  # scene control
  set_pause(v), is_paused()
  # coordinate conversion (relative to this node)
  local_to_global(local), global_to_local(world)
  # timers / scheduling
  create_timer(interval, cb, oneshot=True), remove_timer(handle)
  # math / utilities
  randf(), randi(), rand_range(a,b), clamp(), lerp(), print(), help()
  is_instance_valid(obj), get_global_mouse_position()
  # motion helpers
  move_toward(current, target, max_delta), angle_difference(a, b)

Properties (read-only, live):
  self.delta        -> seconds since last frame
  self.time         -> engine time object (delta, elapsed, fps, ...)
  self.api          -> this ScriptAPI instance
  self.node         -> the attached node
  self.engine       -> the running Engine

Types (constructors available directly on `self`):
  self.Vector2(x, y), self.Color(r, g, b, a), self.Rect2(x, y, w, h)
"""
