"""Editor widget for editing a project's custom input map.

A :class:`InputMapEditor` presents the ``input_map`` (``{action: [key, ...]}``)
as two linked lists -- actions on the left, the selected action's bound keys on
the right -- with buttons to add / remove actions and keys.  Binding a key opens
a modal :class:`KeyCaptureDialog` that grabs the keyboard and returns the Qt key
name (e.g. ``"Key_A"``) exactly as the :class:`engine.core.input.InputManager`
expects.
"""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                               QPushButton, QLabel, QInputDialog, QDialog)


def _key_display(name: str) -> str:
    """Human-friendly label for a Qt key name like ``Key_Left`` -> ``Left``."""
    if name.startswith("Key_"):
        return name[len("Key_"):]
    return name


class KeyCaptureDialog(QDialog):
    """Modal dialog that captures the next key press."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("inputmap.capture_title"))
        self.key_name = None
        self.setMinimumWidth(280)
        self.setMaximumHeight(120)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("inputmap.capture_hint"))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        # NOTE: keyboard grabbing must happen *after* the dialog is shown (see
        # showEvent) -- grabbing in __init__ (while the widget is still hidden)
        # is silently ignored by Qt, which is exactly why key presses were never
        # delivered and the captured key ended up as None.

    def showEvent(self, event) -> None:
        # Bring the dialog to the front and steal keyboard focus from whatever
        # widget (e.g. the "Add key" button) currently holds it.  Only then grab
        # the keyboard so the next key press reaches our keyPressEvent.
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()
        self.grabKeyboard()

    def keyPressEvent(self, event) -> None:
        try:
            self.key_name = Qt.Key(event.key()).name
        except Exception:
            self.key_name = None
        self.accept()

    def mousePressEvent(self, event) -> None:  # don't bind mouse clicks
        self.reject()


class InputMapEditor(QWidget):
    """Edit a project ``input_map`` and return it via :meth:`get_map`."""

    def __init__(self, mapping: Dict[str, List[str]], parent=None):
        super().__init__(parent)
        self._mapping: Dict[str, List[str]] = {
            k: list(v) for k, v in (mapping or {}).items()}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lists = QHBoxLayout()
        # ----- actions -----
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("inputmap.actions")))
        self.action_list = QListWidget()
        self.action_list.addItems(sorted(self._mapping.keys()))
        lists.addLayout(left, 1)
        left.addWidget(self.action_list)
        self._action_btns = QHBoxLayout()
        self._add_action_btn = QPushButton(tr("inputmap.add_action"))
        self._add_action_btn.clicked.connect(self.add_action)
        self._rm_action_btn = QPushButton(tr("inputmap.remove_action"))
        self._rm_action_btn.clicked.connect(self.remove_action)
        self._action_btns.addWidget(self._add_action_btn)
        self._action_btns.addWidget(self._rm_action_btn)
        left.addLayout(self._action_btns)

        # ----- keys -----
        right = QVBoxLayout()
        right.addWidget(QLabel(tr("inputmap.keys")))
        self.key_list = QListWidget()
        lists.addLayout(right, 1)
        right.addWidget(self.key_list)
        self._key_btns = QHBoxLayout()
        self._add_key_btn = QPushButton(tr("inputmap.add_key"))
        self._add_key_btn.clicked.connect(self.add_key)
        self._rm_key_btn = QPushButton(tr("inputmap.remove_key"))
        self._rm_key_btn.clicked.connect(self.remove_key)
        self._key_btns.addWidget(self._add_key_btn)
        self._key_btns.addWidget(self._rm_key_btn)
        right.addLayout(self._key_btns)

        layout.addLayout(lists)

        hint = QLabel(tr("inputmap.apply_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.action_list.currentTextChanged.connect(self._on_action_selected)
        if self.action_list.count():
            self.action_list.setCurrentRow(0)
        else:
            self._on_action_selected("")

    # ------------------------------------------------------------------
    def _on_action_selected(self, action: str) -> None:
        self.key_list.clear()
        if action and action in self._mapping:
            self.key_list.addItems(
                _key_display(k) for k in self._mapping[action])

    def get_map(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._mapping.items()}

    # ----- actions -----
    def add_action(self) -> None:
        name, ok = QInputDialog.getText(
            self, tr("inputmap.add_action_title"), tr("inputmap.add_action_msg"))
        name = (name or "").strip()
        if ok and name and name not in self._mapping:
            self._mapping[name] = []
            self.action_list.addItem(name)
            self.action_list.setCurrentRow(self.action_list.count() - 1)

    def remove_action(self) -> None:
        item = self.action_list.currentItem()
        if item is None:
            return
        action = item.text()
        self._mapping.pop(action, None)
        self.action_list.takeItem(self.action_list.currentRow())

    # ----- keys -----
    def add_key(self) -> None:
        item = self.action_list.currentItem()
        if item is None:
            return
        action = item.text()
        dlg = KeyCaptureDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.key_name:
            if dlg.key_name not in self._mapping[action]:
                self._mapping[action].append(dlg.key_name)
                self.key_list.addItem(_key_display(dlg.key_name))

    def remove_key(self) -> None:
        a_item = self.action_list.currentItem()
        k_item = self.key_list.currentItem()
        if a_item is None or k_item is None:
            return
        action = a_item.text()
        displayed = k_item.text()
        # the displayed text is the friendly name; map back to the raw Key_ name
        for raw in self._mapping[action]:
            if _key_display(raw) == displayed:
                self._mapping[action] = [k for k in self._mapping[action]
                                         if k != raw]
                break
        self.key_list.takeItem(self.key_list.currentRow())


def tr(key: str, **kwargs) -> str:
    from editor.i18n import tr as _tr
    return _tr(key, **kwargs)
