"""Scene tree dock: hierarchical view of the active scene.

Mirrors Godot's Scene dock - shows the node tree, supports selecting,
renaming, deleting and reparenting nodes (via drag & drop), and adding new
nodes through the *Create Node* dialog.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDockWidget, QTreeWidget, QTreeWidgetItem,
                               QMenu, QInputDialog)
from PySide6.QtCore import Qt

from editor.dialogs.create_node_dialog import CreateNodeDialog
from editor.i18n import tr


class SceneTreeDock(QDockWidget):
    def __init__(self, editor, parent=None):
        super().__init__(tr("dock.scene"), parent)
        self.editor = editor
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabel(tr("tree.header"))
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.itemChanged.connect(self._on_rename)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.setWidget(self.tree)
        self._items = {}   # node id -> item

    def retranslate(self) -> None:
        self.setWindowTitle(tr("dock.scene"))
        self.tree.setHeaderLabel(tr("tree.header"))

    # ------------------------------------------------------------------
    def refresh(self, selected: object = None) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._items.clear()
        root = self.editor.get_render_root()
        if root is not None:
            self._add_node(root, self.tree.invisibleRootItem())
        # restore the highlight so the tree matches the inspector / viewport
        if selected is not None:
            item = self._items.get(getattr(selected, "id", None))
            if item is not None:
                item.setSelected(True)
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
        self.tree.blockSignals(False)

    def _add_node(self, node, parent_item) -> None:
        item = QTreeWidgetItem(parent_item)
        item.setText(0, f"{node.name} ({type(node).__name__})")
        item.setData(0, Qt.UserRole, node.id)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._items[node.id] = item
        for c in node.children:
            self._add_node(c, item)

    def _find_node_by_id(self, nid, node=None):
        node = node or self.editor.get_render_root()
        if node is None:
            return None
        if node.id == nid:
            return node
        for c in node.children:
            r = self._find_node_by_id(nid, c)
            if r:
                return r
        return None

    # ------------------------------------------------------------------
    def _on_selection(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        nid = items[0].data(0, Qt.UserRole)
        node = self._find_node_by_id(nid)
        if node is not None:
            self.editor.select_node(node, from_tree=True)

    def _on_rename(self, item, column) -> None:
        if column != 0:
            return
        nid = item.data(0, Qt.UserRole)
        node = self._find_node_by_id(nid)
        if node is not None:
            new_name = item.text(0).split(" (")[0]
            old_name = node.name
            node.name = new_name
            self.editor.push_property_change(node, "name", old_name, new_name)

    # ------------------------------------------------------------------
    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        node = self._find_node_by_id(item.data(0, Qt.UserRole)) if item else None
        menu = QMenu(self)
        add_action = menu.addAction(tr("ctx.add_child"))
        dup_action = menu.addAction(tr("ctx.duplicate"))
        del_action = menu.addAction(tr("ctx.delete_node"))
        dup_action.setEnabled(node is not None and node is not self.editor.edit_root)
        del_action.setEnabled(node is not None and node is not self.editor.edit_root)
        act = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if act == add_action:
            self._add_child(node)
        elif act == dup_action and node is not None:
            self.editor.duplicate_node(node)
        elif act == del_action and node is not None:
            self.editor.delete_node(node)

    def _add_child(self, parent_node) -> None:
        dlg = CreateNodeDialog(self.editor, self)
        if dlg.exec():
            type_name = dlg.selected_type
            if type_name:
                self.editor.create_node(type_name, parent_node)

    # ------------------------------------------------------------------
    def dropEvent(self, event) -> None:
        target_item = self.tree.itemAt(event.pos())
        source_item = self.tree.currentItem()
        if target_item is None or source_item is None or target_item is source_item:
            event.ignore()
            return
        src = self._find_node_by_id(source_item.data(0, Qt.UserRole))
        tgt = self._find_node_by_id(target_item.data(0, Qt.UserRole))
        if src is None or tgt is None:
            event.ignore()
            return
        if src is tgt:
            event.ignore()
            return
        if tgt is self.editor.edit_root:
            # dropping onto the scene root just reorders to the end -> treat as a
            # no-op and do not accept a pointless drop
            event.ignore()
            return
        # prevent dropping a node into its own descendant
        if self._is_descendant(tgt, src):
            event.ignore()
            return
        self.editor.reparent_node(src, tgt)
        event.accept()

    def _is_descendant(self, node, ancestor) -> bool:
        p = node.parent
        while p is not None:
            if p is ancestor:
                return True
            p = p.parent
        return False
