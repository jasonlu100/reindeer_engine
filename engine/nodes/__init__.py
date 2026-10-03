"""Concrete node implementations package.

Importing this package registers every built-in node with the global
:class:`~engine.core.registry.NodeRegistry`, so the editor and the scene
loader can discover them.
"""
from engine.core.node import Node
from engine.core.registry import get_registry

# register the base Node type so plain nodes can be created in the editor
get_registry().register(Node, "Node")

# import modules -> their @register_node decorators run
from engine.nodes.node2d import Node2D            # noqa: E402,F401
from engine.nodes.sprite import Sprite2D          # noqa: E402,F401
from engine.nodes.collision_shape import CollisionShape2D  # noqa: E402,F401
from engine.nodes.rigidbody2d import RigidBody2D  # noqa: E402,F401
from engine.nodes.area2d import Area2D            # noqa: E402,F401
from engine.nodes.camera2d import Camera2D        # noqa: E402,F401
from engine.nodes.label import Label, Node2DHelper  # noqa: E402,F401
from engine.nodes.timer import Timer              # noqa: E402,F401
from engine.nodes.misc import Position2D, CanvasLayer  # noqa: E402,F401
from engine.nodes.visual_extra import (Light2D, ColorRect2D,  # noqa: E402,F401
                                       Polygon2D, Line2D)
from engine.nodes.ui_extra import Button2D, ProgressBar  # noqa: E402,F401
from engine.nodes.particles import Particles2D  # noqa: E402,F401
from engine.nodes.animated_sprite import AnimatedSprite2D  # noqa: E402,F401
from engine.nodes.path2d import Path2D, PathFollow2D  # noqa: E402,F401
from engine.nodes.effects import PostProcess, TileMap  # noqa: E402,F401
from engine.nodes.extra_nodes import (Tween, AudioStreamPlayer,  # noqa: E402,F401
                                      VisibilityNotifier2D,
                                      ParallaxBackground, ParallaxObject,
                                      TextureRect, NinePatchRect,
                                      RemoteTransform2D, Spawner, Joint2D)
