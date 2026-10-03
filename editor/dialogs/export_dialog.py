"""Export / packaging dialog.

Lets the user configure how a Reindeer project is turned into a standalone
``.exe``: product name, company (copyright), the main scene, the set of scenes
to bundle, an optional splash screen image and the run backend.  Pressing
*Build EXE* invokes :func:`engine.runtime.build_exe.build_exe` in a worker
thread so the editor stays responsive, then reports the result.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QComboBox,
                               QListWidget, QListWidgetItem, QPushButton,
                               QFileDialog, QCheckBox, QHBoxLayout, QVBoxLayout,
                               QProgressBar, QLabel, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal

from editor.i18n import tr


class _BuildThread(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, kwargs: dict):
        super().__init__()
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            from engine.runtime.build_exe import build_exe
            exe = build_exe(**self.kwargs)
            self.finished.emit(exe)
        except Exception as exc:
            import traceback
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")


class ExportDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(tr("export.title"))
        self.resize(520, 560)

        scenes = project.scan_scenes()
        main_scene = project.main_scene or (scenes[0] if scenes else "")

        # ---- form fields ----
        form = QFormLayout()

        self.name_edit = QLineEdit(project.name or "MyGame")
        form.addRow(tr("export.product_name"), self.name_edit)

        self.company_edit = QLineEdit("")
        form.addRow(tr("export.company"), self.company_edit)

        self.main_combo = QComboBox()
        self.main_combo.addItems(scenes)
        if main_scene and main_scene in scenes:
            self.main_combo.setCurrentText(main_scene)
        form.addRow(tr("export.main_scene"), self.main_combo)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems([tr("menu.backend_pyside"),
                                     tr("menu.backend_pygame")])
        rb = project.config.get("run_backend", "pyside6")
        self.backend_combo.setCurrentIndex(0 if rb in ("pyside6", "qt") else 1)
        form.addRow(tr("export.backend"), self.backend_combo)

        # ---- scenes checklist ----
        self.scenes_list = QListWidget()
        for sc in scenes:
            item = QListWidgetItem(sc)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable
                          | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked)
            self.scenes_list.addItem(item)
        form.addRow(tr("export.scenes"), self.scenes_list)

        # ---- splash ----
        splash_row = QHBoxLayout()
        self.splash_edit = QLineEdit("")
        self.splash_edit.setPlaceholderText(tr("export.splash_none"))
        browse = QPushButton(tr("export.browse"))
        browse.clicked.connect(self._browse_splash)
        splash_row.addWidget(self.splash_edit)
        splash_row.addWidget(browse)
        form.addRow(tr("export.splash"), splash_row)

        # ---- output ----
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit(os.path.join(project.path, "dist"))
        out_browse = QPushButton(tr("export.browse"))
        out_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_edit)
        out_row.addWidget(out_browse)
        form.addRow(tr("export.output"), out_row)

        self.clean_chk = QCheckBox(tr("export.clean"))
        self.clean_chk.setChecked(True)
        form.addRow("", self.clean_chk)

        # ---- buttons + progress ----
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)        # indeterminate
        self.progress.setVisible(False)
        self.status_label = QLabel("")
        self.build_btn = QPushButton(tr("export.build"))
        self.build_btn.clicked.connect(self._build)
        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.build_btn)
        btn_row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addLayout(btn_row)

        self._thread = None

    # ------------------------------------------------------------------
    def _browse_splash(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("export.splash"), "",
            "PNG Images (*.png);;All Files (*.*)")
        if path:
            self.splash_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tr("export.output"), self.output_edit.text() or self.project.path)
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    def _collect_scenes(self) -> list:
        checked = []
        for i in range(self.scenes_list.count()):
            item = self.scenes_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        # Safety net: if the user somehow unchecked everything, fall back to
        # bundling every listed scene rather than failing the build.
        if not checked:
            checked = [self.scenes_list.item(i).text()
                      for i in range(self.scenes_list.count())]
        return checked

    # ------------------------------------------------------------------
    def _build(self) -> None:
        name = self.name_edit.text().strip() or "Game"
        if self.main_combo.currentIndex() < 0:
            QMessageBox.warning(self, tr("export.title"),
                                tr("export.no_main"))
            return
        included = self._collect_scenes()
        if not included:
            QMessageBox.warning(self, tr("export.title"),
                                tr("export.no_scenes"))
            return

        backend = ("pyside6" if self.backend_combo.currentIndex() == 0
                   else "pygame")
        kwargs = dict(
            project_dir=self.project.path,
            product_name=name,
            company=self.company_edit.text().strip(),
            main_scene=self.main_combo.currentText(),
            included_scenes=included,
            splash=self.splash_edit.text().strip(),
            output_dir=self.output_edit.text().strip(),
            backend=backend,
            clean=self.clean_chk.isChecked(),
        )

        self.build_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setText(tr("export.building"))
        self._thread = _BuildThread(kwargs)
        self._thread.finished.connect(self._on_done)
        self._thread.failed.connect(self._on_fail)
        self._thread.start()

    # ------------------------------------------------------------------
    def _on_done(self, exe_path: str) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self.build_btn.setEnabled(True)
        QMessageBox.information(self, tr("export.title"),
                                tr("export.done", path=exe_path))
        self.accept()

    def _on_fail(self, err: str) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self.build_btn.setEnabled(True)
        QMessageBox.critical(self, tr("export.title"),
                             tr("export.fail", err=err))

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait()
        super().closeEvent(event)
