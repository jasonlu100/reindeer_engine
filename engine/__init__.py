"""Reindeer 2D Game Engine.

A fully-featured, extensible 2D game engine written in Python with a
Godot-inspired node system, a built-in physics engine, a Python scripting
layer and a graphical editor.

The architecture is designed around a few clear, decoupled layers:

    engine.core        -> node tree, signals, input, resources, engine loop
    engine.physics     -> 2D rigid body simulation (no external deps)
    engine.nodes       -> concrete node implementations
    engine.rendering   -> abstraction over a 2D drawing surface
    engine.scripting   -> attachable Python scripts + rich API

All subsystems talk to each other through small, well-defined interfaces
(Node, Signal, Resource, Renderer) so that new node types and behaviour can be
added without touching existing code.
"""

__version__ = "0.1.0"
__author__ = "Reindeer Engine"

# ---------------------------------------------------------------------------
# Engine identity / branding
# ---------------------------------------------------------------------------
#: Canonical, human readable engine name used across the editor, window titles,
#: About dialog and packaged splash screens.
ENGINE_NAME = "Reindeer Engine"
#: Short tagline shown under the name in the About dialog / splash.
ENGINE_TAGLINE = "A Python 2D game engine with a Godot-inspired node system."
#: Brand colours (hex) shared by the editor logo and theme accents.
ENGINE_COLOR_PRIMARY = "#E8743B"    # warm reindeer orange
ENGINE_COLOR_ACCENT = "#F4C15D"     # gold (antler)
ENGINE_COLOR_BG = "#1B3A30"         # deep forest green (badge)

# Convenience re-exports used across the engine and editor.
from engine.core.math2d import Vector2, Rect2, Color
from engine.core.node import Node
from engine.core.signal import Signal
from engine.core.registry import NodeRegistry

__all__ = ["Vector2", "Rect2", "Color", "Node", "Signal", "NodeRegistry",
           "__version__", "ENGINE_NAME", "ENGINE_TAGLINE",
           "ENGINE_COLOR_PRIMARY", "ENGINE_COLOR_ACCENT", "ENGINE_COLOR_BG"]
