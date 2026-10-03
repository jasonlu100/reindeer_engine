"""Reindeer editor main window.

Glues together the engine runtime, the viewport and the docks in a Godot-like
layout: a central viewport, a Scene tree on the left, an Inspector on the
right, a FileSystem browser on the bottom-left and a Debug panel on the
bottom.  Provides scene open/save and a Play/Stop run loop with live preview.
"""
from __future__ import annotations

import os
import sys
import subprocess

from PySide6.QtWidgets import (QMainWindow, QDockWidget, QMenuBar, QMenu,
                               QToolBar, QPushButton, QMessageBox,
                               QInputDialog, QWidget, QApplication, QStatusBar,
                               QLabel, QLineEdit, QTextEdit, QPlainTextEdit)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from engine.core.engine import Engine
from engine.core.registry import get_registry
from engine.core.scene_format import SceneLoader
from engine.nodes.camera2d import Camera2D
from engine.core.node import Node
from engine.core.math2d import Vector2
from engine import ENGINE_NAME, __version__ as ENGINE_VERSION
from editor.branding import engine_logo

from editor.project import Project
from editor.viewport import Viewport
from editor.docks.scene_tree_dock import SceneTreeDock
from editor.docks.inspector import InspectorDock
from editor.docks.filesystem_dock import FileSystemDock
from editor.docks.debug_panel import DebugPanel
from editor.i18n import (tr, set_language, get_language, available_languages)
from editor.settings import get_setting, set_setting
from editor.theme import apply_theme
from editor.history import (History, AddNodeCommand, DeleteNodeCommand,
                            ReparentCommand, MoveCommand, PropertyCommand)


