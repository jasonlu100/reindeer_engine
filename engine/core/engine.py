"""The engine runtime.

:class:`Engine` wires together the core subsystems (time, input, resources,
scene tree and physics world) and exposes a single
``step`` method that advances the whole simulation by one frame.  The editor
drives ``step`` from a timer to provide live preview; a standalone game would
call it from its own main loop.
"""
from __future__ import annotations

from typing import Any, Optional

from engine.core.time import Time
from engine.core.input import InputManager
from engine.core.resource import ResourceManager
from engine.core.scene_tree import SceneTree
from engine.core.scene_format import SceneLoader
from engine.physics import create_physics_world
from engine.nodes.camera2d import Camera2D
from engine.nodes.node2d import Node2D
from engine.core.math2d import Vector2
from engine.core.project_config import load_project_config


class Engine:
    """Top level runtime object."""

    def __init__(self, headless: bool = False, project_dir: str = None,
                 physics_backend: str = None):
        # importing this package registers all built-in node types
        import engine.nodes          # noqa: F401  (registers nodes)

        self.project_dir = project_dir
        # load the (auto-repaired) project config once; reused for physics + input
        cfg = (load_project_config(project_dir, repair_on_disk=False)
               if project_dir else {})
        self.time = Time()
        self.input = InputManager()
        # apply the project's custom input map (falls back to built-in actions)
        self.input.apply_input_map(cfg.get("input_map", {}), merge=True)
        self.resources = ResourceManager()
        self.tree = SceneTree(self)

        # select the physics backend (explicit arg > project config > builtin)
        backend = physics_backend or cfg.get("physics_backend", "builtin")
        self.physics = create_physics_world(backend)
        self.tree.physics = self.physics
        self.tree.resources = self.resources
        self.headless = headless
        self.current_scene_path: Optional[str] = None
        self._loader = SceneLoader(self)
        self.renderer = None  # set by the host (editor) or a runtime window
        self.timers = []      # lightweight callback timers (see add_timer)

    # ------------------------------------------------------------------
    # scene loading / saving
    # ------------------------------------------------------------------
    def load_scene(self, path: str):
        """Load a scene file and set it as the active root scene."""
        scene = self._loader.load(path)
        self.current_scene_path = path
        self.tree.set_root(scene)
        return scene

    def save_scene(self, node, path: str) -> None:
        self._loader.save(node, path)

    def new_scene(self, root_type: str = "Node2D"):
        from engine.core.registry import get_registry
        root = get_registry().create(root_type, "Main")
        self.tree.set_root(root)
        return root

    # ------------------------------------------------------------------
    # frame stepping
    # ------------------------------------------------------------------
    def step(self) -> float:
        """Advance the simulation by one frame. Returns the delta (seconds)."""
        dt = self.time.tick()
        # deliver queued input events to nodes
        events = self.input.drain_events()
        if events:
            self.tree.dispatch_input(events)
        # fixed-ish physics step then visual update
        self.tree.physics_process(dt)
        self.tree.process(dt)
        # keep cameras inside their configured world bounds (a "specified
        # rectangular region" the view cannot leave)
        self.clamp_cameras()
        # engine-level timers (scripted callbacks, tweens, deferred calls ...)
        self._tick_timers(dt)
        self.input.end_frame()
        return dt

    # ------------------------------------------------------------------
    # camera bounds
    # ------------------------------------------------------------------
    def clamp_cameras(self) -> None:
        """Clamp every :class:`Camera2D` with finite ``limit_x`` / ``limit_y`` so
        its centre cannot leave the rectangular world bounds (expressed in *world*
        space).  The clamp is applied to the camera's global position and then
        converted back into its local position so it stays correct even when the
        camera is nested under a transformed parent.  Cameras without limits (the
        default, 1e9) are left untouched.

        Cameras with ``smoothing`` enabled are skipped here: their rendered
        centre is already clamped inside :meth:`Camera2D._render_center`, and
        mutating ``cam.position`` on a smoothed (often parented) camera would
        fight the smoothing and shift it relative to its parent."""
        for cam in self.tree.get_nodes_by_type(Camera2D):
            if getattr(cam, "smoothing", False):
                continue
            lx = getattr(cam, "limit_x", 1e9)
            ly = getattr(cam, "limit_y", 1e9)
            if lx >= 1e8 and ly >= 1e8:
                continue
            gp = cam.get_global_position()
            nx = max(-lx, min(lx, gp.x)) if lx < 1e8 else gp.x
            ny = max(-ly, min(ly, gp.y)) if ly < 1e8 else gp.y
            clamped = Vector2(nx, ny)
            # convert the clamped world position back into the camera's local
            # space (inverse of the parent's global transform)
            parent = cam.parent
            if parent is None or not isinstance(parent, Node2D):
                cam.position = clamped
            else:
                ppos, prot, pscale = parent._global_xform()
                d = clamped - ppos
                d = d.rotated(-prot)
                lx2 = d.x / pscale.x if pscale.x else d.x
                ly2 = d.y / pscale.y if pscale.y else d.y
                cam.position = Vector2(lx2, ly2)

    # ------------------------------------------------------------------
    # timers / deferred callbacks
    # ------------------------------------------------------------------
    def add_timer(self, interval: float, callback, oneshot: bool = True):
        """Register ``callback`` to fire every ``interval`` seconds.

        With ``oneshot=True`` (default) it fires once; otherwise it repeats.
        Returns a handle usable with :meth:`remove_timer`.
        """
        timer = {"interval": float(interval), "acc": 0.0,
                 "callback": callback, "oneshot": bool(oneshot)}
        self.timers.append(timer)
        return timer

    def remove_timer(self, timer) -> None:
        """Cancel a timer previously returned by :meth:`add_timer`."""
        if timer in self.timers:
            self.timers.remove(timer)

    def _tick_timers(self, dt: float) -> None:
        for timer in list(self.timers):
            timer["acc"] += dt
            if timer["acc"] >= timer["interval"]:
                try:
                    timer["callback"]()
                except Exception:
                    import traceback
                    traceback.print_exc()
                if timer["oneshot"]:
                    self.timers.remove(timer)
                else:
                    timer["acc"] = 0.0

    def run_scene(self, path: str, frames: int = 300, dt: float = 1.0 / 60.0) -> None:
        """Headless run of a scene for ``frames`` ticks (useful for tests)."""
        self.load_scene(path)
        for _ in range(frames):
            self.time.delta = dt
            self.time.elapsed += dt
            self.tree.physics_process(dt)
            self.tree.process(dt)
        print(f"[engine] ran {frames} frames; nodes={self.tree.get_node_count()}")

    def reset(self) -> None:
        """Unload the current scene and clear caches (used by the editor)."""
        if self.tree.root is not None:
            self.tree._unregister(self.tree.root)
            self.tree.root = None
        self.physics.clear()
        self.time = Time()
        self.time.set_physics_delta(60)
