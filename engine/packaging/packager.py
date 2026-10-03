"""Packaging tools for Reindeer projects (foundation).

Today this module knows how to:

* :func:`collect_game_files` -- copy the engine runtime (pure-python core + the
  pygame renderer) and the project's assets (scenes, scripts, sprites, addons)
  into an output folder,
* :func:`write_launcher` -- write a small ``run_game.py`` that boots
  :class:`engine.runtime.game.GameRuntime` with the pygame backend,
* :func:`build` -- assemble the folder-based build and optionally hand off to
  `PyInstaller` (when installed) to produce a single executable.

The full "one-click ship" pipeline (icon, installer, platform targets) can be
layered on top of these primitives later.  The runtime that ships inside the
package is exactly the same :class:`engine.runtime.game.GameRuntime` used by the
editor's "Run (Pygame)" button, so there is no behaviour drift between testing
in the editor and the released build.

Usage::

    python -m engine.packaging.packager path/to/project [--output build/game] \
          [--name MyGame] [--onefile]
"""
from __future__ import annotations

import json
import os
import shutil
import sys

# Project folders copied verbatim into the build.
_PROJECT_ASSET_DIRS = ("scenes", "scripts", "sprites",
                       "audio", "fonts", "shaders")
# Engine sub-packages that make up the runtime (the editor is intentionally
# excluded -- a packaged game does not need PySide6 / the editor).
_ENGINE_SUBDIRS = ("core", "nodes", "physics",
                   "rendering", "runtime", "scripting")


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def collect_game_files(project_dir: str, output_dir: str) -> str:
    """Copy the engine runtime + project assets into ``output_dir``.

    Returns the path to the bundled ``engine`` package directory.
    """
    project_dir = os.path.abspath(project_dir)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    engine_src = os.path.join(_repo_root(), "engine")
    engine_dst = os.path.join(output_dir, "engine")
    if os.path.exists(engine_dst):
        shutil.rmtree(engine_dst)
    os.makedirs(engine_dst, exist_ok=True)
    for sub in _ENGINE_SUBDIRS:
        src = os.path.join(engine_src, sub)
        if os.path.isdir(src):
            shutil.copytree(
                src, os.path.join(engine_dst, sub),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo",
                                             ".git"))
    # copy the engine package __init__ so ``import engine`` works from the build
    shutil.copy2(os.path.join(engine_src, "__init__.py"),
                 os.path.join(engine_dst, "__init__.py"))

    # project descriptor + assets
    cfg = os.path.join(project_dir, "project.reindeer")
    if os.path.exists(cfg):
        shutil.copy2(cfg, os.path.join(output_dir, "project.reindeer"))
    for d in _PROJECT_ASSET_DIRS:
        src = os.path.join(project_dir, d)
        if os.path.isdir(src):
            dst = os.path.join(output_dir, d)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(
                src, dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo",
                                             ".git"))

    print(f"[package] collected engine runtime -> {engine_dst}")
    return engine_dst


_LAUNCHER_TEMPLATE = '''\
"""Auto-generated launcher for a packaged Reindeer project.

Boots the pygame runtime against the bundled project in this folder.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine.runtime.game import GameRuntime


def main() -> None:
    runtime = GameRuntime(project_dir=HERE, backend="pygame")
    sys.exit(runtime.run())


if __name__ == "__main__":
    main()
'''


def write_launcher(output_dir: str, app_name: str = "game") -> str:
    """Write ``run_game.py`` (and ``<app_name>.spec`` note) into ``output_dir``."""
    launcher = os.path.join(output_dir, "run_game.py")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(_LAUNCHER_TEMPLATE)
    print(f"[package] wrote launcher -> {launcher}")
    return launcher


def build(project_dir: str, output_dir: str = None, app_name: str = "game",
          onefile: bool = False) -> str:
    """Assemble a runnable build of ``project_dir``.

    Returns the output directory.  If ``onefile`` is requested and PyInstaller
    is available, it is invoked to wrap the launcher into a single executable;
    otherwise the folder-based build (engine + assets + launcher) is produced,
    which is already runnable via ``python run_game.py``.
    """
    project_dir = os.path.abspath(project_dir)
    if output_dir is None:
        output_dir = os.path.join(project_dir, "build", app_name)

    collect_game_files(project_dir, output_dir)
    write_launcher(output_dir, app_name)

    if onefile:
        _try_pyinstaller(output_dir, app_name)
    else:
        print(f"[package] folder build ready at: {output_dir}")
        print(f"[package] run with: python "
              f"{os.path.join(output_dir, 'run_game.py')}")
    return output_dir


def _try_pyinstaller(output_dir: str, app_name: str) -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        print("[package] PyInstaller not installed; skipping onefile build.")
        print(f"[package] folder build remains runnable via run_game.py")
        return
    import subprocess
    launcher = os.path.join(output_dir, "run_game.py")
    cmd = [sys.executable, "-m", "PyInstaller", "--name", app_name,
           "--onefile", "--noconsole", launcher]
    try:
        subprocess.run(cmd, cwd=output_dir, check=True)
        print(f"[package] PyInstaller build finished for {app_name}")
    except Exception as exc:
        print(f"[package] PyInstaller build failed: {exc}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Reindeer packaging tool")
    parser.add_argument("project", help="project directory")
    parser.add_argument("--output", default=None, help="output directory")
    parser.add_argument("--name", default="game", help="application name")
    parser.add_argument("--onefile", action="store_true",
                        help="also wrap into a single exe via PyInstaller")
    args = parser.parse_args()
    build(args.project, args.output, args.name, args.onefile)


if __name__ == "__main__":
    main()
