"""Project management for the editor.

A Reindeer project is a directory containing a ``project.reindeer`` config
file, scene files (``*.reindeer.tscn``) and resources (images, scripts, ...).
The :class:`Project` class discovers these and persists project settings.
"""
from __future__ import annotations

import json
import os
import zipfile
from typing import List

from engine.core.project_config import load_project_config, save_project_config


class Project:
    CONFIG_FILE = "project.reindeer"

    # directories that should never appear in the editor's project browser or
    # scene/resource pickers (build artifacts, hidden, caches, engine internals)
    IGNORED_DIRS = {"addons", "dist", "build", "__pycache__"}

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.name = os.path.basename(self.path)
        self.main_scene = ""
        self.config = {}
        self.load_config()

    # ------------------------------------------------------------------
    def load_config(self) -> None:
        # load_project_config normalises the schema and auto-repairs old / broken
        # projects (e.g. missing ``input_map``) so the editor never crashes.
        self.config = load_project_config(self.path, repair_on_disk=True)
        self.name = self.config.get("name") or self.name
        self.main_scene = self.config.get("main_scene", "")

    def save_config(self) -> None:
        self.config["name"] = self.name
        self.config["main_scene"] = self.main_scene
        save_project_config(self.config, self.path)

    # ------------------------------------------------------------------
    def abs_path(self, rel: str) -> str:
        return os.path.join(self.path, rel) if rel else ""

    def rel_path(self, abs_path: str) -> str:
        return os.path.relpath(abs_path, self.path)

    # ------------------------------------------------------------------
    def scan_scenes(self) -> List[str]:
        out = []
        for root, dirs, files in os.walk(self.path):
            # prune ignored directories so build artifacts / caches never show up
            dirs[:] = [d for d in dirs
                       if d not in self.IGNORED_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(".reindeer.tscn"):
                    out.append(os.path.relpath(os.path.join(root, f), self.path))
        return sorted(out)

    def scan_resources(self) -> List[str]:
        out = []
        for root, dirs, files in os.walk(self.path):
            dirs[:] = [d for d in dirs
                       if d not in self.IGNORED_DIRS and not d.startswith(".")]
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".py", ".wav")):
                    out.append(os.path.relpath(os.path.join(root, f), self.path))
        return sorted(out)

    def ensure_dirs(self) -> None:
        os.makedirs(os.path.join(self.path, "scenes"), exist_ok=True)
        os.makedirs(os.path.join(self.path, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(self.path, "sprites"), exist_ok=True)


# ----------------------------------------------------------------------
# shareable project packages (.zip) — for 二创 / modding and backup
# ----------------------------------------------------------------------
#: directories excluded when packaging a project into a shareable .zip
PACKAGE_EXCLUDE_DIRS = {"__pycache__", ".git", "dist", "build", "addons"}
#: file extensions excluded when packaging
PACKAGE_EXCLUDE_EXT = {".pyc"}


def _is_package_excluded(rel_path: str) -> bool:
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    if any(p in PACKAGE_EXCLUDE_DIRS for p in parts):
        return True
    if os.path.splitext(rel_path)[1].lower() in PACKAGE_EXCLUDE_EXT:
        return True
    if rel_path.endswith(".bak") or rel_path.endswith("~"):
        return True
    return False


def package_project(project_dir: str, zip_path: str) -> int:
    """Zip *project_dir* into *zip_path*, skipping build artifacts / caches.

    Returns the number of files archived.  This is the "export as package"
    operation used by the project manager for 二创 / backup sharing.
    """
    project_dir = os.path.abspath(project_dir)
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            # prune ignored directories in-place so os.walk skips them
            dirs[:] = [d for d in dirs if d not in PACKAGE_EXCLUDE_DIRS]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, project_dir)
                if _is_package_excluded(rel):
                    continue
                zf.write(full, rel)
                count += 1
    return count


def _common_top_dir(names) -> "str | None":
    """If every entry in *names* (zip member paths) shares exactly one leading
    directory, return that directory with a trailing slash; else ``None``.

    This lets packages created from a folder (``my_game/...``) extract cleanly
    into the chosen destination instead of nesting an extra folder.
    """
    tops = set()
    for n in names:
        n = n.replace("\\", "/")
        if n.endswith("/"):
            continue
        parts = n.split("/")
        if len(parts) >= 2 and parts[0]:
            tops.add(parts[0])
        else:
            return None
    if len(tops) == 1:
        return next(iter(tops)) + "/"
    return None


def extract_package(zip_path: str, dest_dir: str) -> int:
    """Extract a .zip package into *dest_dir*.

    Strips a single common top-level directory (if the archive was created from a
    folder) and guards against zip-slip path traversal.  Returns the number of
    files extracted.  Callers should validate the result (e.g. a ``project.reindeer``
    exists) if they require a specific layout.
    """
    dest_dir = os.path.abspath(dest_dir)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        top = _common_top_dir(names)
        for member in names:
            rel = member.replace("\\", "/")
            if top and rel.startswith(top):
                rel = rel[len(top):]
            rel = rel.lstrip("/")
            if not rel or rel.endswith("/"):
                continue
            target = os.path.normpath(os.path.join(dest_dir, rel))
            # protect against zip-slip (member escapes dest_dir)
            if not (target == dest_dir or target.startswith(dest_dir + os.sep)):
                continue
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
            count += 1
    return count
