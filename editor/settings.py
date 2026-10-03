"""Persistent editor-wide settings (language, theme, ...).

Stored as a small JSON file under the user's home directory so the choice
survives across projects.  Falls back to sane defaults when the file is
missing or corrupted.
"""
from __future__ import annotations

import json
import os

SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".reindeer")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "editor_settings.json")

DEFAULTS = {
    "language": "en",
    "theme": "dark",
}


def _load() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULTS)


_cache = None


def _settings() -> dict:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def get_setting(key: str, default=None):
    return _settings().get(key, default)


def set_setting(key: str, value) -> None:
    data = _settings()
    data[key] = value
    global _cache
    _cache = data
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        # settings are best-effort; never break the editor over a write error
        pass
