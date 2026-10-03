"""Scene serialization.

Scenes are stored as human-readable JSON files (``.reindeer.tscn``).  The
format mirrors Godot's tscn philosophy: each node records its *type*, its
*exported properties* and its *children*; the loader reconstructs the exact
tree using the node :class:`~engine.core.registry.NodeRegistry`.  Script
attachments are stored as a ``script`` path and resolved at load time by the
scripting system.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from engine.core.node import Node
from engine.core.registry import get_registry


class SceneLoader:
    EXTENSION = ".reindeer.tscn"

    def __init__(self, engine=None):
        self.engine = engine

    # ------------------------------------------------------------------
    def save(self, root: Node, path: str) -> None:
        # Guard against persisting a broken in-memory tree: every child must
        # report this node as its parent.  A mismatch means the node hierarchy
        # is corrupt and would otherwise be silently written and lost on reload.
        self._assert_consistent(root)
        data = {
            "reindeer_scene": 1,
            "root": self._serialize_node(root),
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _serialize_node(self, node: Node) -> Dict[str, Any]:
        d = node.serialize()
        # ``node.serialize()`` also emits a ``children`` list (in *node* format),
        # but the authoritative child serialisation is performed here from the
        # live node tree so a single code path owns every parent/child link.
        d.pop("children", None)
        # store attached script path (if any)
        d["script"] = getattr(node, "script_path", "") or ""
        # serialise children recursively (preserving their script paths)
        d["children"] = [self._serialize_node(c) for c in node.children]
        return d

    @staticmethod
    def _assert_consistent(node: Node) -> None:
        """Recursively verify that the parent/child relationship is fully
        bidirectional on the live tree:

        * every entry in ``node.children`` must name ``node`` as its parent, and
        * every node with a parent must actually be listed in that parent's
          ``children``.

        The second check matters because a node that points at a parent but is
        missing from its ``children`` list would be silently dropped on save
        (the serialiser only walks ``children``).  Raised ``RuntimeError`` aborts
        the save instead of writing a lossy file."""
        for child in node.children:
            if child.parent is not node:
                raise RuntimeError(
                    "scene save aborted: child %r lists parent %r but is held by "
                    "%r" % (child, child.parent, node))
            SceneLoader._assert_consistent(child)
        if node.parent is not None and node not in node.parent.children:
            raise RuntimeError(
                "scene save aborted: %r points at parent %r but is not in that "
                "parent's children (it would be lost on save)" % (node, node.parent))

    @classmethod
    def verify_file(cls, path: str, engine=None) -> bool:
        """Reload a scene file and confirm every parent/child relationship is
        internally consistent.  Returns ``True`` when the file round-trips
        cleanly, ``False`` (after printing the error) otherwise."""
        try:
            loader = cls(engine)
            root = loader.load(path)
            cls._assert_consistent(root)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[scene] verification failed for {path}: {exc}")
            return False

    # ------------------------------------------------------------------
    def load(self, path: str) -> Node:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        root = self._build(data["root"])
        # resolve script attachments
        if self.engine is not None:
            self._attach_scripts(root)
        return root

    def _build(self, node_data: Dict[str, Any]) -> Node:
        reg = get_registry()
        cls_name = node_data.get("type", "Node")
        cls = reg.get(cls_name)
        if cls is None:
            # unknown node type -> fall back to a generic Node so the scene
            # still loads; the editor will warn the user.
            print(f"[scene] unknown node type '{cls_name}', using Node")
            cls = Node
        node = cls(node_data.get("name", cls_name))
        node.deserialize(node_data)
        node.script_path = node_data.get("script", "") or ""
        for child_data in node_data.get("children", []):
            child = self._build(child_data)
            node.add_child(child)
        return node

    def _attach_scripts(self, root: Node) -> None:
        try:
            from engine.scripting.script import attach_scripts_in_tree
            attach_scripts_in_tree(root, self.engine)
        except Exception as exc:
            print(f"[scene] failed to attach scripts: {exc}")
