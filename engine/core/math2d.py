"""2D math types used throughout the engine.

A lightweight ``Vector2``/``Rect2``/``Color`` implementation that works both
for simulation/rendering math and for serialization.  Keeping the math in a
single module avoids pulling heavy dependencies and makes the engine easy to
embed in the editor (which renders with Qt's QPainter).
"""
from __future__ import annotations

import math
from typing import Iterable, Tuple


class Vector2:
    """Immutable-ish 2D vector with operator overloading."""

    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    # ----- construction helpers -----
    @classmethod
    def zero(cls) -> "Vector2":
        return cls(0.0, 0.0)

    @classmethod
    def one(cls) -> "Vector2":
        return cls(1.0, 1.0)

    @classmethod
    def from_angle(cls, rad: float, length: float = 1.0) -> "Vector2":
        return cls(math.cos(rad) * length, math.sin(rad) * length)

    # ----- operators -----
    def __add__(self, o: "Vector2") -> "Vector2":
        return Vector2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vector2") -> "Vector2":
        return Vector2(self.x - o.x, self.y - o.y)

    def __mul__(self, s: float) -> "Vector2":
        return Vector2(self.x * s, self.y * s)

    def __rmul__(self, s: float) -> "Vector2":
        return Vector2(self.x * s, self.y * s)

    def __truediv__(self, s: float) -> "Vector2":
        return Vector2(self.x / s, self.y / s)

    def __neg__(self) -> "Vector2":
        return Vector2(-self.x, -self.y)

    def __eq__(self, o) -> bool:
        if not isinstance(o, Vector2):
            return NotImplemented
        return self.x == o.x and self.y == o.y

    def __hash__(self):
        return hash((self.x, self.y))

    def __repr__(self):
        return f"Vector2({self.x:.3f}, {self.y:.3f})"

    # ----- vector maths -----
    def dot(self, o: "Vector2") -> float:
        return self.x * o.x + self.y * o.y

    def cross(self, o: "Vector2") -> float:
        return self.x * o.y - self.y * o.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> "Vector2":
        l = self.length()
        if l < 1e-9:
            return Vector2(0, 0)
        return Vector2(self.x / l, self.y / l)

    def distance_to(self, o: "Vector2") -> float:
        return math.hypot(self.x - o.x, self.y - o.y)

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def rotated(self, rad: float) -> "Vector2":
        c, s = math.cos(rad), math.sin(rad)
        return Vector2(self.x * c - self.y * s, self.x * s + self.y * c)

    def clamped(self, max_length: float) -> "Vector2":
        l = self.length()
        if l > max_length and l > 1e-9:
            return self * (max_length / l)
        return Vector2(self.x, self.y)

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


class Rect2:
    """Axis-aligned rectangle."""

    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float = 0.0, y: float = 0.0, w: float = 0.0, h: float = 0.0):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)

    def position(self) -> Vector2:
        return Vector2(self.x, self.y)

    def size(self) -> Vector2:
        return Vector2(self.w, self.h)

    def center(self) -> Vector2:
        return Vector2(self.x + self.w / 2.0, self.y + self.h / 2.0)

    def end(self) -> Vector2:
        return Vector2(self.x + self.w, self.y + self.h)

    def intersects(self, o: "Rect2") -> bool:
        return not (self.x > o.x + o.w or self.x + self.w < o.x or
                    self.y > o.y + o.h or self.y + self.h < o.y)

    def contains(self, p: Vector2) -> bool:
        return self.x <= p.x <= self.x + self.w and self.y <= p.y <= self.y + self.h

    def expanded(self, v: Vector2) -> "Rect2":
        nx, ny = self.x, self.y
        mx, my = self.x + self.w, self.y + self.h
        nx = min(nx, v.x); ny = min(ny, v.y)
        mx = max(mx, v.x); my = max(my, v.y)
        return Rect2(nx, ny, mx - nx, my - ny)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


class Color:
    """RGBA color, components in 0..1."""

    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r: float = 1.0, g: float = 1.0, b: float = 1.0, a: float = 1.0):
        self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)

    @classmethod
    def from_hex(cls, hexstr: str) -> "Color":
        h = hexstr.strip().lstrip("#")
        if len(h) in (3, 4):
            # shorthand #rgb / #rgba -> expand each channel
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            h += "ff"
        if len(h) != 8:
            raise ValueError(f"Invalid hex color: '{hexstr}'")
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        a = int(h[6:8], 16) / 255.0
        return cls(r, g, b, a)

    @classmethod
    def white(cls):
        return cls(1, 1, 1, 1)

    @classmethod
    def red(cls):
        return cls(1, 0, 0, 1)

    @classmethod
    def green(cls):
        return cls(0, 1, 0, 1)

    @classmethod
    def blue(cls):
        return cls(0, 0, 1, 1)

    @classmethod
    def black(cls):
        return cls(0, 0, 0, 1)

    def to_qrgba(self) -> int:
        """Convert to a Qt QRgba integer (0xAARRGGBB)."""
        R = int(max(0, min(1, self.r)) * 255)
        G = int(max(0, min(1, self.g)) * 255)
        B = int(max(0, min(1, self.b)) * 255)
        A = int(max(0, min(1, self.a)) * 255)
        return (A << 24) | (R << 16) | (G << 8) | B

    def as_tuple(self):
        return (self.r, self.g, self.b, self.a)

    def __repr__(self):
        return f"Color({self.r:.2f},{self.g:.2f},{self.b:.2f},{self.a:.2f})"
