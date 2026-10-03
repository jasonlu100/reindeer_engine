"""FileSystem dock.

Browses the project directory as a collapsible **tree** so the directory
architecture is easy to read (the previous flat list quickly became a wall of
paths).  Double-clicking a scene opens it in the editor; double-clicking a
script opens it in the system editor.  Folder and file icons come from the
native style, and the expanded / selected state is preserved across refreshes.
"""
from __future__ import annotations

import os
import sys

import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDockWidget, QTreeWidget, QTreeWidgetItem,
                               QStyle, QMenu, QInputDialog, QMessageBox)

from editor.i18n import tr


#: boilerplate written into newly created scripts (matches the scripting API:
#: the runtime injects ``self.node`` / ``self.api`` / ``self.is_action_pressed``)
SCRIPT_TEMPLATE = '''"""New script. Attach it to a node via the Inspector."""

class NewScript:
    def _ready(self):
        # called once when the node enters the scene
        pass

    def _process(self, delta):
        # called every frame (delta is seconds since last frame)
        pass
'''


class FileSystemDock(QDockWidget):
    def __init__(self, editor, parent=None):
        super().__init__(tr("dock.filesystem"), parent)
        self.editor = editor
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabel(tr("tree.name"))
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context)
        self.setWidget(self.tree)

        # native folder / file icons
        st = self.style()
        self._folder_icon = st.standardIcon(QStyle.SP_DirIcon)
        self._file_icon = st.standardIcon(QStyle.SP_FileIcon)

        self.refresh()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("dock.filesystem"))
        self.tree.setHeaderLabel(tr("tree.name"))

    # ------------------------------------------------------------------
    def _is_ignored_dir(self, name: str) -> bool:
        return (name == "addons"
                or name in ("dist", "build", "__pycache__")
                or name.startswith("."))

    def _save_state(self):
        """Return the set of expanded directory rel-paths and the selected
        file rel-path so the tree can be rebuilt without losing the user's
        view."""
        expanded = set()
        selected = None
        root = self.tree.invisibleRootItem()

        def walk(item):
            nonlocal selected
            for i in range(item.childCount()):
                c = item.child(i)
                rel = c.data(0, Qt.UserRole)
                if rel:  # directories and files carry a rel-path
                    if c.childCount() > 0 and c.isExpanded():
                        expanded.add(rel)
                    if c.isSelected():
                        selected = rel
                walk(c)

        walk(root)
        return expanded, selected

    def refresh(self, *args) -> None:
        expanded, selected = self._save_state()
        self.tree.clear()

        root_path = self.editor.project.path
        name = os.path.basename(root_path.rstrip(os.sep)) or root_path
        root_item = QTreeWidgetItem(self.tree, [name])
        root_item.setData(0, Qt.UserRole, "")
        root_item.setData(0, Qt.UserRole + 1, True)  # is a directory
        root_item.setExpanded(True)
        root_item.setIcon(0, self._folder_icon)
        items = {root_path: root_item}

        for cur, dirs, fs in os.walk(root_path):
            # prune ignored directories so they never descend
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(d)]
            parent = items.get(cur)
            if parent is None:
                continue

            for d in sorted(dirs):
                dpath = os.path.join(cur, d)
                rel = self.editor.project.rel_path(dpath)
                child = QTreeWidgetItem(parent, [d])
                child.setData(0, Qt.UserRole, rel)
                child.setData(0, Qt.UserRole + 1, True)  # is a directory
                child.setIcon(0, self._folder_icon)
                if rel in expanded:
                    child.setExpanded(True)
                items[dpath] = child

            for f in sorted(fs):
                fpath = os.path.join(cur, f)
                rel = self.editor.project.rel_path(fpath)
                if rel == "project.reindeer":
                    continue
                fitem = QTreeWidgetItem(parent, [f])
                fitem.setData(0, Qt.UserRole, rel)
                fitem.setData(0, Qt.UserRole + 1, False)  # is a file
                fitem.setIcon(0, self._file_icon)
                if rel == selected:
                    fitem.setSelected(True)
                parent.addChild(fitem)

    # ------------------------------------------------------------------
    # context menu: create / delete / reveal files & folders
    # ------------------------------------------------------------------
    def _on_context(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        rel = item.data(0, Qt.UserRole) if item else ""
        is_dir = bool(item.data(0, Qt.UserRole + 1)) if item else False

        act_script = menu.addAction(tr("fs.ctx.new_script"))
        act_scene = menu.addAction(tr("fs.ctx.new_scene"))
        act_folder = menu.addAction(tr("fs.ctx.new_folder"))
        menu.addSeparator()

        if item is not None and not is_dir:
            act_open = menu.addAction(tr("fs.ctx.open"))
            act_reveal = menu.addAction(tr("fs.ctx.reveal"))
            menu.addSeparator()
            act_delete = menu.addAction(tr("fs.ctx.delete"))
        elif item is not None and is_dir:
            act_reveal = menu.addAction(tr("fs.ctx.reveal"))
            menu.addSeparator()
            act_delete = menu.addAction(tr("fs.ctx.delete"))
        else:
            act_reveal = menu.addAction(tr("fs.ctx.reveal"))
        menu.addSeparator()
        act_refresh = menu.addAction(tr("fs.ctx.refresh"))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        # resolve the directory new items should be created in
        if is_dir and rel:
            target_dir = rel
        elif rel and not is_dir:
            target_dir = os.path.dirname(rel)
        else:
            target_dir = ""

        # dispatch by action identity (robust to translation / menu text)
        if chosen is act_script:
            self._new_script(target_dir)
        elif chosen is act_scene:
            self._new_scene(target_dir)
        elif chosen is act_folder:
            self._new_folder(target_dir)
        elif chosen is act_open:
            self._on_double(item, 0)
        elif chosen is act_reveal:
            self._reveal(rel, is_dir)
        elif chosen is act_delete:
            self._delete(item, rel, is_dir)
        elif chosen is act_refresh:
            self.refresh()

    # ---- creation helpers ----
    def _create_in(self, dir_rel, name, kind, content="") -> None:
        base = (self.editor.project.abs_path(dir_rel)
                if dir_rel else self.editor.project.path)
        full = os.path.join(base, name)
        if os.path.exists(full):
            QMessageBox.warning(self, tr("fs.ctx.new_folder"),
                                tr("fs.exists", name=name))
            return
        try:
            if kind == "folder":
                os.makedirs(full, exist_ok=True)
            elif kind == "scene":
                self._write_scene(full)
            else:  # script
                with open(full, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception as exc:
            QMessageBox.critical(self, tr("fs.ctx.new_folder"),
                                 tr("fs.create_error", err=str(exc)))
            return
        self.refresh()

    def _new_script(self, dir_rel) -> None:
        name, ok = QInputDialog.getText(self, tr("fs.ctx.new_script"),
                                        tr("fs.new_script_msg"),
                                        text="new_script")
        if not (ok and name.strip()):
            return
        name = name.strip()
        if not name.endswith(".py"):
            name += ".py"
        self._create_in(dir_rel, name, "script", SCRIPT_TEMPLATE)

    def _new_scene(self, dir_rel) -> None:
        name, ok = QInputDialog.getText(self, tr("fs.ctx.new_scene"),
                                        tr("fs.new_scene_msg"),
                                        text="new_scene")
        if not (ok and name.strip()):
            return
        name = name.strip()
        if not name.endswith(".reindeer.tscn"):
            name += ".reindeer.tscn"
        self._create_in(dir_rel, name, "scene")

    def _new_folder(self, dir_rel) -> None:
        name, ok = QInputDialog.getText(self, tr("fs.ctx.new_folder"),
                                        tr("fs.new_folder_msg"),
                                        text="new_folder")
        if ok and name.strip():
            self._create_in(dir_rel, name.strip(), "folder")

    def _write_scene(self, full) -> None:
        from engine.core.registry import get_registry
        from engine.core.scene_format import SceneLoader
        get_registry().autodiscover("engine.nodes")
        root = get_registry().create("Node2D", "Main")
        SceneLoader(None).save(root, full)

    def _reveal(self, rel, is_dir) -> None:
        full = (self.editor.project.abs_path(rel)
                if rel else self.editor.project.path)
        try:
            if rel and not is_dir:
                self._reveal_file(full)
            else:
                self._reveal_dir(full)
        except Exception as exc:
            print(f"[editor] reveal failed: {exc}")

    # ---- cross-platform "show in file manager" helpers ----
    @staticmethod
    def _reveal_dir(path: str) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def _reveal_file(path: str) -> None:
        if sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,",
                            os.path.normpath(path)], check=False)
        else:
            FileSystemDock._reveal_dir(os.path.dirname(path))

    @staticmethod
    def _open_external(path: str) -> None:
        """Open a file/folder in the OS default handler (cross-platform)."""
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _delete(self, item, rel, is_dir) -> None:
        if not rel:
            return  # never delete the project root
        if rel == "project.reindeer":
            QMessageBox.warning(self, tr("fs.delete_title"),
                                tr("fs.cannot_delete"))
            return
        ans = QMessageBox.question(
            self, tr("fs.delete_title"),
            tr("fs.delete_msg", name=os.path.basename(rel)),
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        full = self.editor.project.abs_path(rel)
        try:
            if is_dir:
                import shutil
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)
        except Exception as exc:
            QMessageBox.critical(self, tr("fs.delete_title"),
                                 tr("fs.delete_error", err=str(exc)))
            return
        self.refresh()

    # ------------------------------------------------------------------
    def _on_double(self, item, column) -> None:
        rel = item.data(0, Qt.UserRole)
        if not rel:
            return  # a directory: just expand / collapse
        full = self.editor.project.abs_path(rel)
        if rel.endswith(".reindeer.tscn"):
            self.editor.open_scene(rel)
        else:
            self._open_external(full)
