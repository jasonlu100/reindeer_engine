"""Resource management.

A *resource* is anything that can be loaded from disk and shared between
nodes (textures, scripts, scenes, audio, ...).  The :class:`ResourceManager`
caches loaded resources by path and hands out the same instance to every
requester, much like Godot's ``ResourceLoader``.  The engine ships with a
few built-in resource types and new types can be registered via
:func:`ResourceManager.register_type`.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, Type


class Resource:
    """Base class for all loadable resources."""

    #: resource file extension handled by this type (without dot)
    EXTENSION = ""

    def __init__(self, path: str = ""):
        self.path = path
        self._loaded = False

    def load(self, path: str) -> None:
        """Populate the resource from ``path``. Override in subclasses."""
        self.path = path
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def __repr__(self):
        return f"<{type(self).__name__} path={self.path!r}>"


class ResourceManager:
    """Loads, caches and tracks engine resources."""

    def __init__(self):
        self._cache: Dict[str, Resource] = {}
        self._types: Dict[str, Type[Resource]] = {}
        self._loaders: Dict[str, Callable[[str], Resource]] = {}
        self.register_type("reindeer.tscn", "SceneResource", None)

    # ------------------------------------------------------------------
    def register_type(self, extension: str, name: str,
                      loader: Callable[[str], Resource] = None) -> None:
        """Register how to load a given file extension.

        ``loader`` is a callable ``(path) -> Resource`` or ``None`` (the
        resource type itself implements ``load``).
        """
        self._loaders[extension] = loader

    def register_resource_class(self, ext: str, cls: Type[Resource]) -> None:
        self._types[ext] = cls
        self.register_type(ext, cls.__name__)

    def get_loader(self, path: str) -> Callable[[str], Resource]:
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        return self._loaders.get(ext)

    # ------------------------------------------------------------------
    def load(self, path: str) -> Resource:
        """Load (or return a cached) resource for ``path``."""
        path = os.path.normpath(path)
        if path in self._cache:
            return self._cache[path]
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        cls = self._types.get(ext)
        if cls is not None:
            res = cls(path)
            res.load(path)
        else:
            loader = self._loaders.get(ext)
            if loader is not None:
                res = loader(path)
            else:
                # unknown -> treat as a generic text/binary resource
                res = Resource(path)
                res.load(path)
        self._cache[path] = res
        return res

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def preload(self, path: str) -> Resource:
        return self.load(path)

    def release(self, path: str) -> None:
        self._cache.pop(path, None)

    def clear(self) -> None:
        for r in self._cache.values():
            r.unload()
        self._cache.clear()

    def all_resources(self):
        return list(self._cache.values())
