"""Script attachment.

A *script* is a normal Python ``.py`` file.  When a node has a ``script``
property pointing at such a file, the engine loads it, finds the first class
defined in it, instantiates it (with no args) and *injects* the scripting
API onto the instance so user code can call ``self.get_node(...)`` etc.
directly.  The node then forwards its lifecycle / frame callbacks to the
script instance automatically.
"""
from __future__ import annotations

import ast
import os
from typing import Any

from engine.scripting.api import ScriptAPI

# Descriptor that forwards attribute access from a script instance to its
# :class:`ScriptAPI` so that *every* public member of the API -- methods, the
# ``Vector2`` / ``Color`` / ``Rect2`` classes, the ``delta`` / ``time``
# properties, ``help`` ... -- is reachable as a plain ``self.xxx`` from inside a
# user script.  This keeps the exposed surface automatically in sync with
# :class:`ScriptAPI` (no more hand-maintained injection list to fall out of date).
class _ApiForward:
    """Read-only descriptor forwarding a script attribute to the ScriptAPI."""

    def __init__(self, name: str):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance.api, self._name)


def _find_script_class(source: str, namespace: dict):
    """Return the first class defined in the module source."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls = namespace.get(node.name)
            if isinstance(cls, type):
                return cls
    return None


def create_script_instance(node, engine) -> Any:
    """Load the node's script file and build its instance."""
    path = getattr(node, "script_path", "") or ""
    if not path:
        return None
    if not os.path.isabs(path):
        base = getattr(engine, "project_dir", "") or ""
        path = os.path.join(base, path) if base else path
    if not os.path.exists(path):
        print(f"[script] script not found: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    namespace: dict = {}
    try:
        exec(compile(source, path, "exec"), namespace)
    except Exception as exc:
        print(f"[script] failed to compile {path}: {exc}")
        return None

    cls = _find_script_class(source, namespace)
    if cls is None:
        # no class defined: expose module-level callables on a *fresh* instance
        # class (not the global SimpleNamespace, which would otherwise be mutated
        # by the API-forwarding loop below and leak across every script).  The
        # functions are bound to the instance so they behave like methods
        # (``self`` is the instance, giving access to ``self.api`` / ``self.node``
        # / ``self.engine``) - consistent with the class-based path.
        cls = type("ScriptInstance", (object,), {})
        instance = cls()
        for name, val in namespace.items():
            if callable(val) and not name.startswith("__"):
                setattr(instance, name, val.__get__(instance))
    else:
        try:
            instance = cls()
        except Exception as exc:
            print(f"[script] failed to instantiate script class in {path}: {exc}")
            return None

    # inject the API + convenience methods
    api = ScriptAPI(node, engine)
    instance.api = api
    instance.node = node
    instance.engine = engine
    # Expose every public member of the ScriptAPI on the script instance, so
    # user code can call ``self.get_node(...)`` *or* ``self.Vector2(...)`` /
    # ``self.delta`` / ``self.time`` / ``self.help()`` directly.  Private
    # members (lifecycle hooks such as ``_ready``) are skipped on purpose so the
    # script's own definitions win.  ``api`` / ``node`` / ``engine`` are set
    # directly above and excluded here to avoid redundant forwarding.
    cls = instance.__class__
    for name in dir(api):
        if name.startswith("_"):
            continue
        if name in ("api", "node", "engine"):
            continue
        setattr(cls, name, _ApiForward(name))

    # if the script defines an explicit _attach hook, call it
    attach = getattr(instance, "_attach", None)
    if attach is not None:
        try:
            attach()
        except Exception:
            import traceback
            traceback.print_exc()

    return instance


def attach_scripts_in_tree(root, engine) -> None:
    """Walk a scene tree and attach every node's script."""
    def walk(n):
        if getattr(n, "script_path", ""):
            inst = create_script_instance(n, engine)
            if inst is not None:
                n.set_script_instance(inst)
        for c in n.children:
            walk(c)
    walk(root)
