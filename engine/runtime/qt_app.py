"""Standalone PySide6 runtime entry point.

Launches a Reindeer project in a separate PySide6 window using the reusable
:class:`engine.runtime.game.GameRuntime` with the ``qt`` backend.  This is the
PySide6 equivalent of :mod:`engine.runtime.pygame_app` and, like it, is the
runtime the packaging step reuses for the shipped executable.
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    parser = argparse.ArgumentParser(description="Reindeer PySide6 runtime")
    parser.add_argument("scene", nargs="?", default="",
                        help="scene file (.reindeer.tscn); defaults to the "
                             "project's configured main scene")
    parser.add_argument("--project", default="", help="project directory")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--title", default="Reindeer (PySide6)")
    args = parser.parse_args()

    from engine.runtime.game import GameRuntime
    runtime = GameRuntime(
        project_dir=args.project or os.getcwd(),
        main_scene=args.scene,
        width=args.width,
        height=args.height,
        title=args.title,
        backend="qt",
    )
    sys.exit(runtime.run())


if __name__ == "__main__":
    main()
