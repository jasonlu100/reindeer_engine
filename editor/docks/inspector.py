"""Inspector dock.

Displays and edits the exported properties of the selected node.  Widgets are
generated generically from each node's :class:`PropertyDef` metadata, so the
inspector automatically supports every node type - built-in, plugin or user
defined.  It also exposes the *script attachment* control.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDockWidget, QWidget, QFormLayout, QLineEdit,
                               QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout,
                               QColorDialog, QFileDialog, QLabel, QScrollArea)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from engine.core.node import (PT_FLOAT, PT_INT, PT_BOOL, PT_STRING, PT_VECTOR2,
                              PT_VECTOR2I, PT_COLOR, PT_ENUM, PT_RESOURCE,
                              PT_NODE_PATH)
from engine.core.math2d import Vector2, Color
from editor.i18n import tr


class InspectorDock(QDockWidget):
    def __init__(self, editor, parent=None):
        super().__init__(tr("dock.inspector"), parent)
        self.editor = editor
        self.current_node = None
        self._widgets = {}

        self.scroll = QScrollArea()
        self.container = QWidget()
        self.form = QFormLayout(self.container)
        self.scroll.setWidget(self.container)
        self.scroll.setWidgetResizable(True)
        self.setWidget(self.scroll)

    # ------------------------------------------------------------------
    def inspect(self, node) -> None:
        self.current_node = node
        self._clear()
        if node is None:
            self.form.addRow(QLabel(tr("inspector.none")))
            return

        title = QLabel(f"<b>{node.name}</b>  ({type(node).__name__})")
        self.form.addRow(title)

        for pdef in node.get_property_list():
            self._add_property_row(node, pdef)

        # script attachment
        self.form.addRow(QLabel(""))
        self.form.addRow(QLabel(f"<b>{tr('inspector.script')}</b>"))
        script_row = QHBoxLayout()
        self.script_edit = QLineEdit(getattr(node, "script_path", "") or "")
        browse = QPushButton("...")
        browse.clicked.connect(self._browse_script)
        script_row.addWidget(self.script_edit)
        script_row.addWidget(browse)
        self.form.addRow(tr("inspector.script_label"), script_row)
        self.script_edit.editingFinished.connect(self._on_script_changed)

        self.container.adjustSize()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("dock.inspector"))
        self.inspect(self.current_node)

    def _clear(self) -> None:
        while self.form.count():
            item = self.form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._widgets.clear()

    # ------------------------------------------------------------------
    def _add_property_row(self, node, pdef) -> None:
        val = node.get_property(pdef.name)
        if pdef.type == PT_BOOL:
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(lambda v, n=node, p=pdef: self._set(n, p, v))
        elif pdef.type == PT_INT:
            w = QSpinBox()
            w.setRange(pdef.min_value if pdef.min_value is not None else -999999,
                       pdef.max_value if pdef.max_value is not None else 999999)
            w.setValue(int(val or 0))
            w.valueChanged.connect(lambda v, n=node, p=pdef: self._set(n, p, v))
        elif pdef.type == PT_FLOAT:
            w = QDoubleSpinBox()
            w.setRange(-1e9, 1e9)
            w.setSingleStep(0.1)
            w.setValue(float(val or 0))
            w.valueChanged.connect(lambda v, n=node, p=pdef: self._set(n, p, v))
        elif pdef.type == PT_ENUM:
            w = QComboBox()
            w.addItems(pdef.options)
            if val in pdef.options:
                w.setCurrentText(val)
            w.currentTextChanged.connect(
                lambda v, n=node, p=pdef: self._set(n, p, v))
        elif pdef.type == PT_VECTOR2:
            self._add_vector_row(node, pdef, val, False)
            return
        elif pdef.type == PT_VECTOR2I:
            self._add_vector_row(node, pdef, val, True)
            return
        elif pdef.type == PT_COLOR:
            w = QPushButton(self._color_text(val))
            w.clicked.connect(
                lambda _, n=node, p=pdef, btn=w: self._edit_color(n, p, btn))
        elif pdef.type in (PT_STRING, PT_RESOURCE, PT_NODE_PATH):
            w = QWidget()
            hl = QHBoxLayout(w)
            le = QLineEdit("" if val is None else str(val))
            le.editingFinished.connect(
                lambda le=le, n=node, p=pdef: self._set(n, p, le.text()))
            hl.addWidget(le)
            if pdef.type == PT_RESOURCE:
                b = QPushButton("...")
                b.clicked.connect(lambda _, le=le, n=node, p=pdef:
                                 self._browse_resource(le, n, p))
                hl.addWidget(b)
        else:
            # unknown property type: if it looks like a vector, edit it as one;
            # otherwise fall back to a plain (uneditable-without-retype) text box
            if hasattr(val, "x") and hasattr(val, "y"):
                self._add_vector_row(node, pdef, val, False)
                return
            else:
                w = QLineEdit("" if val is None else str(val))
                w.editingFinished.connect(
                    lambda w=w, n=node, p=pdef: self._set(n, p, w.text()))

        self._widgets[pdef.name] = w
        self.form.addRow(pdef.name, w)

    # ------------------------------------------------------------------
    def _add_vector_row(self, node, pdef, val, is_int) -> None:
        w = QWidget()
        hl = QHBoxLayout(w)
        if is_int:
            sx = QSpinBox(); sy = QSpinBox()
            sx.setRange(-999999, 999999); sy.setRange(-999999, 999999)
            sx.setValue(int(getattr(val, "x", 0)))
            sy.setValue(int(getattr(val, "y", 0)))
        else:
            sx = QDoubleSpinBox(); sy = QDoubleSpinBox()
            sx.setRange(-1e9, 1e9); sy.setRange(-1e9, 1e9)
            sx.setSingleStep(0.1); sy.setSingleStep(0.1)
            sx.setValue(float(getattr(val, "x", 0)))
            sy.setValue(float(getattr(val, "y", 0)))
        hl.addWidget(sx); hl.addWidget(sy)
        sx.valueChanged.connect(
            lambda vx, n=node, p=pdef, syy=sy: self._set(
                n, p, Vector2(vx, syy.value())))
        sy.valueChanged.connect(
            lambda vy, n=node, p=pdef, sxx=sx: self._set(
                n, p, Vector2(sxx.value(), vy)))
        self._widgets[pdef.name] = w
        self.form.addRow(pdef.name, w)

    # ------------------------------------------------------------------
    def _set(self, node, pdef, value) -> None:
        old = node.get_property(pdef.name)
        node.set_property(pdef.name, value)
        self.editor.push_property_change(node, pdef.name, old, value)

    def _color_text(self, c: Color) -> str:
        return f"RGBA({c.r:.2f}, {c.g:.2f}, {c.b:.2f}, {c.a:.2f})"

    def _edit_color(self, node, pdef, btn) -> None:
        cur = node.get_property(pdef.name)
        dlg = QColorDialog(QColor.fromRgba(cur.to_qrgba()), self)
        if dlg.exec():
            qc = dlg.selectedColor()
            new = Color(qc.redF(), qc.greenF(), qc.blueF(), qc.alphaF())
            node.set_property(pdef.name, new)
            btn.setText(self._color_text(new))
            self.editor.push_property_change(node, pdef.name, cur, new)

    def _browse_resource(self, le, node, pdef) -> None:
        exts = (pdef.resource_ext or "").split(",")
        exts = [e.strip().lower() for e in exts if e.strip()]
        if exts:
            wildcards = " ".join(f"*.{e}" for e in exts)
            filters = [f"Resources ({wildcards})", "All files (*.*)"]
        else:
            filters = ["Resources (*.png *.jpg *.jpeg *.wav *.ogg *.mp3)",
                       "All files (*.*)"]
        path, _ = QFileDialog.getOpenFileName(
            self, "Select resource", self.editor.project.path,
            ";;".join(filters))
        if path:
            rel = self.editor.project.rel_path(path)
            old = node.get_property(pdef.name)
            le.setText(rel)
            node.set_property(pdef.name, rel)
            self.editor.push_property_change(node, pdef.name, old, rel)

    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select script", self.editor.project.path, "Python (*.py)")
        if path:
            rel = self.editor.project.rel_path(path)
            self.script_edit.setText(rel)
            self._on_script_changed()

    def _on_script_changed(self):
        if self.current_node is None:
            return
        old = self.current_node.script_path
        self.current_node.script_path = self.script_edit.text()
        self.editor.push_property_change(self.current_node, "script_path",
                                         old, self.current_node.script_path)
