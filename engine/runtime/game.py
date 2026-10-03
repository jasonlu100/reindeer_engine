"""Reusable engine runtime (the foundation for running a project).

This module owns the logic that *runs* a Reindeer project outside the editor.
Both the standalone pygame window (:mod:`engine.runtime.pygame_app`) and the
future packaged executable drive the simulation through
:class:`GameRuntime`: it builds an :class:`~engine.core.engine.Engine`, loads
the project's main scene and runs the shared :func:`Engine.step` frame loop
while feeding input and rendering with a chosen backend.

The only backend shipped today is ``"pygame"`` -- which is also the renderer
the packaged game uses.  Adding another backend means implementing the same
small draw-surface contract that
:class:`engine.rendering.pygame_renderer.PygameRenderer` already satisfies and
selecting it here.
"""
from __future__ import annotations

import json
import os
import sys


def _qt_key_name(pygame_key: int) -> str:
    """Map a pygame key constant to the Qt-style name the InputManager uses."""
    import pygame
    name = pygame.key.name(pygame_key)
    return "Key_" + name.replace(" ", "").capitalize()


class GameRuntime:
    """Owns an :class:`Engine` plus a render backend and runs the game loop.

    Parameters
    ----------
    project_dir:
        Root of the game project (contains ``project.reindeer`` and the scene /
        script / sprite folders).
    main_scene:
        Scene file relative to ``project_dir``.  If omitted, the project's
        configured ``main_scene`` is used (or the first ``.reindeer.tscn``).
    width, height, title:
        Initial window geometry / caption (used by GUI backends).
    backend:
        Renderer backend name.  Only ``"pygame"`` is implemented currently.
    """

    def __init__(self, project_dir: str, main_scene: str = "",
                 width: int = 960, height: int = 540, title: str = "Reindeer",
                 backend: str = None):
        self.project_dir = os.path.abspath(project_dir)
        self.width = width
        self.height = height
        self.title = title
        self._config = self._load_config()
        # honour the project's configured run_backend unless explicitly overridden
        self.backend = backend or self._config.get("run_backend", "pygame")

        # resolve the main scene (explicit > project config > first on disk)
        if not main_scene:
            main_scene = self._config.get("main_scene", "")
        if not main_scene:
            main_scene = self._discover_first_scene()
        if not main_scene:
            raise FileNotFoundError(
                f"No scene to run in project {self.project_dir}")
        self.main_scene = main_scene

        # project config may override the window geometry
        wsize = self._config.get("window_size")
        if isinstance(wsize, (list, tuple)) and len(wsize) == 2:
            self.width, self.height = int(wsize[0]), int(wsize[1])

        # build the engine + the chosen render backend
        from engine.core.engine import Engine
        self.engine = Engine(
            headless=True,
            project_dir=self.project_dir,
            physics_backend=self._config.get("physics_backend", "builtin"))
        # the engine already applied the project input map from disk, but assert
        # it here from the resolved config so a hand-built runtime is consistent.
        self.engine.input.apply_input_map(
            self._config.get("input_map", {}), merge=True)
        self.renderer = self._make_renderer(self.backend)
        self.engine.renderer = self.renderer

        scene_path = os.path.join(self.project_dir, self.main_scene)
        self.engine.load_scene(scene_path)

    # ------------------------------------------------------------------
    # configuration / scene resolution
    # ------------------------------------------------------------------
    def _load_config(self) -> dict:
        from engine.core.project_config import load_project_config
        # repair_on_disk=True heals an out-of-date project file in place (the
        # write is silently skipped when the media is read-only, e.g. packaged).
        return load_project_config(self.project_dir, repair_on_disk=True)

    def _discover_first_scene(self) -> str:
        for root, _dirs, files in os.walk(self.project_dir):
            for fn in files:
                if fn.endswith(".reindeer.tscn"):
                    rel = os.path.relpath(os.path.join(root, fn),
                                          self.project_dir)
                    return rel.replace("\\", "/")
        return ""

    def _make_renderer(self, backend: str):
        if backend in ("pygame",):
            from engine.rendering.pygame_renderer import PygameRenderer
            return PygameRenderer(self.project_dir)
        if backend in ("qt", "pyside6"):
            from engine.rendering import Renderer2D
            return Renderer2D(self.project_dir)
        raise ValueError(f"unknown render backend: {backend}")

    # ------------------------------------------------------------------
    # frame loop
    # ------------------------------------------------------------------
    def run(self) -> int:
        """Dispatch to the backend-specific run loop."""
        if self.backend in ("qt", "pyside6"):
            return self.run_qt()
        return self.run_pygame()

    def run_qt(self) -> int:
        """Run the game loop in a separate PySide6 window."""
        from engine.runtime.qt_runtime import run as qt_run
        return qt_run(self.engine, self.width, self.height, self.title)

    def run_pygame(self) -> int:
        """Run the game loop with a pygame window. Returns a process exit code."""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        clock = pygame.time.Clock()
        running = True
        try:
            while running:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        running = False
                    elif ev.type == pygame.KEYDOWN:
                        self.engine.input.on_key_down(_qt_key_name(ev.key))
                    elif ev.type == pygame.KEYUP:
                        self.engine.input.on_key_up(_qt_key_name(ev.key))
                    elif ev.type == pygame.MOUSEBUTTONDOWN:
                        self.engine.input.on_mouse_down(
                            ev.button, ev.pos[0], ev.pos[1])
                    elif ev.type == pygame.MOUSEBUTTONUP:
                        self.engine.input.on_mouse_up(
                            ev.button, ev.pos[0], ev.pos[1])
                    elif ev.type == pygame.MOUSEMOTION:
                        self.engine.input.on_mouse_move(ev.pos[0], ev.pos[1])

                # ---- shared simulation step (identical to the editor) ----
                self.engine.step()
                # ---- render with the active backend ----
                cam = self.engine.tree.find_camera()
                self.renderer.begin(screen, self.width, self.height, cam)
                self.renderer.render(self.engine.tree)
                self.renderer.end()
                pygame.display.flip()
                clock.tick(60)
        finally:
            pygame.quit()
        return 0
