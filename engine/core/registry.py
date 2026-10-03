"""Node class registry.

The registry is the heart of the engine's extensibility: every node *type*
(regardless of whether it ships with the engine, comes from a plugin, or is
user-defined) registers itself here.  The editor, the scene loader and the
scripting API all discover node types exclusively through this registry, so
adding a new node never requires touching existing code.
"""
from __future__ import annotations

import importlib
from typing import Dict, List, Optional, Type


class NodeRegistry:
    def __init__(self):
        self._by_name: Dict[str, Type] = {}
        self._by_category: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    def register(self, cls: Type, category: str = None) -> Type:
        """Register a node class. ``cls.CATEGORY`` may be overridden."""
        name = cls.__name__
        self._by_name[name] = cls
        cat = category or getattr(cls, "CATEGORY", "Node")
        cls.CATEGORY = cat
        self._by_category.setdefault(cat, [])
        if name not in self._by_category[cat]:
            self._by_category[cat].append(name)
        return cls

    def register_class(self, cls: Type) -> Type:
        return self.register(cls)

    def get(self, name: str) -> Optional[Type]:
        return self._by_name.get(name)

    def create(self, name: str, node_name: str = ""):
        cls = self._by_name.get(name)
        if cls is None:
            raise KeyError(f"unknown node type '{name}'")
        return cls(node_name)

    def names(self) -> List[str]:
        return sorted(self._by_name.keys())

    def categories(self) -> Dict[str, List[str]]:
        return {k: sorted(v) for k, v in self._by_category.items()}

    def names_in_category(self, category: str) -> List[str]:
        return sorted(self._by_category.get(category, []))

    def clear(self) -> None:
        self._by_name.clear()
        self._by_category.clear()

    # ------------------------------------------------------------------
    def autodiscover(self, package: str) -> None:
        """Import a package so that its ``@register_node`` decorators run."""
        try:
            importlib.import_module(package)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[registry] failed to autodiscover {package}: {exc}")


# global singleton registry used everywhere in the engine
NodeRegistry_INSTANCE = NodeRegistry()


def get_registry() -> NodeRegistry:
    return NodeRegistry_INSTANCE


def register_node(category: str = "Node"):
    """Class decorator: register a node class with the global registry.

    Example::

        @register_node("Physics")
        class RigidBody2D(Node2D):
            ...
    """
    def deco(cls):
        cls.CATEGORY = category
        NodeRegistry_INSTANCE.register(cls)
        return cls
    return deco
