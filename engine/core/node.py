"""The :class:`Node` base class and the property/serialization system.

Every object that lives in a scene is a ``Node``.  Nodes form a tree
(parent/child) and receive lifecycle callbacks (``_enter_tree``, ``_ready``,
``_exit_tree``) plus per-frame callbacks (``_process``, ``_physics_process``,
``_input``) and a draw hook (``_draw``).

To make the editor's inspector and the scene save/load work generically,
nodes declare *exported properties* through the ``PROPERTIES`` class
attribute.  Each :class:`PropertyDef` describes a field's name, type, default
value and (optional) editor hints; the engine uses this metadata both to
build the inspector widgets and to (de)serialize a scene file.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Type

from engine.core.math2d import Vector2, Color, Rect2
from engine.core.signal import SignalEmitter

_ID_COUNTER = itertools.count(1)

# property value types understood by the engine / editor
PT_FLOAT = "float"
PT_INT = "int"
PT_BOOL = "bool"
PT_STRING = "string"
PT_VECTOR2 = "vector2"
PT_COLOR = "color"
PT_ENUM = "enum"
PT_NODE_PATH = "node_path"
PT_RESOURCE = "resource"
PT_VECTOR2I = "vector2i"


class PropertyDef:
    """Metadata describing an editable property of a node."""

    def __init__(self, name: str, ptype: str, default: Any = None,
                 group: str = "General", hint: str = "",
                 min_value=None, max_value=None, options: List[str] = None,
                 resource_ext: str = ""):
        self.name = name
        self.type = ptype
        self.default = default
        self.group = group
        self.hint = hint
        self.min_value = min_value
        self.max_value = max_value
        self.options = options or []
        self.resource_ext = resource_ext

    def clone_default(self) -> Any:
        return _clone(self.default)


def _clone(v: Any) -> Any:
    if isinstance(v, (Vector2, Color, Rect2)):
        return type(v)(*v.as_tuple()) if isinstance(v, Rect2) else type(v)(*_vec_args(v))
    if isinstance(v, list):
        return [ _clone(x) for x in v ]
    if isinstance(v, dict):
        return { k: _clone(x) for k, x in v.items() }
    return v


def _vec_args(v):
    if isinstance(v, Vector2):
        return (v.x, v.y)
    if isinstance(v, Color):
        return (v.r, v.g, v.b, v.a)
    return ()


class Node(SignalEmitter):
    """Base class for everything in the scene tree."""

    #: class-level registry of exported properties (see PropertyDef)
    PROPERTIES: List[PropertyDef] = [
        PropertyDef("name", PT_STRING, "", group="Node"),
        PropertyDef("visible", PT_BOOL, True, group="Node"),
    ]

    #: human readable category shown in the "Create Node" dialog
    CATEGORY = "Node"

    def __init__(self, name: str = ""):
        super().__init__()
        self.id = next(_ID_COUNTER)
        self.name = name or type(self).__name__
        self.parent: Optional["Node"] = None
        self.children: List["Node"] = []
        self.tree = None               # set when added to a SceneTree
        self.owner_scene = None        # scene instance this node belongs to
        self._script_instances: List[Any] = []
        self._ready_called = False
        self._in_tree = False
        # path to an attached script (resolved at scene load / editor time).
        # Declared on every node (including ones created fresh in the editor) so
        # the inspector never hits AttributeError when reading script_path.
        self.script_path: str = ""
        # properties found in a scene file but unknown to this node type
        # (e.g. authored by a newer engine) are kept here so they survive a
        # save/load round-trip instead of being silently discarded.
        self._extra_props: Dict[str, Any] = {}

        # initialise exported properties from their defaults
        self._prop_defs: Dict[str, PropertyDef] = {p.name: p for p in self.PROPERTIES}
        for p in self.PROPERTIES:
            if p.name == "name":
                # `name` is managed by the constructor, not the default
                continue
            setattr(self, p.name, p.clone_default())

        # default signals every node has
        self.add_signal("tree_entered")
        self.add_signal("tree_exiting")
        self.add_signal("ready")

    # ------------------------------------------------------------------
    # property helpers
    # ------------------------------------------------------------------
    def get_property(self, name: str) -> Any:
        return getattr(self, name, None)

    def set_property(self, name: str, value: Any) -> None:
        old = getattr(self, name, None)
        setattr(self, name, value)
        if self._in_tree:
            self.on_property_changed(name, old, value)

    def on_property_changed(self, name: str, old, new) -> None:
        """Hook for subclasses to react to inspector / script changes."""

    def get_property_list(self) -> List[PropertyDef]:
        return list(self.PROPERTIES)

    def get_property_def(self, name: str) -> Optional[PropertyDef]:
        return self._prop_defs.get(name)

    def get_groups(self) -> List[str]:
        return sorted({p.group for p in self.PROPERTIES})

    # ------------------------------------------------------------------
    # tree manipulation
    # ------------------------------------------------------------------
    def add_child(self, node: "Node") -> None:
        if node is self:
            raise ValueError("cannot add a node as its own child")
        if node.parent is not None:
            node.parent.remove_child(node)
        node.parent = self
        self.children.append(node)
        if self._in_tree:
            self.tree._register(node)
            # single post-order ready pass for the newly added subtree
            self.tree._call_ready(node)

    def remove_child(self, node: "Node") -> None:
        if node in self.children:
            self.children.remove(node)
            node.parent = None
            if self._in_tree and self.tree is not None:
                self.tree._unregister(node)

    def get_child(self, index: int) -> "Node":
        return self.children[index]

    def get_child_count(self) -> int:
        return len(self.children)

    def get_children(self) -> List["Node"]:
        return list(self.children)

    def get_parent(self) -> Optional["Node"]:
        return self.parent

    def get_index(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.children.index(self)

    def has_node(self, path: str) -> bool:
        try:
            return self.get_node(path) is not None
        except Exception:
            return False

    def get_node(self, path: str) -> Optional["Node"]:
        """Resolve a node by path (absolute starting with '/', or relative)."""
        if path.startswith("/"):
            root = self.tree.root if self.tree else self._find_root()
            node = root
            parts = [p for p in path.split("/") if p]
            # the scene root node is itself the tree root; skip a leading
            # segment that names it (Godot-style absolute paths)
            if parts and parts[0] == root.name:
                parts = parts[1:]
        else:
            node = self
            parts = path.split("/")

        for part in parts:
            if part == ".":
                continue
            if part == "..":
                node = node.parent if node.parent else node
                continue
            if node is None:
                return None
            nxt = None
            for c in node.children:
                if c.name == part:
                    nxt = c
                    break
            node = nxt
        return node

    def _find_root(self) -> "Node":
        n = self
        while n.parent is not None:
            n = n.parent
        return n

    def find_node(self, name: str, recursive: bool = True) -> Optional["Node"]:
        for c in self.children:
            if c.name == name:
                return c
            if recursive:
                r = c.find_node(name, True)
                if r is not None:
                    return r
        return None

    def get_path(self) -> str:
        parts = []
        n: Optional[Node] = self
        while n is not None:
            parts.append(n.name)
            n = n.parent
        parts.reverse()
        return "/" + "/".join(parts)

    # ------------------------------------------------------------------
    # convenience helpers (mirror the scripting API for editor/HUD code)
    # ------------------------------------------------------------------
    def get_tree(self):
        """Return the :class:`SceneTree` this node belongs to (or None)."""
        return self.tree

    def get_node_or_null(self, path: str):
        """Like :meth:`get_node` but returns None instead of raising."""
        try:
            return self.get_node(path)
        except Exception:
            return None

    def free(self) -> None:
        """Immediately remove this node from its parent (and from the tree)."""
        if self.parent is not None:
            self.parent.remove_child(self)

    def queue_free(self) -> None:
        """Remove this node (alias of :meth:`free` in this engine)."""
        self.free()

    # ------------------------------------------------------------------
    # script attachment (delegated to the scripting system)
    # ------------------------------------------------------------------
    def set_script_instance(self, instance: Any) -> None:
        self._script_instances.append(instance)

    def get_script_instances(self) -> List[Any]:
        return self._script_instances

    def has_script(self) -> bool:
        return len(self._script_instances) > 0

    # ------------------------------------------------------------------
    # lifecycle / frame callbacks (forwarded to scripts)
    # ------------------------------------------------------------------
    def _enter_tree(self) -> None:
        self._in_tree = True
        self.emit("tree_entered")
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_enter_tree", None))

    def _ready(self) -> None:
        if self._ready_called:
            return
        self._ready_called = True
        self.emit("ready")
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_ready", None))

    def _exit_tree(self) -> None:
        self.emit("tree_exiting")
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_exit_tree", None))
        self._in_tree = False
        # allow a node that is removed and later re-added to fire _ready again
        self._ready_called = False

    def _process(self, delta: float) -> None:
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_process", None), delta)

    def _physics_process(self, delta: float) -> None:
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_physics_process", None), delta)

    def _input(self, event: dict) -> None:
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_input", None), event)

    def _draw(self, renderer, camera) -> None:
        for inst in self._script_instances:
            _safe_call(getattr(inst, "_draw", None), renderer, camera)

    # subclass hooks (documented for extension)
    def _notification(self, what: str) -> None:
        """Receive engine notifications (e.g. 'ready', 'exit_tree')."""

    # ------------------------------------------------------------------
    # serialization
    # ------------------------------------------------------------------
    def serialize(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "type": type(self).__name__,
            "name": self.name,
            "props": {},
        }
        for p in self.PROPERTIES:
            data["props"][p.name] = _serialize_value(getattr(self, p.name, None))
        self._serialize_extra(data)
        data["children"] = [c.serialize() for c in self.children]
        return data

    def deserialize(self, data: Dict[str, Any]) -> None:
        self.name = data.get("name", self.name)
        props = data.get("props", {})
        for key, val in props.items():
            if key in self._prop_defs:
                setattr(self, key, _deserialize_value(self._prop_defs[key].type, val))
            else:
                # unknown property: preserve it (best-effort type restore) so it
                # is not lost when the scene is saved again.
                self._extra_props[key] = _deserialize_value_heuristic(val)
        # children are rebuilt by the scene loader so we ignore them here

    def _serialize_extra(self, data: Dict[str, Any]) -> None:
        for key, val in self._extra_props.items():
            if key in data.get("props", {}):
                continue
            data["props"][key] = _serialize_value(val)

    def __repr__(self):
        return f"<{type(self).__name__} '{self.name}' id={self.id}>"


def _safe_call(fn, *args):
    if fn is None:
        return
    try:
        fn(*args)
    except Exception:
        import traceback
        traceback.print_exc()


# ----------------------------------------------------------------------
# value (de)serialization helpers
# ----------------------------------------------------------------------
def _serialize_value(v: Any) -> Any:
    if isinstance(v, Vector2):
        return {"__type__": "Vector2", "x": v.x, "y": v.y}
    if isinstance(v, Color):
        return {"__type__": "Color", "r": v.r, "g": v.g, "b": v.b, "a": v.a}
    if isinstance(v, Rect2):
        return {"__type__": "Rect2", "x": v.x, "y": v.y, "w": v.w, "h": v.h}
    if isinstance(v, Node):
        return {"__type__": "NodePath", "path": v.get_path()}
    return v


def _deserialize_value(ptype: str, v: Any) -> Any:
    if isinstance(v, dict) and "__type__" in v:
        t = v["__type__"]
        if t == "Vector2":
            return Vector2(v["x"], v["y"])
        if t == "Color":
            return Color(v["r"], v["g"], v["b"], v["a"])
        if t == "Rect2":
            return Rect2(v["x"], v["y"], v["w"], v["h"])
        if t == "NodePath":
            return v["path"]
    return v


def _deserialize_value_heuristic(v: Any) -> Any:
    """Restore a value whose type is not declared in any PropertyDef.  Uses the
    ``__type__`` marker when present, otherwise returns the raw value."""
    if isinstance(v, dict) and "__type__" in v:
        return _deserialize_value(v["__type__"], v)
    return v
