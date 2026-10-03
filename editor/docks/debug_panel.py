"""Debug / output panel.

Shows live runtime statistics (FPS, node count, physics bodies) and a log
console.  The editor routes ``print``/``log`` output here during play.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QLabel,
                               QTextEdit, QHBoxLayout)

from editor.i18n import tr


class DebugPanel(QDockWidget):
    def __init__(self, editor, parent=None):
        super().__init__(tr("dock.debug"), parent)
        self.editor = editor
        w = QWidget()
        layout = QVBoxLayout(w)

        stats = QHBoxLayout()
        self.fps_lbl = QLabel(tr("debug.fps_none"))
        self.nodes_lbl = QLabel(tr("debug.nodes_none"))
        self.bodies_lbl = QLabel(tr("debug.bodies_none"))
        stats.addWidget(self.fps_lbl)
        stats.addWidget(self.nodes_lbl)
        stats.addWidget(self.bodies_lbl)
        layout.addLayout(stats)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(self.console)

        self.setWidget(w)

    def update_stats(self, fps: float, nodes: int, bodies: int) -> None:
        self.fps_lbl.setText(tr("debug.fps", v=fps))
        self.nodes_lbl.setText(tr("debug.nodes", v=nodes))
        self.bodies_lbl.setText(tr("debug.bodies", v=bodies))

    def retranslate(self) -> None:
        self.setWindowTitle(tr("dock.debug"))
        self.fps_lbl.setText(tr("debug.fps_none"))
        self.nodes_lbl.setText(tr("debug.nodes_none"))
        self.bodies_lbl.setText(tr("debug.bodies_none"))

    def log(self, msg: str) -> None:
        self.console.append(msg)
