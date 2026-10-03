"""Editor viewport.

A ``QWidget`` that renders the active scene with :class:`Renderer2D` and
forwards mouse / keyboard input into the engine.  It supports node selection,
dragging, camera pan & zoom, and switches between *edit* and *play* modes
(which the editor toggles).
"""
from __future__ import annotations

import math
import time

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import (QPainter, QPen, QColor, QMouseEvent, QWheelEvent,
                           QPolygonF, QFont)

from engine.rendering import Renderer2D
from engine.core.math2d import Vector2
from engine.nodes.node2d import Node2D
from editor.branding import engine_logo


class Viewport(QWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.renderer = Renderer2D(editor.project.path)
        self.timer = QTimer(self)
        self.timer.setInterval(16)  # ~60fps
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self._panning = False
        self._pan_last = None
        self._drag_node = None
        self._drag_axis = None      # None = free drag, "x"/"y" = gizmo axis drag
        self._drag_offset = Vector2(0, 0)
        self._drag_start_pos = None  # local position captured at drag start
        self._last_mouse = Vector2(0, 0)
        self._gizmo_len = 48.0      # screen-space length of the X / Y handles

        # FPS measurement for the debug panel (updated ~2x per second)
        self._fps_frames = 0
        self._fps_last = time.perf_counter()
        self._fps = 60.0

    # ------------------------------------------------------------------
    def _on_tick(self) -> None:
        if self.editor.playing:
            self.editor.engine.step()
            self.editor.update_debug()
        else:
            # edit-mode live preview: let nodes animate (particles, tweens, ...)
            self.editor.preview_step(1.0 / 60.0)
            # refresh the debug panel / status bar at a relaxed cadence so the
            # node count and FPS stay current without thrashing the UI
            now = time.perf_counter()
            self._fps_frames += 1
            if now - self._fps_last >= 0.5:
                self._fps = self._fps_frames / (now - self._fps_last)
                self._fps_frames = 0
                self._fps_last = now
                self.editor._edit_fps = self._fps
                self.editor.update_debug()
        self.update()  # trigger paint

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            root = self.editor.get_render_root()
            camera = self.editor.get_camera()
            self.renderer.begin(painter, self.width(), self.height(), camera)
            try:
                if not self.editor.playing:
                    self._draw_grid(painter, camera)
                if root is not None:
                    self.renderer.render_root(root)
                if not self.editor.playing:
                    if self.editor.selected_node is not None:
                        self._draw_selection(painter, camera,
                                             self.editor.selected_node)
                        self._draw_gizmo(painter, camera,
                                         self.editor.selected_node)
                    self._draw_watermark(painter)
            finally:
                self.renderer.end()
        finally:
            painter.end()

    def _draw_grid(self, painter, camera) -> None:
        from engine.core.math2d import Vector2 as V
        step = 32.0
        w, h = self.width(), self.height()
        pen = QPen(QColor(255, 255, 255, 25))
        painter.setPen(pen)
        # vertical
        left = camera.screen_to_world(V(0, 0), w, h)
        right = camera.screen_to_world(V(w, h), w, h)
        start_x = math.floor(left.x / step) * step
        x = start_x
        while x < right.x:
            s = camera.world_to_screen(V(x, 0), w, h)
            painter.drawLine(int(s.x), 0, int(s.x), h)
            x += step
        top = camera.screen_to_world(V(0, 0), w, h)
        bottom = camera.screen_to_world(V(w, h), w, h)
        start_y = math.floor(top.y / step) * step
        y = start_y
        while y < bottom.y:
            s = camera.world_to_screen(V(0, y), w, h)
            painter.drawLine(0, int(s.y), w, int(s.y))
            y += step

    def _draw_selection(self, painter, camera, node) -> None:
        gp = node.get_global_position() if hasattr(node, "get_global_position") \
            else Vector2(0, 0)
        size = self._node_pick_size(node)
        s = camera.world_to_screen(gp, self.width(), self.height())
        z = camera.zoom
        painter.setPen(QPen(QColor(90, 160, 255), 1.5))
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(int(s.x - size.x * z / 2), int(s.y - size.y * z / 2),
                         int(size.x * z), int(size.y * z))

    def _node_pick_size(self, node) -> Vector2:
        # sprites: use the (possibly loaded) texture size for accurate picking
        ts = getattr(node, "get_texture_size", None)
        if callable(ts):
            size = node.get_texture_size()
            if size.x > 0 and size.y > 0:
                return size
        if hasattr(node, "width") and hasattr(node, "height"):
            return Vector2(getattr(node, "width", 32), getattr(node, "height", 32))
        return Vector2(32, 32)

    # ------------------------------------------------------------------
    # move gizmo (X / Y handles) + branding watermark
    # ------------------------------------------------------------------
    def _gizmo_geometry(self, camera, node):
        gp = node.get_global_position() if hasattr(node, "get_global_position") \
            else Vector2(0, 0)
        c = camera.world_to_screen(gp, self.width(), self.height())
        cx, cy = c.x, c.y
        L = self._gizmo_len
        x_tip = QPointF(cx + L, cy)        # X axis handle (points right)
        y_tip = QPointF(cx, cy - L)        # Y axis handle (points up)
        return (cx, cy, x_tip, y_tip, L)

    @staticmethod
    def _dist_to_segment(px, py, x1, y1, x2, y2) -> float:
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def _hit_gizmo(self, camera, node, sx, sy):
        geo = self._gizmo_geometry(camera, node)
        if geo is None:
            return None
        cx, cy, x_tip, y_tip, L = geo
        if self._dist_to_segment(sx, sy, cx, cy, x_tip.x(), x_tip.y()) <= 9:
            return "x"
        if self._dist_to_segment(sx, sy, cx, cy, y_tip.x(), y_tip.y()) <= 9:
            return "y"
        return None

    def _draw_arrow(self, painter, x1, y1, x2, y2, color) -> None:
        pen = QPen(color, 2.5)
        painter.setPen(pen)
        painter.setBrush(color)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        # arrow head
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 10.0
        a1 = angle - math.pi / 7
        a2 = angle + math.pi / 7
        p1 = QPointF(x2 - size * math.cos(a1), y2 - size * math.sin(a1))
        p2 = QPointF(x2 - size * math.cos(a2), y2 - size * math.sin(a2))
        painter.drawPolygon(QPolygonF([QPointF(x2, y2), p1, p2]))

    def _draw_gizmo(self, painter, camera, node) -> None:
        geo = self._gizmo_geometry(camera, node)
        if geo is None:
            return
        cx, cy, x_tip, y_tip, L = geo
        self._draw_arrow(painter, cx, cy, x_tip.x(), x_tip.y(),
                         QColor(255, 90, 90))      # X -> red
        self._draw_arrow(painter, cx, cy, y_tip.x(), y_tip.y(),
                         QColor(84, 214, 106))     # Y -> green
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 4, 4)

    def _draw_watermark(self, painter) -> None:
        pix = engine_logo(28)
        text = "Reindeer Engine"
        painter.setFont(QFont("SansSerif", 10))
        tw = painter.fontMetrics().horizontalAdvance(text)
        total = pix.width() + 8 + tw
        x = self.width() - total - 12
        y = self.height() - pix.height() - 12
        painter.drawPixmap(int(x), int(y), pix)
        painter.setPen(QColor(255, 255, 255, 150))
        painter.drawText(int(x + pix.width() + 8), int(y + pix.height() - 4),
                         text)

    def _world_to_local(self, node, world):
        """Convert a world position to ``node``'s local position, accounting for
        the parent's global transform (position / rotation / scale)."""
        parent = node.parent
        if parent is None or not isinstance(parent, Node2D):
            return world
        ppos, prot, pscale = parent._global_xform()
        d = world - ppos
        d = d.rotated(-prot)
        lx = d.x / pscale.x if pscale.x else d.x
        ly = d.y / pscale.y if pscale.y else d.y
        return Vector2(lx, ly)

    # ------------------------------------------------------------------
    def screen_to_world(self, sx: float, sy: float) -> Vector2:
        cam = self.editor.get_camera()
        return cam.screen_to_world(Vector2(sx, sy), self.width(), self.height())

    def pick_node(self, world: Vector2, node=None):
        root = self.editor.get_render_root()
        if root is None:
            return None
        found = [None]

        def walk(n):
            # visit children first so top-most (later drawn) wins
            for c in n.children:
                walk(c)
            if found[0] is not None:
                return
            if not getattr(n, "visible", True):
                return
            gp = n.get_global_position() if hasattr(n, "get_global_position") \
                else Vector2(0, 0)
            size = self._node_pick_size(n)
            half = size * 0.5
            if (gp.x - half.x <= world.x <= gp.x + half.x and
                    gp.y - half.y <= world.y <= gp.y + half.y):
                found[0] = n
        walk(root)
        return found[0]

    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_last = event.pos()
            return
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = None
            # 1) if a node is already selected, test its move-gizmo handles
            #    first so the X / Y arrows take priority over re-picking.
            if not self.editor.playing and self.editor.selected_node is not None:
                cam = self.editor.get_camera()
                axis = self._hit_gizmo(cam, self.editor.selected_node,
                                       event.x(), event.y())
                if axis is not None:
                    node = self.editor.selected_node
                    world = self.screen_to_world(event.x(), event.y())
                    gp = node.get_global_position()
                    self._drag_node = node
                    self._drag_axis = axis
                    self._drag_offset = gp - world
                    self._drag_start_pos = Vector2(node.position.x,
                                                  node.position.y)
                    return
            # 2) otherwise pick whatever is under the cursor and select it
            world = self.screen_to_world(event.x(), event.y())
            node = self.pick_node(world)
            self.editor.select_node(node)
            self._drag_node = node
            self._drag_axis = None
            if node is not None:
                gp = node.get_global_position()
                self._drag_offset = gp - world
                self._drag_start_pos = Vector2(node.position.x,
                                              node.position.y)
        # feed to engine when playing
        if self.editor.playing:
            self.editor.engine.input.on_mouse_down(
                event.button().value, event.x(), event.y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._last_mouse = Vector2(event.x(), event.y())
        if self._panning and self._pan_last is not None:
            dx = event.x() - self._pan_last.x()
            dy = event.y() - self._pan_last.y()
            cam = self.editor.get_camera()
            cam.offset = cam.offset - Vector2(dx / cam.zoom, dy / cam.zoom)
            self._pan_last = event.pos()
            return
        if self._drag_node is not None and not self.editor.playing:
            world = self.screen_to_world(event.x(), event.y())
            target = world + self._drag_offset
            local = self._world_to_local(self._drag_node, target)
            node = self._drag_node
            if self._drag_axis == "x":
                node.position = Vector2(local.x, node.position.y)
            elif self._drag_axis == "y":
                node.position = Vector2(node.position.x, local.y)
            else:
                node.position = Vector2(local.x, local.y)
            self.editor.on_node_moved(node)
        if self.editor.playing:
            self.editor.engine.input.on_mouse_move(event.x(), event.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_last = None
        if event.button() == Qt.LeftButton:
            if self._drag_node is not None and self._drag_start_pos is not None:
                node = self._drag_node
                self.editor.commit_node_move(
                    node, self._drag_start_pos,
                    Vector2(node.position.x, node.position.y))
            self._drag_node = None
            self._drag_axis = None
            self._drag_start_pos = None
        if self.editor.playing:
            self.editor.engine.input.on_mouse_up(
                event.button().value, event.x(), event.y())

    def wheelEvent(self, event: QWheelEvent) -> None:
        cam = self.editor.get_camera()
        factor = 1.1 if event.angleDelta().y() > 0 else 1.0 / 1.1
        cam.zoom = max(0.05, min(8.0, cam.zoom * factor))

    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        if self.editor.playing:
            try:
                name = Qt.Key(event.key()).name
            except Exception:
                name = ""
            if name:
                self.editor.engine.input.on_key_down(name)
        else:
            # editor shortcuts
            if event.key() == Qt.Key_Delete:
                self.editor.delete_selected()
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if self.editor.playing:
            try:
                name = Qt.Key(event.key()).name
            except Exception:
                name = ""
            if name:
                self.editor.engine.input.on_key_up(name)
        else:
            super().keyReleaseEvent(event)
