"""Create Node dialog.

A searchable, Godot-like picker for choosing a node type.  Types are grouped
by category and sourced entirely from the :class:`NodeRegistry`, so any
built-in, plugin or user node appears automatically.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QTreeWidget,
                               QTreeWidgetItem, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt

from engine.core.registry import get_registry
from editor.i18n import tr


class CreateNodeDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle(tr("dialog.create_title"))
        self.resize(420, 500)
        self.selected_type = ""

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("dialog.search_ph"))
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(tr("dialog.node_types"))
        self.tree.itemDoubleClicked.connect(self._accept)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        self.ok_btn = QPushButton(tr("dialog.create"))
        self.ok_btn.setEnabled(False)
        self.cancel_btn = QPushButton(tr("dialog.cancel"))
        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self._populate()
        self.tree.itemSelectionChanged.connect(self._on_sel)

    # ------------------------------------------------------------------
    def _populate(self) -> None:
        cats = get_registry().categories()
        for cat, names in cats.items():
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, cat)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            for name in names:
                it = QTreeWidgetItem(cat_item)
                it.setText(0, name)
                it.setData(0, Qt.UserRole, name)
        self.tree.expandAll()

    def _filter(self, text: str) -> None:
        text = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            cat_visible = False
            for j in range(cat.childCount()):
                child = cat.child(j)
                match = text in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    cat_visible = True
            cat.setHidden(not cat_visible)

    def _on_sel(self) -> None:
        items = self.tree.selectedItems()
        has_selection = bool(items) and bool(items[0].data(0, Qt.UserRole))
        self.ok_btn.setEnabled(has_selection)

    def _accept(self) -> None:
        items = self.tree.selectedItems()
        if items and items[0].data(0, Qt.UserRole):
            self.selected_type = items[0].data(0, Qt.UserRole)
            self.accept()
        elif isinstance(self.tree.currentItem(), QTreeWidgetItem) and \
                self.tree.currentItem().parent() is not None:
            self.selected_type = self.tree.currentItem().text(0)
            self.accept()
