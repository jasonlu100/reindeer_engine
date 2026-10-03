"""Package a Reindeer project into a standalone Windows executable.

This module turns a :class:`~editor.project.Project` (a folder with a
``project.reindeer`` config, ``scenes/``, ``scripts/`` and ``sprites/``) into a
single ``.exe`` using PyInstaller.  The generated launcher boots the reusable
:class:`engine.runtime.game.GameRuntime` against the bundled project folder, so
the shipped game is byte-for-byte the same simulation the editor previews.

Typical use is from the editor's Export dialog, but the function
:func:`build_exe` is callable from anywhere and a small CLI is provided for
testing::

    python -m engine.runtime.build_exe --project example_project \\
           --name "My Game" --output dist
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from engine.core.project_config import load_project_config, DEFAULT_INPUT_MAP


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _repo_root() -> str:
    """Return the repository root (the folder that contains the ``engine`` pkg)."""
    here = os.path.dirname(os.path.abspath(__file__))
    # engine/runtime/build_exe.py -> repo root is two levels up
    return os.path.abspath(os.path.join(here, "..", ".."))


def _scan_scenes(project_dir: str) -> list:
    out = []
    for root, _dirs, files in os.walk(project_dir):
        for fn in files:
            if fn.endswith(".reindeer.tscn"):
                rel = os.path.relpath(os.path.join(root, fn), project_dir)
                out.append(rel.replace("\\", "/"))
    return sorted(out)


def _ensure_pyinstaller() -> bool:
    """Return True if PyInstaller is importable, installing it if the user
    permits.  Returns False if it cannot be made available."""
    try:
        import PyInstaller  # noqa: F401
        return True
    except Exception:
        return False


def _install_pyinstaller() -> bool:
    import subprocess
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# staging
# ---------------------------------------------------------------------------
def _stage_project(project_dir: str, main_scene: str, included_scenes: list,
                   backend: str, staging_game: str) -> dict:
    """Copy the project into ``staging_game`` keeping only the chosen scenes.

    ``scripts/`` and ``sprites/`` (and any other asset folders) are copied as a
    whole because scenes reference them by relative path; scene ``.tscn`` files
    not in ``included_scenes`` (and not the main scene) are dropped.
    """
    os.makedirs(staging_game, exist_ok=True)

    # copy everything, then prune unwanted scene files
    def _ignore(path, names):
        return {n for n in names
                if n in (".git", "__pycache__", "dist", "build")
                or n.endswith(".pyc")}

    if os.path.isdir(project_dir):
        for entry in os.listdir(project_dir):
            src = os.path.join(project_dir, entry)
            dst = os.path.join(staging_game, entry)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True,
                                ignore=_ignore)
            elif os.path.isfile(src) and not src.endswith(".pyc"):
                shutil.copy2(src, dst)

    keep = set(included_scenes)
    keep.add(main_scene)
    for root, _dirs, files in os.walk(staging_game):
        for fn in files:
            if fn.endswith(".reindeer.tscn"):
                rel = os.path.relpath(os.path.join(root, fn), staging_game)
                rel = rel.replace("\\", "/")
                if rel not in keep:
                    os.remove(os.path.join(root, fn))

    # (re)write the packaged project config so main scene + backend are correct.
    # We start from the (auto-repaired, normalized) source config so the custom
    # input_map and any extra keys survive into the packaged game.
    cfg = load_project_config(project_dir, repair_on_disk=False)
    physics = cfg.get("physics_backend", "builtin")
    pymunk_available = False
    try:                                    # keep pymunk only if it is installed
        import pymunk  # noqa: F401
        pymunk_available = True
    except Exception:
        if physics == "pymunk":
            physics = "builtin"
    packaged_cfg = dict(cfg)  # preserves input_map + any extra keys
    packaged_cfg["main_scene"] = main_scene
    packaged_cfg["run_backend"] = backend
    packaged_cfg["physics_backend"] = physics
    if not isinstance(packaged_cfg.get("input_map"), dict):
        packaged_cfg["input_map"] = {k: list(v)
                                     for k, v in DEFAULT_INPUT_MAP.items()}
    with open(os.path.join(staging_game, "project.reindeer"), "w",
              encoding="utf-8") as f:
        json.dump(packaged_cfg, f, indent=2, ensure_ascii=False)
    return packaged_cfg, pymunk_available


def _write_launcher(staging_dir: str, product_name: str, main_scene: str,
                    backend: str, repo_root: str,
                    bundle_pymunk: bool = False) -> str:
    """Write a self-contained launcher that runs the bundled project."""
    # normalise the backend the runtime understands
    rt_backend = "qt" if backend in ("pyside6", "qt") else "pygame"
    launcher = os.path.join(staging_dir, "launcher.py")
    # Force the chosen backend modules to be collected by PyInstaller regardless
    # of the runtime branch that is taken.
    if rt_backend == "qt":
        backend_imports = (
            "import PySide6  # noqa: F401\n"
            "from engine.rendering import Renderer2D  # noqa: F401\n"
        )
    else:
        backend_imports = (
            "import pygame  # noqa: F401\n"
            "from engine.rendering.pygame_renderer import PygameRenderer  # noqa: F401\n"
        )
    physics_imports = (
        "import pymunk  # noqa: F401\n" if bundle_pymunk else ""
    )
    code = (
        "# -*- coding: utf-8 -*-\n"
        "import os\n"
        "import sys\n"
        f"sys.path.insert(0, {repo_root!r})\n"
        "\n"
        "# Ensure the engine package and all node types are importable/bundled.\n"
        "import engine.nodes  # noqa: F401\n"
        "import engine.scripting.script  # noqa: F401\n"
        + backend_imports +
        physics_imports +
        "\n"
        "from engine.runtime.game import GameRuntime\n"
        "\n"
        "def _project_dir():\n"
        "    if getattr(sys, 'frozen', False):\n"
        "        # PyInstaller onefile: bundled data lives under _MEIPASS\n"
        "        return os.path.join(sys._MEIPASS, 'game_project')\n"
        "    return os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
        "                        'game_project')\n"
        "\n"
        "def main():\n"
        "    rt = GameRuntime(\n"
        "        project_dir=_project_dir(),\n"
        f"        main_scene={main_scene!r},\n"
        f"        backend={rt_backend!r},\n"
        "    )\n"
        "    sys.exit(rt.run())\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(code)
    return launcher


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def build_exe(project_dir: str, product_name: str, company: str = "",
              main_scene: str = "", included_scenes: list = None,
              splash: str = "", output_dir: str = "", backend: str = None,
              clean: bool = True) -> str:
    """Package ``project_dir`` into a standalone executable.

    Parameters
    ----------
    project_dir:
        Root of the Reindeer project (contains ``project.reindeer``).
    product_name:
        Name of the product / output executable (without extension).
    company:
        Copyright / company string baked into the executable metadata.
    main_scene:
        Scene file relative to ``project_dir`` used as the game entry point.
    included_scenes:
        Additional ``.reindeer.tscn`` files (relative paths) to bundle.  The
        ``main_scene`` is always included even if omitted here.
    splash:
        Optional path to a PNG splash screen shown while the exe loads.
    output_dir:
        Folder where the final ``.exe`` is written (default: ``<project>/dist``).
    backend:
        Render backend for the packaged game (``pyside6`` or ``pygame``).
        Defaults to the project's configured ``run_backend``.
    clean:
        Remove the temporary staging / build artefacts afterwards.

    Returns
    -------
    str
        Absolute path to the generated executable.

    Raises
    ------
    RuntimeError
        If PyInstaller cannot be obtained or the build fails.
    """
    project_dir = os.path.abspath(project_dir)
    cfg = _load_config(project_dir)

    if not main_scene:
        main_scene = cfg.get("main_scene", "")
    if not main_scene:
        all_scenes = _scan_scenes(project_dir)
        if not all_scenes:
            raise RuntimeError("no scenes found in project")
        main_scene = all_scenes[0]
    if backend is None:
        backend = cfg.get("run_backend", "pyside6")
    if included_scenes is None:
        included_scenes = _scan_scenes(project_dir)

    if not _ensure_pyinstaller():
        if not _install_pyinstaller():
            raise RuntimeError(
                "PyInstaller is required but could not be installed. "
                "Run: pip install pyinstaller")
    import PyInstaller.__main__ as pyi_main  # noqa: E402

    repo_root = _repo_root()
    work_root = tempfile.mkdtemp(prefix="reindeer_build_")
    staging_game = os.path.join(work_root, "game_project")
    _, pymunk_available = _stage_project(project_dir, main_scene,
                                        included_scenes, backend, staging_game)
    launcher = _write_launcher(work_root, product_name, main_scene, backend,
                               repo_root, bundle_pymunk=pymunk_available)

    if not output_dir:
        output_dir = os.path.join(project_dir, "dist")
    os.makedirs(output_dir, exist_ok=True)
    build_dir = os.path.join(work_root, "build")
    spec_dir = work_root

    sep = os.pathsep
    args = [
        launcher,
        "--name", product_name,
        "--onefile",
        "--windowed",
        "--distpath", output_dir,
        "--workpath", build_dir,
        "--specpath", spec_dir,
        "--paths", repo_root,
        "--add-data", f"{staging_game}{sep}game_project",
        "--hidden-import", "engine",
        "--hidden-import", "engine.nodes",
        "--hidden-import", "engine.scripting.script",
    ]
    if pymunk_available:
        # pymunk is imported lazily at runtime, so force PyInstaller to bundle it
        # when the packaged game is configured to use the pymunk backend.
        args += ["--hidden-import", "pymunk"]
    if backend in ("pyside6", "qt"):
        args += ["--hidden-import", "PySide6",
                 "--hidden-import", "PySide6.QtCore",
                 "--hidden-import", "PySide6.QtGui",
                 "--hidden-import", "PySide6.QtWidgets"]
    else:
        args += ["--hidden-import", "pygame"]
    if company:
        args += ["--copyright", company]
    if splash and os.path.isfile(splash) and splash.lower().endswith(".png"):
        args += ["--splash", splash]

    try:
        pyi_main.run(args)
    except SystemExit as exc:           # PyInstaller calls sys.exit()
        if int(getattr(exc, "code", 0) or 0) not in (0, None):
            raise RuntimeError(f"PyInstaller exited with code {exc.code}")

    exe = os.path.join(output_dir, product_name + ".exe")
    if not os.path.isfile(exe):
        raise RuntimeError("PyInstaller finished but no executable was produced")

    if clean:
        shutil.rmtree(work_root, ignore_errors=True)
    return exe


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli_main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Package a Reindeer project to EXE")
    p.add_argument("--project", required=True, help="project directory")
    p.add_argument("--name", default="", help="product name")
    p.add_argument("--company", default="")
    p.add_argument("--main-scene", default="")
    p.add_argument("--scenes", nargs="*", default=None, help="extra scenes")
    p.add_argument("--splash", default="")
    p.add_argument("--output", default="")
    p.add_argument("--backend", default=None,
                   choices=["pyside6", "pygame"])
    args = p.parse_args()

    name = args.name or os.path.basename(os.path.abspath(args.project))
    exe = build_exe(args.project, name, company=args.company,
                    main_scene=args.main_scene,
                    included_scenes=args.scenes, splash=args.splash,
                    output_dir=args.output, backend=args.backend)
    print(f"[build] executable: {exe}")


if __name__ == "__main__":
    _cli_main()
