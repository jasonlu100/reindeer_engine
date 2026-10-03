"""Generates the example project's scene file.

Run once (``python build_example.py``) to materialise
``scenes/main.reindeer.tscn`` from the engine API.  This keeps the example
scene in sync with the engine's serialization format.

The scene is intentionally asset-free: it uses :class:`ColorRect2D` for every
visual element so it renders identically in the editor preview and in a shipped
pygame/pyside6 build without needing any image files.  The physics demo (a
dynamic crate falling onto a static floor), a scripted player, a blinking enemy,
an additive :class:`Light2D` and a vignette :class:`PostProcess` all exercise
the core engine features.
"""
from __future__ import annotations

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.core.engine import Engine
from engine.core.registry import get_registry
from engine.core.scene_format import SceneLoader
from engine.core.math2d import Vector2, Color


def build():
    engine = Engine(headless=True)
    reg = get_registry()

    root = reg.create("Node2D", "Main")

    # camera centred on the 960x540 design resolution
    cam = reg.create("Camera2D", "Camera2D")
    cam.current = True
    cam.position = Vector2(480, 270)
    root.add_child(cam)

    # full-view background (drawn first -> behind everything)
    bg = reg.create("ColorRect2D", "Background")
    bg.position = Vector2(480, 270)
    bg.width, bg.height = 960, 540
    bg.color = Color(0.10, 0.12, 0.20, 1.0)
    bg.z_index = -100
    root.add_child(bg)

    # static ground (collision + matching coloured bar, fully on screen)
    ground = reg.create("RigidBody2D", "Ground")
    ground.body_type = "static"
    ground.position = Vector2(480, 500)
    gcol = reg.create("CollisionShape2D", "Col")
    gcol.width, gcol.height = 900, 40
    ground.add_child(gcol)
    g_vis = reg.create("ColorRect2D", "GroundVisual")
    g_vis.width, g_vis.height = 900, 40
    g_vis.color = Color(0.28, 0.52, 0.32, 1.0)
    ground.add_child(g_vis)
    root.add_child(ground)

    # dynamic crate (falls onto the ground -> physics demo)
    crate = reg.create("RigidBody2D", "Crate")
    crate.position = Vector2(480, 200)
    ccol = reg.create("CollisionShape2D", "Col")
    ccol.width = ccol.height = 44
    crate.add_child(ccol)
    c_vis = reg.create("ColorRect2D", "CrateVisual")
    c_vis.width = c_vis.height = 44
    c_vis.color = Color(0.90, 0.55, 0.20, 1.0)
    crate.add_child(c_vis)
    root.add_child(crate)

    # scripted player
    player = reg.create("ColorRect2D", "Player")
    player.position = Vector2(160, 360)
    player.width, player.height = 40, 56
    player.color = Color(0.20, 0.70, 1.0, 1.0)
    player.script_path = "scripts/player.py"
    root.add_child(player)

    # blinking enemy
    enemy = reg.create("ColorRect2D", "Enemy")
    enemy.position = Vector2(700, 360)
    enemy.width, enemy.height = 40, 40
    enemy.color = Color(1.0, 0.30, 0.30, 1.0)
    enemy.script_path = "scripts/enemy.py"
    root.add_child(enemy)

    # additive light following the player
    light = reg.create("Light2D", "HeroLight")
    light.position = Vector2(160, 360)
    light.radius = 240.0
    light.energy = 0.9
    light.color = Color(1.0, 0.95, 0.8, 1.0)
    root.add_child(light)

    # decorative tile strip, fully inside the view (no stray edge stripe)
    tm = reg.create("TileMap", "Decor")
    tm.position = Vector2(240, 70)
    tm.tile_size = Vector2(40, 40)
    tm.palette = "#4a6fa5,#6b8e23,#888888,#c0392b"
    for i in range(12):
        tm.set_cell(i, 0, 1 if i % 2 == 0 else 2)
        tm.set_cell(i, 1, 3 if i % 3 == 0 else 2)
    root.add_child(tm)

    # vignette post effect (drawn last, on top of the scene)
    pp = reg.create("PostProcess", "PostFX")
    pp.effect = "vignette"
    pp.strength = 0.40
    pp.tint = Color(0.0, 0.0, 0.0, 1.0)
    root.add_child(pp)

    out_dir = os.path.join(HERE, "scenes")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "main.reindeer.tscn")
    SceneLoader(engine).save(root, out)

    # write project config (full, including run backend + window size)
    cfg = os.path.join(HERE, "project.reindeer")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({
            "name": "Reindeer Demo",
            "main_scene": "scenes/main.reindeer.tscn",
            "window_size": [960, 540],
            "run_backend": "pygame",
            "physics_backend": "builtin",
            "input_map": {
                "ui_left": ["Key_Left", "Key_A"],
                "ui_right": ["Key_Right", "Key_D"],
                "ui_up": ["Key_Up", "Key_W"],
                "ui_down": ["Key_Down", "Key_S"],
                "ui_accept": ["Key_Enter", "Key_Return", "Key_Space"],
                "ui_cancel": ["Key_Escape"],
                "ui_jump": ["Key_Space"],
                "ui_run": ["Key_Shift"],
            },
        }, f, indent=2)

    print(f"[build] wrote {out}")
    print(f"[build] node count = {engine.tree.get_node_count()}")


if __name__ == "__main__":
    build()
