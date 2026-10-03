"""Editor application entry point.

Creates the Qt application and the :class:`Editor` main window.  Usage::

    python run_editor.py [project_directory]

If no project directory is given, the bundled ``example_project`` is opened.
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    # make sure the engine + editor packages are importable
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from PySide6.QtWidgets import QApplication, QMessageBox
    from editor.editor_window import Editor
    from editor.settings import get_setting
    from editor.i18n import set_language, tr
    from editor.theme import apply_theme
    from editor.branding import engine_icon

    # restore the last-used editor preferences before building any UI
    set_language(get_setting("language", "en"))

    app = QApplication(sys.argv)
    app.setApplicationName("Reindeer Engine")
    app.setApplicationDisplayName(tr("app.title"))
    app.setWindowIcon(engine_icon())
    apply_theme(app, get_setting("theme", "dark"))

    if len(sys.argv) > 1:
        # explicit project path on the command line -> open it directly
        project_path = os.path.abspath(sys.argv[1])
        if os.path.exists(project_path) and not os.path.isdir(project_path):
            QMessageBox.critical(
                None, tr("app.title"),
                tr("app.path_not_dir", path=project_path))
            sys.exit(1)
        os.makedirs(project_path, exist_ok=True)
        window = Editor(project_path)
        window.show()
    else:
        # no project given -> show the project manager hub first
        from editor.project_manager import ProjectManager
        window = ProjectManager()
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
