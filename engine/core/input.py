"""Input manager.

Tracks keyboard / mouse state and exposes an API similar to Godot's
``Input`` singleton: ``is_action_pressed("ui_right")``, ``is_action_just_pressed``,
``get_mouse_position()`` and event dispatch.  The editor forwards Qt events
into this manager so that scripts behave identically in-editor and at runtime.
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from engine.core.math2d import Vector2
from engine.core.project_config import DEFAULT_INPUT_MAP


# Default action -> key mapping.  New actions can be registered at runtime
# through :meth:`InputManager.add_action` or loaded from a project's
# ``input_map`` via :meth:`InputManager.apply_input_map`.
DEFAULT_ACTIONS = {name: set(keys) for name, keys in DEFAULT_INPUT_MAP.items()}


class InputManager:
    """Centralised input state."""

    def __init__(self):
        self.actions: Dict[str, Set[str]] = {k: set(v) for k, v in DEFAULT_ACTIONS.items()}
        self._pressed: Set[str] = set()          # keys currently down (Qt key names)
        self._just_pressed: Set[str] = set()      # pressed this frame
        self._just_released: Set[str] = set()     # released this frame
        self._mouse_pos: Vector2 = Vector2(0, 0)
        self._mouse_buttons: Set[int] = set()
        self._mouse_just_pressed: Set[int] = set()
        self._mouse_just_released: Set[int] = set()
        # queued high-level events delivered to nodes via _input / _unhandled_input
        self._event_queue: List[dict] = []

    # ----- configuration -----
    def add_action(self, name: str, keys: List[str]) -> None:
        self.actions[name] = set(keys)

    def apply_input_map(self, mapping: Dict[str, List[str]],
                        merge: bool = True) -> None:
        """Load a project ``input_map`` (``{action: [key, ...]}``).

        With ``merge=True`` (default) the mapping is layered on top of the
        built-in defaults, so existing ``ui_*`` actions keep working while
        project-defined actions are added and any overridden actions take the
        new keys.  With ``merge=False`` only the supplied actions exist.
        """
        new_actions: Dict[str, Set[str]] = {}
        if merge:
            for name, keys in DEFAULT_ACTIONS.items():
                new_actions[name] = set(keys)
        if isinstance(mapping, dict):
            for name, keys in mapping.items():
                if not isinstance(name, str) or not name:
                    continue
                if isinstance(keys, str):
                    keys = [keys]
                if isinstance(keys, (list, tuple)):
                    clean = {k for k in keys if isinstance(k, str) and k}
                    if clean:
                        new_actions[name] = clean
        self.actions = new_actions

    def get_actions(self) -> Dict[str, Set[str]]:
        """Return a copy of the current action -> keys mapping (for the UI)."""
        return {name: set(keys) for name, keys in self.actions.items()}

    # ----- state feeding (called by the host, e.g. the editor) -----
    def on_key_down(self, qt_key_name: str) -> None:
        if qt_key_name not in self._pressed:
            self._pressed.add(qt_key_name)
            self._just_pressed.add(qt_key_name)
        self._event_queue.append({"type": "key", "name": qt_key_name, "pressed": True})

    def on_key_up(self, qt_key_name: str) -> None:
        self._pressed.discard(qt_key_name)
        self._just_released.add(qt_key_name)
        self._event_queue.append({"type": "key", "name": qt_key_name, "pressed": False})

    def on_mouse_move(self, x: float, y: float) -> None:
        self._mouse_pos = Vector2(x, y)

    def on_mouse_down(self, button: int, x: float, y: float) -> None:
        self._mouse_buttons.add(button)
        self._mouse_just_pressed.add(button)
        self._mouse_pos = Vector2(x, y)
        self._event_queue.append({"type": "mouse", "button": button,
                                  "pressed": True, "pos": Vector2(x, y)})

    def on_mouse_up(self, button: int, x: float, y: float) -> None:
        self._mouse_buttons.discard(button)
        self._mouse_just_released.add(button)
        self._mouse_pos = Vector2(x, y)
        self._event_queue.append({"type": "mouse", "button": button,
                                  "pressed": False, "pos": Vector2(x, y)})

    # ----- frame lifecycle -----
    def begin_frame(self) -> None:
        """Clear per-frame edge state. Call once at the start of each frame."""
        self._just_pressed.clear()
        self._just_released.clear()
        self._mouse_just_pressed.clear()
        self._mouse_just_released.clear()

    def end_frame(self) -> None:
        """Discard queued events after they have been delivered."""
        self._event_queue.clear()

    def drain_events(self) -> List[dict]:
        events = self._event_queue
        self._event_queue = []
        return events

    # ----- queries -----
    def is_key_pressed(self, qt_key_name: str) -> bool:
        return qt_key_name in self._pressed

    def is_key_just_pressed(self, qt_key_name: str) -> bool:
        return qt_key_name in self._just_pressed

    def is_key_just_released(self, qt_key_name: str) -> bool:
        return qt_key_name in self._just_released

    def is_action_pressed(self, action: str) -> bool:
        keys = self.actions.get(action, set())
        return any(k in self._pressed for k in keys)

    def is_action_just_pressed(self, action: str) -> bool:
        keys = self.actions.get(action, set())
        return any(k in self._just_pressed for k in keys)

    def is_action_just_released(self, action: str) -> bool:
        keys = self.actions.get(action, set())
        return any(k in self._just_released for k in keys)

    def get_mouse_position(self) -> Vector2:
        return self._mouse_pos

    def is_mouse_button_pressed(self, button: int) -> bool:
        return button in self._mouse_buttons

    def is_mouse_button_just_pressed(self, button: int) -> bool:
        return button in self._mouse_just_pressed
