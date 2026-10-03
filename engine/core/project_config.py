"""Project configuration: schema, safe loading and auto-repair.

The on-disk format is ``project.reindeer`` (a JSON document).  Because users may
hand-edit it or open projects created by older releases, *every* field is
normalised and malformed values are repaired to safe defaults instead of
crashing the editor or runtime.  The repaired document can optionally be written
back to disk so a project's settings are self-healing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

CONFIG_FILE = "project.reindeer"

# Built-in input actions that ship with every project.  A project may override
# any of these (by giving the same action name a different key list) or add new
# actions through its ``input_map``.  These names mirror Godot's convention.
DEFAULT_INPUT_MAP: Dict[str, List[str]] = {
    "ui_accept": ["Key_Enter", "Key_Return", "Key_Space"],
    "ui_cancel": ["Key_Escape"],
    "ui_left":   ["Key_Left", "Key_A"],
    "ui_right":  ["Key_Right", "Key_D"],
    "ui_up":     ["Key_Up", "Key_W"],
    "ui_down":   ["Key_Down", "Key_S"],
    "ui_jump":   ["Key_Space"],
    "ui_run":    ["Key_Shift"],
}

DEFAULT_WINDOW_SIZE: List[int] = [960, 540]
DEFAULT_RUN_BACKEND = "pyside6"
DEFAULT_PHYSICS_BACKEND = "builtin"


def _as_str(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _as_int_pair(value: Any, default: List[int]) -> List[int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return [int(value[0]), int(value[1])]
        except Exception:
            return list(default)
    return list(default)


def _normalize_input_map(raw: Any) -> Dict[str, List[str]]:
    """Repair an input map into ``{action: [key, ...]}``.

    Unknown / malformed entries are dropped rather than raising, and the
    built-in actions are always present (so scripts relying on ``ui_*`` keep
    working even in an old or hand-edited project).
    """
    out: Dict[str, List[str]] = {}
    if isinstance(raw, dict):
        for action, keys in raw.items():
            if not isinstance(action, str) or not action:
                continue
            if isinstance(keys, str):
                keys = [keys]
            if not isinstance(keys, (list, tuple)):
                continue
            clean = [k for k in keys if isinstance(k, str) and k]
            if clean:
                out[action] = clean
    # built-in actions are always available as a safe fallback
    for action, keys in DEFAULT_INPUT_MAP.items():
        out.setdefault(action, list(keys))
    return out


def normalize_project_config(raw: Any) -> Dict[str, Any]:
    """Return a fully repaired config derived from *raw* (which may be garbage)."""
    if not isinstance(raw, dict):
        raw = {}
    cfg: Dict[str, Any] = {
        "name": _as_str(raw.get("name"), ""),
        "main_scene": _as_str(raw.get("main_scene"), ""),
        "window_size": _as_int_pair(raw.get("window_size"), DEFAULT_WINDOW_SIZE),
        "run_backend": _as_str(raw.get("run_backend"), DEFAULT_RUN_BACKEND),
        "physics_backend": _as_str(raw.get("physics_backend"),
                                   DEFAULT_PHYSICS_BACKEND),
        "input_map": _normalize_input_map(raw.get("input_map")),
    }
    # preserve any extra (unknown) keys so we never clobber user data
    for key, value in raw.items():
        if key not in cfg:
            cfg[key] = value
    return cfg


def load_project_config(project_dir: str, repair_on_disk: bool = True) -> Dict[str, Any]:
    """Load and normalise ``project.reindeer`` for *project_dir*.

    Returns a safe, fully-repaired config.  A missing or unreadable file yields
    the default config.  When ``repair_on_disk`` is True and the on-disk document
    differs from the normalised version (e.g. an old schema without
    ``input_map``), the repaired copy is written back so the project heals
    itself on next open.
    """
    cfg_path = os.path.join(project_dir, CONFIG_FILE)
    raw: Any = {}
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            raw = {}
    cfg = normalize_project_config(raw)
    if repair_on_disk and os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except Exception:
            existing = None
        # dict comparison is order-independent; only rewrite on a real change
        if existing != cfg:
            try:
                save_project_config(cfg, project_dir)
            except Exception:
                # read-only media (e.g. a packaged game) -> skip, never crash
                pass
    return cfg


def save_project_config(cfg: Dict[str, Any], project_dir: str) -> None:
    """Persist *cfg* to ``project.reindeer`` (creating it if necessary)."""
    cfg_path = os.path.join(project_dir, CONFIG_FILE)
    os.makedirs(project_dir, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as handle:
        json.dump(cfg, handle, indent=2, ensure_ascii=False)
