"""Standalone PySide6 game window.

Runs a fully detached window (its own :class:`QApplication` when launched in a
separate process) that drives the shared :func:`Engine.step` frame loop and
renders with the Qt :class:`~engine.rendering.Renderer2D`.  This is the PySide6
counterpart of :mod:`engine.runtime.pygame_app` and shares the exact same
engine, scene and scripting runtime -- only the surface/backend differs, which
is why the editor preview and the released build look identical.
"""
from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter


class QtGameWindow(QWidget):
    """A top-level window that renders one Engine instance with Renderer2D."""

    def __init__(self, engine, width: int = 960, height: int = 540,
                 title: str = "Reindeer (PySide6)"):
        super().__init__()
        self.engine = engine
        self.resize(width, height)
        self.setWindowTitle(title)
        self.renderer = engine.renderer
        if self.renderer is not None:
            self.renderer.set_resource_base(engine.project_dir or "")

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        try:
            self.engine.step()
        except Exception:
            traceback.print_exc()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            cam = self.engine.tree.find_camera()
            if self.renderer is not None:
                self.renderer.begin(painter, self.width(), self.height(), cam)
                self.renderer.render(self.engine.tree)
                self.renderer.end()
        except Exception:
            traceback.print_exc()
        finally:
            painter.end()

    # ------------------------------------------------------------------
    # input forwarding
    # ------------------------------------------------------------------
    @staticmethod
    def _kname(event) -> str:
        try:
            return Qt.Key(event.key()).name
        except Exception:
            return ""

    def keyPressEvent(self, event) -> None:
        name = self._kname(event)
        if name:
            self.engine.input.on_key_down(name)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        name = self._kname(event)
        if name:
            self.engine.input.on_key_up(name)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event) -> None:
        self.engine.input.on_mouse_down(event.button().value,
                                        event.x(), event.y())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.engine.input.on_mouse_up(event.button().value,
                                      event.x(), event.y())
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self.engine.input.on_mouse_move(event.x(), event.y())
        super().mouseMoveEvent(event)


def run(engine, width: int = 960, height: int = 540,
        title: str = "Reindeer (PySide6)") -> int:
    """Create the QApplication (if needed) and run the game window to completion."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = QtGameWindow(engine, width, height, title)
    win.show()
    return app.exec()
