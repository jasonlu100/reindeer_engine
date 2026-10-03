"""Standalone pygame runtime entry point.

Launches a Reindeer project in a pygame window using the reusable
:class:`engine.runtime.game.GameRuntime`.  This is also the runtime that the
future packaging step embeds into the shipped executable.

Usage::

    python -m engine.runtime.pygame_app [scene.reindeer.tscn] --project <dir> \
          [--width 960] [--height 540] [--title "Game"]
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    parser = argparse.ArgumentParser(description="Reindeer pygame runtime")
    parser.add_argument("scene", nargs="?", default="",
                        help="scene file (.reindeer.tscn); defaults to the "
                             "project's configured main scene")
    parser.add_argument("--project", default="", help="project directory")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--title", default="Reindeer (Pygame)")
    args = parser.parse_args()

    from engine.runtime.game import GameRuntime
    runtime = GameRuntime(
        project_dir=args.project or os.getcwd(),
        main_scene=args.scene,
        width=args.width,
        height=args.height,
        title=args.title,
        backend="pygame",
    )
    sys.exit(runtime.run())


if __name__ == "__main__":
    main()