class Editor(QMainWindow):
    def __init__(self, project_path: str):
        super().__init__()
        self.setWindowTitle(tr("app.title"))
        self.resize(1280, 800)

        self.project = Project(project_path)
        self.project.ensure_dirs()

        try:
            self.engine = Engine(
                headless=False,
                project_dir=self.project.path,
                physics_backend=self.project.config.get("physics_backend",
                                                       "builtin"))
        except Exception as exc:
            # e.g. the project selected the pymunk backend but pymunk is not
            # installed -> fall back to the built-in engine rather than crash.
            self.engine = Engine(headless=False, project_dir=self.project.path,
                                physics_backend="builtin")
            QMessageBox.warning(self, tr("app.title"),
                               tr("physics.backend_missing", err=str(exc)))
        self.engine.project_dir = self.project.path

        self.playing = False
        self.edit_root = None
        self.current_scene_path = ""
        self.selected_node = None
        self.modified = False
        self._edit_fps = 0.0

        # bounded undo / redo history (max 30 operations)
        self.history = History(self, limit=30)
        self.history.on_change = self._update_undo_actions
        self._game_proc = None        # separate-window game process (if running)
        self._backend_actions = {}    # backend menu actions for check state

        # editor camera used for the editing view (pan / zoom)
        self.view_camera = Camera2D("EditorCamera")
        self.view_camera.zoom = 1.0

        self.engine.renderer = None  # set after viewport creation

        self._build_ui()
        self.engine.renderer = self.viewport.renderer
        self.engine.renderer.set_resource_base(self.project.path)

        # open main scene or create a blank one
        if self.project.main_scene and os.path.exists(
                self.project.abs_path(self.project.main_scene)):
            self.open_scene(self.project.main_scene)
        else:
            self.new_scene()

        self.update_debug()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # central viewport
        self.viewport = Viewport(self)
        self.setCentralWidget(self.viewport)

        # docks
        self.scene_tree_dock = SceneTreeDock(self)
        self.inspector_dock = InspectorDock(self)
        self.filesystem_dock = FileSystemDock(self)
        self.debug_panel = DebugPanel(self)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.scene_tree_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.filesystem_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.debug_panel)

        # toolbars / menus
        self._build_menus()
        self._build_toolbar()

        # status bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel(tr("status.ready"))
        self.status_bar.addWidget(self.status_label)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        mb.clear()

        file_menu = mb.addMenu(tr("menu.file"))
        file_menu.addAction(tr("menu.new_scene"), self.new_scene)
        file_menu.addAction(tr("menu.open_scene"), self._open_scene_dialog)
        file_menu.addAction(tr("menu.save_scene"), self.save_scene)
        file_menu.addAction(tr("menu.save_scene_as"), self.save_scene_as)
        file_menu.addSeparator()
        file_menu.addAction(tr("menu.quit"), self.close)

        scene_menu = mb.addMenu(tr("menu.scene"))
        self.play_act = scene_menu.addAction(tr("menu.play"), self.play)
        scene_menu.addAction(tr("menu.stop"), self.stop)
        scene_menu.addAction(tr("menu.set_main"), self._set_main_scene)
        scene_menu.addAction(tr("menu.pygame_run"), self.run_pygame)

        # Edit menu: undo / redo
        edit_menu = mb.addMenu(tr("menu.edit"))
        self.undo_act = edit_menu.addAction(
            tr("menu.undo"), self.history.undo)
        self.redo_act = edit_menu.addAction(
            tr("menu.redo"), self.history.redo)
        self._update_undo_actions()

        settings_menu = mb.addMenu(tr("menu.settings"))
        lang_menu = settings_menu.addMenu(tr("menu.language"))
        for code, label in available_languages():
            act = lang_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(code == get_language())
            act.triggered.connect(
                lambda _checked, c=code: self._set_language(c))
        theme_menu = settings_menu.addMenu(tr("menu.theme"))
        for name, label in [("dark", tr("theme.dark")),
                            ("light", tr("theme.light"))]:
            act = theme_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(name == get_setting("theme", "dark"))
            act.triggered.connect(
                lambda _checked, n=name: self._set_theme(n))

        # 项目设置 lives under 设置 -- per-project window size, physics and run backend
        project_menu = settings_menu.addMenu(tr("menu.project_settings"))
        project_menu.addAction(tr("projset.open"), self._open_project_settings)

        # 运行后端 -- choose pyside6 or pygame as the run target (under 项目设置)
        backend_menu = project_menu.addMenu(tr("menu.run_backend"))
        for code, label in (("pyside6", tr("menu.backend_pyside")),
                            ("pygame", tr("menu.backend_pygame"))):
            act = backend_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(code == self._run_backend())
            act.triggered.connect(
                lambda _checked, c=code: self._set_run_backend(c))
            self._backend_actions[code] = act

        help_menu = mb.addMenu(tr("menu.help"))
        help_menu.addAction(tr("menu.tutorial"), self._open_tutorial)
        help_menu.addAction(tr("menu.about"), self._show_about)

        # 导出 / 打包 -- build a standalone executable from the project
        export_menu = mb.addMenu(tr("menu.export"))
        export_menu.addAction(tr("export.package"), self._open_export)

        # 测试功能入口 -- 明确标注「测试」，避免与正式功能混淆
        test_menu = mb.addMenu(tr("menu.test"))
        test_menu.addAction(tr("ai.open"), self._open_ai_chat)

    def _set_language(self, code: str) -> None:
        set_language(code)
        set_setting("language", code)
        self.retranslate()

    def _set_theme(self, name: str) -> None:
        set_setting("theme", name)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, name)

    def _build_toolbar(self) -> None:
        if getattr(self, "toolbar", None) is None:
            self.toolbar = QToolBar(tr("toolbar.main"), self)
            self.addToolBar(self.toolbar)
        else:
            self.toolbar.clear()
        self.play_btn = QPushButton(tr("tb.play"))
        self.stop_btn = QPushButton(tr("tb.stop"))
        self.save_btn = QPushButton(tr("tb.save"))
        self.undo_btn = QPushButton(tr("tb.undo"))
        self.redo_btn = QPushButton(tr("tb.redo"))
        self.pygame_btn = QPushButton(tr("tb.pygame"))
        self.play_btn.clicked.connect(self.play)
        self.stop_btn.clicked.connect(self.stop)
        self.save_btn.clicked.connect(self.save_scene)
        self.undo_btn.clicked.connect(self.history.undo)
        self.redo_btn.clicked.connect(self.history.redo)
        self.pygame_btn.clicked.connect(self.run_pygame)
        self.toolbar.addWidget(self.play_btn)
        self.toolbar.addWidget(self.stop_btn)
        self.toolbar.addWidget(self.save_btn)
        self.toolbar.addWidget(self.undo_btn)
        self.toolbar.addWidget(self.redo_btn)
        self.toolbar.addWidget(self.pygame_btn)

    # ------------------------------------------------------------------
    # rendering helpers
    # ------------------------------------------------------------------
    def get_render_root(self):
        if self.playing:
            return self.engine.tree.root
        return self.edit_root

    def get_camera(self):
        if self.playing:
            cam = self.engine.tree.find_camera()
            if cam is not None:
                return cam
        return self.view_camera

    # ------------------------------------------------------------------
    # scene operations
    # ------------------------------------------------------------------
    def new_scene(self) -> None:
        self.stop()
        self.edit_root = get_registry().create("Node2D", "Main")
        # a freshly created scene is not yet saved; leave the path empty so the
        # first save prompts "Save As" instead of silently overwriting main scene
        self.current_scene_path = ""
        self.selected_node = None
        self.modified = False
        self.history.clear()
        self._refresh_all()
        self._update_title()

    def open_scene(self, rel_path: str) -> None:
        self.stop()
        full = self.project.abs_path(rel_path)
        loader = SceneLoader(None)  # edit mode: do NOT run scripts
        self.edit_root = loader.load(full)
        self.current_scene_path = rel_path
        self.selected_node = None
        self.modified = False
        self.history.clear()
        self._refresh_all()
        self._update_title()

    def _open_scene_dialog(self) -> None:
        scenes = self.project.scan_scenes()
        if not scenes:
            QMessageBox.information(self, tr("open.title"),
                                    tr("open.none"))
            return
        item, ok = QInputDialog.getItem(self, tr("open.title"),
                                       tr("open.choose"), scenes, 0, False)
        if ok and item:
            self.open_scene(item)

    def save_scene(self) -> bool:
        """Persist the current scene. Returns ``True`` if it was actually saved
        (``False`` when the user cancels the *Save As* prompt)."""
        if not self.current_scene_path:
            return self.save_scene_as()
        self._save_to(self.current_scene_path)
        self.modified = False
        self._update_title()
        return True

    def _sanitize_scene_name(self, name: str) -> str:
        """Turn user input into a safe ``scenes/<name>.reindeer.tscn`` path.

        Strips directory separators and any accidental extension so the file is
        always written inside the project's ``scenes/`` folder."""
        name = (name or "").strip()
        name = os.path.basename(name)
        name = name.replace("\\", "").replace("/", "")
        if name.endswith(".reindeer.tscn"):
            name = name[: -len(".reindeer.tscn")]
        name = name.strip()
        if not name:
            return ""
        return f"scenes/{name}.reindeer.tscn"

    def save_scene_as(self) -> bool:
        name, ok = QInputDialog.getText(self, tr("saveas.title"),
                                       tr("saveas.msg"),
                                       text="main")
        if not (ok and name):
            return False
        rel = self._sanitize_scene_name(name)
        if not rel:
            return False
        self.current_scene_path = rel
        self._save_to(rel)
        self.modified = False
        self.filesystem_dock.refresh()
        self._update_title()
        return True

    def _save_to(self, rel: str) -> None:
        full = self.project.abs_path(rel)
        loader = SceneLoader(self.engine)
        loader.save(self.edit_root, full)
        # Verify the write round-trips faithfully.  This catches any (future or
        # hypothetical) silent data-loss in the save path immediately, instead of
        # letting edits "disappear" on the next project open.
        if not loader.verify_file(full, self.engine):
            QMessageBox.warning(
                self, tr("app.title"),
                tr("save.verify_fail", path=rel))

    def _set_main_scene(self) -> None:
        if not self.current_scene_path:
            self.save_scene_as()
        self.project.main_scene = self.current_scene_path
        self.project.save_config()
        QMessageBox.information(self, tr("mainscene.title"),
                                tr("mainscene.msg",
                                   path=self.current_scene_path))

    # ------------------------------------------------------------------
    # history-aware operations
    # ------------------------------------------------------------------
    def _apply_command(self, cmd) -> None:
        """Apply *cmd* (performing its mutation) and record it in history."""
        cmd.redo()
        self.history.push(cmd)
        self._after_history()

    def create_node(self, type_name: str, parent_node: Node = None) -> None:
        cls = get_registry().get(type_name)
        if cls is None:
            return
        node = cls()
        parent = parent_node or self.edit_root
        if parent is None:
            # blank document with no root yet - just adopt the node as root
            self.edit_root = node
            self._after_history()
            self.select_node(node)
            return
        self._apply_command(AddNodeCommand(self, node, parent, None))
        self.select_node(node)

    def delete_node(self, node: Node) -> None:
        if node is None or node is self.edit_root:
            return
        parent = node.parent
        if parent is None:
            return
        index = parent.children.index(node)
        before = (parent.children[index + 1]
                  if index + 1 < len(parent.children) else None)
        self._apply_command(DeleteNodeCommand(self, node, parent, before))

    def delete_selected(self) -> None:
        if self.selected_node is not None:
            self.delete_node(self.selected_node)

    def duplicate_node(self, node: Node) -> None:
        if node is None or node is self.edit_root or node.parent is None:
            return
        parent = node.parent
        loader = SceneLoader(self.engine)
        new_node = loader._build(node.serialize())
        new_node.script_path = getattr(node, "script_path", "") or ""
        new_node.name = self._unique_name(node.name, parent)
        index = parent.children.index(node)
        before = (parent.children[index + 1]
                  if index + 1 < len(parent.children) else None)
        self._apply_command(AddNodeCommand(self, new_node, parent, before))
        self.select_node(new_node)

    def _unique_name(self, base: str, parent: Node) -> str:
        existing = {c.name for c in parent.children}
        if base not in existing:
            return base
        i = 2
        while f"{base}_{i}" in existing:
            i += 1
        return f"{base}_{i}"

    def reparent_node(self, src: Node, tgt: Node) -> None:
        if src is None or src.parent is None or src is tgt:
            return
        old_parent = src.parent
        old_index = old_parent.children.index(src)
        old_before = (old_parent.children[old_index + 1]
                      if old_index + 1 < len(old_parent.children) else None)
        new_before = None  # appended to the target subtree
        self._apply_command(ReparentCommand(
            self, src, old_parent, old_before, tgt, new_before))

    def commit_node_move(self, node, old_pos, new_pos) -> None:
        """Record a completed drag as a single undoable move operation."""
        if old_pos == new_pos:
            return
        self._apply_command(MoveCommand(self, node, old_pos, new_pos))

    def push_property_change(self, node, name, old_val, new_val) -> None:
        """Record an inspector / rename / script property edit (no live UI
        refresh - the widget already reflects the new value)."""
        if old_val == new_val:
            return
        self.history.push(PropertyCommand(self, node, name, old_val, new_val))
        self.modified = True
        self._update_title()
        self.viewport.update()

    # ------------------------------------------------------------------
    # low-level mutation helpers (used by history commands)
    # ------------------------------------------------------------------
    def _add_node_before(self, node, parent, before) -> None:
        if parent is None:
            return
        if node.parent is not None:
            node.parent.remove_child(node)
        node.parent = parent
        # insert before the given sibling, or append if it is missing/None
        if before is not None and before in parent.children:
            idx = parent.children.index(before)
            parent.children.insert(idx, node)
        else:
            parent.children.append(node)

    def _remove_node(self, node) -> None:
        if node.parent is not None:
            node.parent.remove_child(node)

    def _set_node_local_position(self, node, pos) -> None:
        node.position = Vector2(pos.x, pos.y)
        self.viewport.update()

    def _set_property(self, node, name, value) -> None:
        node.set_property(name, value)
        if self.selected_node is node:
            self.inspector_dock.inspect(node)
        self.viewport.update()

    def _node_in_tree(self, node, root) -> bool:
        if node is root:
            return True
        for c in root.children:
            if self._node_in_tree(node, c):
                return True
        return False

    def _validate_selection(self) -> None:
        node = self.selected_node
        if node is not None and (self.edit_root is None
                                or not self._node_in_tree(node, self.edit_root)):
            self.selected_node = None
            self.inspector_dock.inspect(None)

    def _after_history(self) -> None:
        self._validate_selection()
        self.modified = True
        self._update_title()
        self._refresh_all()

    def _update_undo_actions(self) -> None:
        if hasattr(self, "undo_act"):
            self.undo_act.setEnabled(self.history.can_undo())
            self.undo_act.setText(
                tr("menu.undo") + (f" ({self.history.undo_label()})"
                                   if self.history.can_undo() else ""))
        if hasattr(self, "redo_act"):
            self.redo_act.setEnabled(self.history.can_redo())
            self.redo_act.setText(
                tr("menu.redo") + (f" ({self.history.redo_label()})"
                                   if self.history.can_redo() else ""))

    # ------------------------------------------------------------------
    def select_node(self, node, from_tree: bool = False) -> None:
        self.selected_node = node
        self.inspector_dock.inspect(node)
        if not from_tree:
            # highlight in the tree
            self.scene_tree_dock.refresh(self.selected_node)

    def on_scene_modified(self) -> None:
        self.modified = True
        self._update_title()

    def on_node_moved(self, node) -> None:
        self.modified = True

    def preview_step(self, delta: float) -> None:
        """Run lightweight node callbacks in edit mode so the viewport shows a
        live preview (particles animate, tweens play, timers tick).  Scripts are
        not attached in edit mode, so only built-in behaviour runs."""
        root = self.edit_root
        if root is None:
            return

        def walk(n):
            for fn_name in ("_process", "_physics_process"):
                fn = getattr(n, fn_name, None)
                if fn is not None:
                    try:
                        fn(delta)
                    except Exception:
                        import traceback
                        traceback.print_exc()
            for c in n.children:
                walk(c)

        walk(root)

    # ------------------------------------------------------------------
    # run / stop
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def play(self) -> None:
        """Run the project in a separate window using the selected backend."""
        self.run_game(self._run_backend())

    def run_game(self, backend: str) -> None:
        """Save the current scene and launch it in a separate window using the
        given backend (``pyside6`` or ``pygame``).  The window runs in its own
        process, fully detached from the editor."""
        if backend == "pygame":
            try:
                import pygame  # noqa: F401
            except Exception:
                QMessageBox.information(self, tr("pygame.title"),
                                       tr("pygame.missing"))
                return
        if not self.current_scene_path:
            # the user may cancel the Save As prompt -> abort the run
            if not self.save_scene_as():
                return
        else:
            self._save_to(self.current_scene_path)
        # pass the scene path *relative* to the project; the runtime joins it with
        # the project directory (robust regardless of OS path separators).
        scene_rel = self.current_scene_path
        runner_dir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "engine", "runtime"))
        runner = os.path.join(runner_dir,
                              "qt_app.py" if backend in ("qt", "pyside6")
                              else "pygame_app.py")
        cmd = [sys.executable, runner, scene_rel, "--project", self.project.path]
        wsize = self.project.config.get("window_size")
        if isinstance(wsize, (list, tuple)) and len(wsize) == 2:
            cmd += ["--width", str(int(wsize[0])),
                    "--height", str(int(wsize[1]))]
        try:
            self._game_proc = subprocess.Popen(cmd)
        except Exception as exc:
            QMessageBox.warning(self, tr("pygame.title"),
                                tr("pygame.launch_failed", err=str(exc)))

    def run_pygame(self) -> None:
        """Shortcut: run the project with the pygame backend."""
        self.run_game("pygame")

    def stop(self) -> None:
        """Terminate the separate-window game process if it is still running."""
        proc = getattr(self, "_game_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self._game_proc = None

    # ------------------------------------------------------------------
    def _run_backend(self) -> str:
        return self.project.config.get("run_backend", "pyside6")

    def _set_run_backend(self, code: str) -> None:
        self.project.config["run_backend"] = code
        self.project.save_config()
        for c, act in getattr(self, "_backend_actions", {}).items():
            act.setChecked(c == code)

    def _open_project_settings(self) -> None:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QComboBox, QDialogButtonBox,
                                       QGroupBox)
        from editor.dialogs.input_map_dialog import InputMapEditor

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("projset.title"))
        dlg.setMinimumWidth(540)
        root = QVBoxLayout(dlg)

        # ---- window / backend group ----
        grp_win = QGroupBox(tr("projset.group_window"))
        form = QFormLayout(grp_win)
        ws = self.project.config.get("window_size")
        w0 = ws[0] if isinstance(ws, (list, tuple)) and len(ws) == 2 else 960
        h0 = ws[1] if isinstance(ws, (list, tuple)) and len(ws) == 2 else 540
        w_edit = QLineEdit(str(w0))
        h_edit = QLineEdit(str(h0))
        be_box = QComboBox()
        be_box.addItems([tr("menu.backend_pyside"), tr("menu.backend_pygame")])
        be_box.setCurrentIndex(0 if self._run_backend() == "pyside6" else 1)
        phys_box = QComboBox()
        phys_box.addItems(["builtin", "pymunk"])
        phys_box.setCurrentIndex(
            0 if self.project.config.get("physics_backend", "builtin") == "builtin" else 1)
        form.addRow(tr("projset.width"), w_edit)
        form.addRow(tr("projset.height"), h_edit)
        form.addRow(tr("projset.backend"), be_box)
        form.addRow(tr("projset.physics"), phys_box)
        root.addWidget(grp_win)

        # ---- input map group ----
        grp_input = QGroupBox(tr("inputmap.group"))
        input_layout = QVBoxLayout(grp_input)
        input_editor = InputMapEditor(
            self.project.config.get("input_map", {}))
        input_layout.addWidget(input_editor)
        root.addWidget(grp_input)

        # ---- buttons ----
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        if dlg.exec() == QDialog.Accepted:
            try:
                w = int(w_edit.text()); h = int(h_edit.text())
            except ValueError:
                w, h = 960, 540
            self.project.config["window_size"] = [w, h]
            self.project.config["run_backend"] = ("pyside6"
                                                 if be_box.currentIndex() == 0
                                                 else "pygame")
            self.project.config["physics_backend"] = (
                "builtin" if phys_box.currentIndex() == 0 else "pymunk")
            # custom input map edited in the widget
            self.project.config["input_map"] = input_editor.get_map()
            self.project.save_config()
            # re-apply the new input map to the live preview engine immediately
            if getattr(self, "engine", None) is not None:
                self.engine.input.apply_input_map(
                    self.project.config["input_map"], merge=True)
            QMessageBox.information(self, tr("projset.title"),
                                   tr("inputmap.saved"))

    # (run_pygame is implemented via run_game() in the play section above)

    # ------------------------------------------------------------------
    def _open_export(self) -> None:
        """Open the packaging dialog to build a standalone executable."""
        from editor.dialogs.export_dialog import ExportDialog
        dlg = ExportDialog(self.project, self)
        dlg.exec()

    def _open_ai_chat(self) -> None:
        """打开 AI 对话窗口（测试功能）。"""
        from editor.dialogs.ai_chat_dialog import AIChatDialog
        dlg = AIChatDialog(self, self)
        dlg.show()  # 非模态：可同时保持编辑器可见

    # (run_pygame is implemented via run_game() in the play section above)

    # ------------------------------------------------------------------
    def update_debug(self) -> None:
        if self.playing:
            fps = self.engine.time.fps if hasattr(self.engine, "time") else 0
            nodes = self.engine.tree.get_node_count()
            bodies = len(self.engine.physics.bodies)
        else:
            # edit mode: show the scene being edited and the editor's own FPS
            fps = getattr(self, "_edit_fps", 0.0)
            nodes = self._count_nodes(self.edit_root)
            bodies = 0
        self.debug_panel.update_stats(fps, nodes, bodies)
        if getattr(self, "status_label", None) is not None:
            fps_text = tr("debug.fps", v=f"{fps:.0f}")
            nodes_text = tr("status.nodes", count=nodes)
            self.status_label.setText(f"{fps_text}  ·  {nodes_text}")

    @staticmethod
    def _count_nodes(root) -> int:
        if root is None:
            return 0
        n = 1
        for c in root.children:
            n += Editor._count_nodes(c)
        return n

    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self.scene_tree_dock.refresh(self.selected_node)
        self.inspector_dock.inspect(self.selected_node)
        self.filesystem_dock.refresh()
        self.viewport.update()

    def _update_title(self) -> None:
        star = "*" if self.modified else ""
        path = self.current_scene_path or "unsaved"
        self.setWindowTitle(f"{tr('app.title')} — {self.project.name}/{path}{star}")

    def _open_tutorial(self) -> None:
        """Open the bundled web tutorial (``web_doc/index.html``) in the
        system's default browser."""
        base = os.path.dirname(os.path.abspath(__file__))  # editor/
        html = os.path.abspath(os.path.join(base, "..", "web_doc", "index.html"))
        if not os.path.isfile(html):
            QMessageBox.warning(
                self, tr("tutorial.title"),
                tr("tutorial.missing", path=html))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(html))

    def _show_about(self) -> None:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                       QLabel, QDialogButtonBox)
        from PySide6.QtGui import QPixmap
        from engine import ENGINE_TAGLINE
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("about.title"))
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(engine_logo(96))
        top.addWidget(logo)
        info = QVBoxLayout()
        name = QLabel(f"<h2>{ENGINE_NAME}</h2>")
        tag = QLabel(ENGINE_TAGLINE)
        tag.setWordWrap(True)
        ver = QLabel(tr("about.version", v=ENGINE_VERSION))
        info.addWidget(name)
        info.addWidget(tag)
        info.addWidget(ver)
        top.addLayout(info)
        layout.addLayout(top)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

    def retranslate(self) -> None:
        """Re-apply all static UI text after a language change."""
        self.menuBar().clear()
        self._build_menus()
        self._build_toolbar()
        self.scene_tree_dock.retranslate()
        self.inspector_dock.retranslate()
        self.filesystem_dock.retranslate()
        self.debug_panel.retranslate()
        if getattr(self, "status_label", None) is not None:
            self.status_label.setText(tr("status.ready"))
        self._update_title()
        # refresh dock contents so translated labels are picked up
        self.scene_tree_dock.refresh(self.selected_node)
        self.inspector_dock.inspect(self.selected_node)

    # ------------------------------------------------------------------
    # keyboard shortcuts: undo / redo
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        # let text-editing widgets keep their native undo/redo (e.g. typing in a
        # line edit or the script path field); only intercept globally otherwise
        fw = self.focusWidget()
        if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return
        if event.modifiers() & Qt.ControlModifier:
            key = event.key()
            if key == Qt.Key_Z and not (event.modifiers() & Qt.ShiftModifier):
                if self.history.can_undo():
                    self.history.undo()
                    event.accept()
                    return
            elif key == Qt.Key_Z and (event.modifiers() & Qt.ShiftModifier):
                if self.history.can_redo():
                    self.history.redo()
                    event.accept()
                    return
            elif key == Qt.Key_Y:
                if self.history.can_redo():
                    self.history.redo()
                    event.accept()
                    return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if self.modified:
            ans = QMessageBox.question(
                self, tr("unsaved.title"),
                tr("unsaved.msg"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                event.ignore()
                return
            if ans == QMessageBox.Yes:
                # if the save is cancelled (e.g. Save As dialog dismissed) we must
                # not close the window, otherwise unsaved work is lost
                if not self.save_scene():
                    event.ignore()
                    return
        super().closeEvent(event)
