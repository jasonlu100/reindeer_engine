"""Packaging scaffold for Reindeer projects.

This is the *foundation* for turning a project into a standalone, distributable
build.  See :mod:`engine.packaging.packager` for the build primitives and the
command-line interface.
"""
from engine.packaging.packager import (
    build,
    collect_game_files,
    write_launcher,
)

__all__ = ["build", "collect_game_files", "write_launcher"]
