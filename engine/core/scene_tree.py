"""Scene tree.

The :class:`SceneTree` owns the live node hierarchy, drives the per-frame
callbacks (``_process`` / ``_physics_process``), dispatches input events and
manages lifecycle ordering.  It is the single object that the rest of the
engine (physics world, scripts, renderer) talks to when they need to reach
"the world".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.core.node import Node


class SceneTree:
    """Owns the active node hierarchy and runs the frame loop."""

    def __init__(self, engine: Any = None):
        self.engine = engine
        self.root: Optional[Node] = None
        self.physics = None          # set by the engine (PhysicsWorld)
        self.resources = None        # ResourceManager, set by engine
        self.paused = False
        self._groups: Dict[str, List[Node]] = {}   # name -> [nodes]

    # ------------------------------------------------------------------
    # scene management
    # ------------------------------------------------------------------
    def set_root(self, node: Node) -> None:
        if self.root is not None:
            self._unregister(self.root)
        self.root = node
        node.tree = self
        node.owner_scene = node
        if node.parent is None:
            self._register(node)
            # single post-order ready pass: children become ready before parents
            self._call_ready(node)

    def change_scene(self, scene: Node) -> None:
        """Replace the current root scene with ``scene``."""
        self.set_root(scene)

    # ------------------------------------------------------------------
    # registration / lifecycle
    # ------------------------------------------------------------------
    def _register(self, node: Node) -> None:
        """Top-down enter-tree pass for *node* and its descendants."""
        node.tree = self
        node._enter_tree()
        for c in node.children:
            self._register(c)

    def _call_ready(self, node: Node) -> None:
        for c in node.children:
            self._call_ready(c)
        node._ready()

    def _unregister(self, node: Node) -> None:
        for c in list(node.children):
            self._unregister(c)
        # drop the node from every group it belonged to
        for g in list(getattr(node, "_groups", set())):
            self.remove_from_group(node, g)
        node._exit_tree()
        node.tree = None

    # ------------------------------------------------------------------
    # groups (tag nodes so scripts can address them collectively)
    # ------------------------------------------------------------------
    def add_to_group(self, node: Node, name: str) -> None:
        self._groups.setdefault(name, [])
        if node not in self._groups[name]:
            self._groups[name].append(node)
        if not hasattr(node, "_groups"):
            node._groups = set()
        node._groups.add(name)

    def remove_from_group(self, node: Node, name: str) -> None:
        lst = self._groups.get(name)
        if lst and node in lst:
            lst.remove(node)
            if not lst:
                self._groups.pop(name, None)
        if getattr(node, "_groups", None):
            node._groups.discard(name)

    def is_in_group(self, node: Node, name: str) -> bool:
        return name in getattr(node, "_groups", set())

    def get_nodes_in_group(self, name: str) -> List[Node]:
        return list(self._groups.get(name, []))

    def call_group(self, name: str, method: str, *args) -> None:
        """Call ``method(*args)`` on every node in ``name``."""
        for n in self.get_nodes_in_group(name):
            fn = getattr(n, method, None)
            if fn is not None:
                try:
                    fn(*args)
                except Exception:
                    import traceback
                    traceback.print_exc()

    # ------------------------------------------------------------------
    # frame loop
    # ------------------------------------------------------------------
    def process(self, delta: float) -> None:
        """Visual frame update (calls ``_process`` on every node)."""
        if self.root is None or self.paused:
            return
        self._traverse(self.root, "_process", delta)

    def physics_process(self, delta: float) -> None:
        """Fixed-step physics update (calls ``_physics_process``)."""
        if self.root is None or self.paused:
            return
        # step the physics world first, then notify nodes
        if self.physics is not None:
            self.physics.step(delta)
        self._traverse(self.root, "_physics_process", delta)

    def dispatch_input(self, events: List[dict]) -> None:
        if self.root is None:
            return
        for ev in events:
            self._traverse(self.root, "_input", ev)

    def _traverse(self, node: Node, method: str, *args) -> None:
        fn = getattr(node, method, None)
        if fn is not None:
            try:
                fn(*args)
            except Exception:
                import traceback
                traceback.print_exc()
        for c in node.children:
            self._traverse(c, method, *args)

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def get_nodes_by_type(self, cls: type) -> List[Node]:
        out: List[Node] = []
        if self.root is not None:
            self._collect(self.root, cls, out)
        return out

    def _collect(self, node: Node, cls: type, out: List[Node]) -> None:
        if isinstance(node, cls):
            out.append(node)
        for c in node.children:
            self._collect(c, cls, out)

    def get_first_node_of_type(self, cls: type) -> Optional[Node]:
        nodes = self.get_nodes_by_type(cls)
        return nodes[0] if nodes else None

    def find_camera(self):
        """Return the active :class:`Camera2D` if any."""
        _resolve_camera_type()
        cams = self.get_nodes_by_type(_CAMERA_TYPE)
        if not cams:
            return None
        # last enabled camera wins (Godot-like)
        for c in reversed(cams):
            if getattr(c, "current", False):
                return c
        return cams[-1]

    def get_node_count(self) -> int:
        if self.root is None:
            return 0
        count = 0

        def walk(n: Node):
            nonlocal count
            count += 1
            for c in n.children:
                walk(c)
        walk(self.root)
        return count


# The camera type is imported lazily to avoid a circular import with nodes.
_CAMERA_TYPE = None


def _resolve_camera_type():
    global _CAMERA_TYPE
    if _CAMERA_TYPE is None:
        from engine.nodes.camera2d import Camera2D
        _CAMERA_TYPE = Camera2D
