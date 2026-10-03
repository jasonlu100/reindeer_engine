"""Project manager ("hub") for the Reindeer Engine.

This is a standalone launcher window that sits **in front of** the editor.  It
lets the user keep several independent projects and decide which one to open:

* list known projects (persisted in a small JSON registry),
* create a brand new project (folders + ``project.reindeer`` + a starter scene),
* import an existing project folder (one that already contains ``project.reindeer``),
* open / remove-from-list / permanently delete projects,
* and finally launch the editor for the chosen project.

The editor itself is unchanged: ``Editor(project_path)`` still works exactly as
before.  When the editor window is closed the manager reappears, so the two are
cleanly separated but linked.
"""
from __future__ import annotations

import json
import os
import time
import zipfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget, QStyle,
                               QMessageBox)

from editor.i18n import tr
from editor.branding import engine_logo, engine_icon
from editor.settings import SETTINGS_DIR
from editor.project import Project, package_project, extract_package


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOCATION = os.path.join(REPO_ROOT, "projects")

REG_PATH = os.path.join(SETTINGS_DIR, "projects.json")


# ----------------------------------------------------------------------
# registry persistence
# ----------------------------------------------------------------------
def load_registry() -> list:
    """Return the list of known projects as ``[{name, path}, ...]``."""
    try:
        with open(REG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [d for d in data
                    if isinstance(d, dict) and d.get("path")]
    except Exception:
        pass
    return []


def save_registry(items: list) -> None:
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(REG_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        # best-effort; never break the manager over a write error
        pass


def _add_to_registry(path: str) -> None:
    path = os.path.abspath(path)
    items = load_registry()
    if any(os.path.abspath(i["path"]) == path for i in items):
        return
    name = Project(path).name if os.path.isdir(path) else os.path.basename(path)
    items.insert(0, {"name": name, "path": path})
    save_registry(items)


# ----------------------------------------------------------------------
# "New Project" dialog
# ----------------------------------------------------------------------
class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("manager.new_title"))
        self.setWindowIcon(engine_icon())
        self.setMinimumWidth(460)

        form = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("manager.new_name_ph"))
        form.addRow(tr("manager.new_name"), self.name_edit)

        loc_row = QHBoxLayout()
        self.loc_edit = QLineEdit(DEFAULT_LOCATION)
        self.browse_btn = QPushButton(tr("manager.new_browse"))
        self.browse_btn.clicked.connect(self._browse)
        loc_row.addWidget(self.loc_edit)
        loc_row.addWidget(self.browse_btn)
        form.addRow(tr("manager.new_location"), loc_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("manager.new_create"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("manager.new_cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.name_edit.setFocus()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, tr("manager.new_location"), self.loc_edit.text())
        if d:
            self.loc_edit.setText(d)

    def data(self):
        return self.name_edit.text().strip(), self.loc_edit.text().strip()


# ----------------------------------------------------------------------
# manager window
# ----------------------------------------------------------------------
class ProjectManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app.title") + " — " + tr("manager.title"))
        self.setWindowIcon(engine_icon())
        self.resize(760, 480)

        self._editor = None
        self._projects = []

        st = self.style()
        self._folder_icon = st.standardIcon(QStyle.SP_DirIcon)

        self._build_ui()
        self._apply_style()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # ---- header (logo + titles) ----
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(engine_logo(56))
        header.addWidget(logo)
        titles = QVBoxLayout()
        self.title_lbl = QLabel("<h2 style='margin:0'>" +
                               tr("app.title") + "</h2>")
        self.subtitle_lbl = QLabel("<span style='color:#9fb3ab'>" +
                                   tr("manager.subtitle") + "</span>")
        titles.addWidget(self.title_lbl)
        titles.addWidget(self.subtitle_lbl)
        header.addLayout(titles)
        header.addStretch(1)
        root.addLayout(header)

        # ---- body: list + side panel ----
        body = QHBoxLayout()
        body.setSpacing(14)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_selected)
        self.list.currentItemChanged.connect(self._on_select)
        body.addWidget(self.list, 2)

        side = QVBoxLayout()
        side.setSpacing(10)

        self.detail = QLabel(tr("manager.no_projects"))
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(110)
        self.detail.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        side.addWidget(self.detail)

        side.addStretch(1)

        self.open_btn = QPushButton(tr("manager.open"))
        self.open_btn.setMinimumHeight(34)
        self.open_btn.clicked.connect(self.open_selected)
        side.addWidget(self.open_btn)

        self.remove_btn = QPushButton(tr("manager.remove"))
        self.remove_btn.clicked.connect(self.remove_selected)
        side.addWidget(self.remove_btn)

        self.delete_btn = QPushButton(tr("manager.delete"))
        self.delete_btn.clicked.connect(self.delete_selected)
        side.addWidget(self.delete_btn)

        side.addSpacing(8)

        self.new_btn = QPushButton(tr("manager.new"))
        self.new_btn.clicked.connect(self.new_project)
        side.addWidget(self.new_btn)

        self.import_btn = QPushButton(tr("manager.import"))
        self.import_btn.clicked.connect(self.import_project)
        side.addWidget(self.import_btn)

        self.import_pkg_btn = QPushButton(tr("manager.new_from_pkg"))
        self.import_pkg_btn.clicked.connect(self.import_package)
        side.addWidget(self.import_pkg_btn)

        self.export_pkg_btn = QPushButton(tr("manager.export_pkg"))
        self.export_pkg_btn.clicked.connect(self.export_package)
        side.addWidget(self.export_pkg_btn)

        self.refresh_btn = QPushButton(tr("manager.refresh"))
        self.refresh_btn.clicked.connect(self.refresh)
        side.addWidget(self.refresh_btn)

        side.addSpacing(8)

        self.quit_btn = QPushButton(tr("manager.quit"))
        self.quit_btn.clicked.connect(self.close)
        side.addWidget(self.quit_btn)

        body.addLayout(side, 1)
        root.addLayout(body)

    # ------------------------------------------------------------------
    def _apply_style(self) -> None:
        self.setStyleSheet("""
            ProjectManager QPushButton {
                padding: 6px 12px;
                border-radius: 6px;
            }
            ProjectManager QListWidget {
                border-radius: 8px;
                padding: 4px;
            }
            ProjectManager QLabel#detail, .QLabel {
                border-radius: 6px;
            }
        """)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.list.clear()
        self._projects = load_registry()
        if not self._projects:
            self.detail.setText(tr("manager.no_projects"))
        for d in self._projects:
            path = d.get("path")
            name = d.get("name") or os.path.basename(path)
            item = QListWidgetItem(self._folder_icon, name)
            item.setData(Qt.UserRole, path)
            # store the clean name separately so parsing the (possibly
            # translated) "missing" suffix off the display text is unnecessary
            item.setData(Qt.UserRole + 1, name)
            if not os.path.isdir(path):
                item.setForeground(QColor("#d08a8a"))
                item.setText(f"{name}  ({tr('manager.missing')})")
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._on_select(self.list.currentItem(), None)

    def _on_select(self, current, _previous) -> None:
        if current is None:
            self.detail.setText(tr("manager.no_projects"))
            self.open_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        path = current.data(Qt.UserRole)
        name = current.data(Qt.UserRole + 1) or os.path.basename(path)
        lines = [f"<b>{name}</b>",
                 f"<span style='color:#9fb3ab'>{tr('manager.path')}: "
                 f"{path}</span>"]
        if os.path.isdir(path):
            try:
                mtime = os.path.getmtime(path)
                tstr = time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(mtime))
                lines.append(f"<span style='color:#9fb3ab'>"
                             f"{tr('manager.modified')}: {tstr}</span>")
            except Exception:
                pass
            try:
                scenes = Project(path).scan_scenes()
                lines.append(f"<span style='color:#9fb3ab'>"
                             f"{tr('manager.scenes')}: {len(scenes)}</span>")
            except Exception:
                pass
        else:
            lines.append(f"<span style='color:#d08a8a'>"
                         f"({tr('manager.missing')})</span>")
        self.detail.setText("<br>".join(lines))
        self.open_btn.setEnabled(os.path.isdir(path))
        self.remove_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def selected_path(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def open_selected(self) -> None:
        path = self.selected_path()
        if not path:
            QMessageBox.information(self, tr("manager.title"),
                                    tr("manager.empty_warn"))
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, tr("manager.title"),
                                tr("manager.missing_warn", name=os.path.basename(path)))
            return
        self.open_project(path)

    def closeEvent(self, event) -> None:
        # if a child editor is still open (e.g. the manager window was closed
        # directly), make sure it is torn down too so the process exits cleanly
        if self._editor is not None:
            try:
                self._editor.close()
            except Exception:
                pass
        super().closeEvent(event)

    def open_project(self, path: str) -> None:
        # import here so the editor package is only loaded when actually needed
        from editor.editor_window import Editor
        editor = Editor(os.path.abspath(path))
        editor.setWindowIcon(engine_icon())
        # when the editor is closed we return to the manager
        editor.setAttribute(Qt.WA_DeleteOnClose, True)
        editor.destroyed.connect(self._on_editor_closed)
        self._editor = editor
        self.hide()
        editor.show()

    def _on_editor_closed(self) -> None:
        self._editor = None
        self.retranslate()
        self.refresh()
        self.show()
        self.raise_()

    # ------------------------------------------------------------------
    def new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, location = dlg.data()
        if not name:
            QMessageBox.warning(self, tr("manager.new_title"),
                                tr("manager.new_invalid"))
            return
        proj_dir = os.path.join(location, name)
        if os.path.exists(proj_dir):
            QMessageBox.warning(self, tr("manager.new_title"),
                                tr("manager.new_exists"))
            return
        try:
            os.makedirs(proj_dir, exist_ok=True)
            proj = Project(proj_dir)
            proj.name = name
            proj.save_config()
            proj.ensure_dirs()
            self._create_starter_scene(proj)
        except Exception as exc:
            QMessageBox.critical(self, tr("manager.new_title"),
                                 tr("manager.new_error", err=str(exc)))
            return
        _add_to_registry(proj_dir)
        self.refresh()
        QMessageBox.information(self, tr("manager.new_title"),
                                tr("manager.new_created", name=name))

    @staticmethod
    def _create_starter_scene(proj: Project) -> None:
        """Create a minimal ``scenes/main.reindeer.tscn`` so the project opens
        with something usable.  Best-effort: failure just means a blank project."""
        try:
            from engine.core.registry import get_registry
            from engine.core.scene_format import SceneLoader
            # nodes self-register when their package is imported
            get_registry().autodiscover("engine.nodes")
            root = get_registry().create("Node2D", "Main")
            loader = SceneLoader(None)  # edit mode: no script execution
            scene_rel = "scenes/main.reindeer.tscn"
            loader.save(root, proj.abs_path(scene_rel))
            proj.main_scene = scene_rel
            proj.save_config()
        except Exception as exc:
            print(f"[manager] starter scene not created: {exc}")

    def import_project(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, tr("manager.import_title"),
            os.path.expanduser("~"))
        if not d:
            return
        cfg = os.path.join(d, Project.CONFIG_FILE)
        if not os.path.exists(cfg):
            QMessageBox.warning(self, tr("manager.import_title"),
                                tr("manager.import_invalid"))
            return
        _add_to_registry(d)
        self.refresh()

    # ------------------------------------------------------------------
    def import_package(self) -> None:
        """Create a NEW project by extracting a shared .zip resource package.

        Useful for 二创 / modding: download someone's package, point at the .zip,
        pick a name + location, and a fresh editable project is created.  If the
        package lacks a ``project.reindeer`` config, a default one + starter
        scene are generated so any zip of assets becomes a working project.
        """
        zpath, _ = QFileDialog.getOpenFileName(
            self, tr("manager.new_from_pkg_title"),
            os.path.expanduser("~"), tr("manager.pkg_filter"))
        if not zpath:
            return
        if not zipfile.is_zipfile(zpath):
            QMessageBox.warning(self, tr("manager.new_from_pkg_title"),
                                tr("manager.import_pkg_invalid"))
            return
        dlg = NewProjectDialog(self)
        dlg.setWindowTitle(tr("manager.new_from_pkg_title"))
        dlg.name_edit.setText(os.path.splitext(os.path.basename(zpath))[0])
        if dlg.exec() != QDialog.Accepted:
            return
        name, location = dlg.data()
        if not name:
            QMessageBox.warning(self, tr("manager.new_from_pkg_title"),
                                tr("manager.new_invalid"))
            return
        dest = os.path.join(location, name)
        if os.path.exists(dest):
            QMessageBox.warning(self, tr("manager.new_from_pkg_title"),
                                tr("manager.new_exists"))
            return
        try:
            os.makedirs(dest, exist_ok=True)
            extract_package(zpath, dest)
            # guarantee a valid project even if the package had no config
            if not os.path.exists(os.path.join(dest, Project.CONFIG_FILE)):
                proj = Project(dest)
                proj.name = name
                proj.save_config()
                proj.ensure_dirs()
                self._create_starter_scene(proj)
        except Exception as exc:
            QMessageBox.critical(self, tr("manager.new_from_pkg_title"),
                                 tr("manager.new_error", err=str(exc)))
            return
        _add_to_registry(dest)
        self.refresh()
        QMessageBox.information(self, tr("manager.new_from_pkg_title"),
                                tr("manager.new_created", name=name))

    def export_package(self) -> None:
        """Package the selected project into a shareable .zip (for 二创 / backup)."""
        path = self.selected_path()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, tr("manager.export_pkg_title"),
                                tr("manager.export_pkg_nosel"))
            return
        default_name = os.path.basename(path) + ".reindeer.zip"
        out, _ = QFileDialog.getSaveFileName(
            self, tr("manager.export_pkg_title"),
            os.path.join(os.path.expanduser("~"), default_name),
            tr("manager.pkg_filter"))
        if not out:
            return
        try:
            n = package_project(path, out)
        except Exception as exc:
            QMessageBox.critical(self, tr("manager.export_pkg_title"),
                                 tr("manager.export_pkg_error", err=str(exc)))
            return
        QMessageBox.information(self, tr("manager.export_pkg_title"),
                                tr("manager.export_pkg_done", path=out, n=n))

    def remove_selected(self) -> None:
        path = self.selected_path()
        if not path:
            return
        ans = QMessageBox.question(
            self, tr("manager.remove_title"),
            tr("manager.remove_msg", name=os.path.basename(path)),
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        items = [i for i in load_registry()
                 if os.path.abspath(i["path"]) != os.path.abspath(path)]
        save_registry(items)
        self.refresh()

    def delete_selected(self) -> None:
        path = self.selected_path()
        if not path or not os.path.isdir(path):
            return
        ans = QMessageBox.warning(
            self, tr("manager.delete_title"),
            tr("manager.delete_msg", name=os.path.basename(path)),
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        import shutil
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception as exc:
            QMessageBox.critical(self, tr("manager.delete_title"),
                                 tr("manager.delete_error", err=str(exc)))
            return
        items = [i for i in load_registry()
                 if os.path.abspath(i["path"]) != os.path.abspath(path)]
        save_registry(items)
        self.refresh()

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.setWindowTitle(tr("app.title") + " — " + tr("manager.title"))
        self.title_lbl.setText("<h2 style='margin:0'>" + tr("app.title") + "</h2>")
        self.subtitle_lbl.setText("<span style='color:#9fb3ab'>" +
                                  tr("manager.subtitle") + "</span>")
        self.open_btn.setText(tr("manager.open"))
        self.remove_btn.setText(tr("manager.remove"))
        self.delete_btn.setText(tr("manager.delete"))
        self.new_btn.setText(tr("manager.new"))
        self.import_btn.setText(tr("manager.import"))
        self.import_pkg_btn.setText(tr("manager.new_from_pkg"))
        self.export_pkg_btn.setText(tr("manager.export_pkg"))
        self.refresh_btn.setText(tr("manager.refresh"))
        self.quit_btn.setText(tr("manager.quit"))
        self._on_select(self.list.currentItem(), None)
