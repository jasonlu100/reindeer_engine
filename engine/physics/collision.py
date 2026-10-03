"""Narrow-phase collision detection.

Produces a :class:`Manifold` (contact normal, penetration depth and contact
points) for circle/box/polygon pairs.  The math is a compact, well-known
implementation of:

* circle vs circle
* circle vs convex polygon (with inside test)
* convex polygon vs convex polygon (SAT + reference/incident face clipping)

All functions operate on already-transformed *world-space* vertices so the
broad phase can stay shape-agnostic.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from engine.core.math2d import Vector2, Rect2
from engine.physics.collider import CircleShape


class Manifold:
    __slots__ = ("normal", "penetration", "contacts")

    def __init__(self, normal: Vector2, penetration: float, contacts: List[Vector2]):
        # normal points from A to B
        self.normal = normal
        self.penetration = penetration
        self.contacts = contacts


# ----------------------------------------------------------------------
# circle vs circle
# ----------------------------------------------------------------------
def circle_circle(a_pos: Vector2, a_r: float, b_pos: Vector2, b_r: float) -> Optional[Manifold]:
    normal = b_pos - a_pos
    dist_sq = normal.length_squared()
    r = a_r + b_r
    if dist_sq >= r * r:
        return None
    dist = dist_sq ** 0.5
    if dist == 0.0:
        normal = Vector2(0, 1)
        pen = a_r
        contact = a_pos
    else:
        normal = normal / dist
        pen = r - dist
        contact = a_pos + normal * a_r
    return Manifold(normal, pen, [contact])


# ----------------------------------------------------------------------
# circle (A) vs convex polygon (B)
# ----------------------------------------------------------------------
def circle_polygon(c: Vector2, r: float, verts: List[Vector2],
                   flip: bool = False) -> Optional[Manifold]:
    n = len(verts)
    best_sep = -1e9
    best_idx = 0
    for i in range(n):
        v1 = verts[i]
        v2 = verts[(i + 1) % n]
        edge = v2 - v1
        nrm = Vector2(edge.y, -edge.x).normalized()  # outward (CCW winding)
        d = nrm.dot(c - v1)
        if d > r:
            return None  # separating axis -> no collision
        if d > best_sep:
            best_sep = d
            best_idx = i
            best_nrm = nrm

    if best_sep < 0:
        # center is inside the polygon
        normal = best_nrm
        pen = r - best_sep  # best_sep negative -> r + |best_sep|
        if flip:
            normal = -normal
        return Manifold(normal, pen, [Vector2(c.x, c.y)])
    else:
        # center outside, near face best_idx
        v1 = verts[best_idx]
        v2 = verts[(best_idx + 1) % n]
        # closest point on the face segment to the circle center
        edge = v2 - v1
        t = max(0.0, min(1.0, edge.dot(c - v1) / max(edge.length_squared(), 1e-9)))
        closest = v1 + edge * t
        delta = c - closest
        dist = delta.length()
        if dist > r:
            return None
        if dist == 0.0:
            normal = best_nrm
        else:
            normal = delta / dist
        pen = r - dist
        if flip:
            normal = -normal
        return Manifold(normal, pen, [closest])


# ----------------------------------------------------------------------
# convex polygon vs convex polygon (SAT + clipping)
# ----------------------------------------------------------------------
def _find_least_penetration(verts1: List[Vector2], verts2: List[Vector2]
                            ) -> Tuple[float, int]:
    best_dist = -1e9
    best_idx = 0
    n = len(verts1)
    for i in range(n):
        v1 = verts1[i]
        v2 = verts1[(i + 1) % n]
        edge = v2 - v1
        nrm = Vector2(edge.y, -edge.x).normalized()
        # support point of verts2 in -nrm direction
        min_proj = 1e9
        for p in verts2:
            proj = nrm.dot(p)
            if proj < min_proj:
                min_proj = proj
        proj1 = nrm.dot(v1)
        d = min_proj - proj1
        if d > best_dist:
            best_dist = d
            best_idx = i
    return best_dist, best_idx


def _clip(v: Vector2, n: Vector2, offset: float) -> Tuple[float, bool]:
    """Clip a single point against plane n·x <= offset. Returns (dist, inside)."""
    d = n.dot(v) - offset
    return d, (d <= 0.0)


def polygon_polygon(vertsA: List[Vector2], vertsB: List[Vector2]
                    ) -> Optional[Manifold]:
    penA, faceA = _find_least_penetration(vertsA, vertsB)
    if penA >= 0:
        return None
    penB, faceB = _find_least_penetration(vertsB, vertsA)
    if penB >= 0:
        return None

    ref_verts, inc_verts, ref_face, flip = (
        (vertsA, vertsB, faceA, False) if penA > penB - 0.0005
        else (vertsB, vertsA, faceB, True))

    rn = len(ref_verts)
    v1 = ref_verts[ref_face]
    v2 = ref_verts[(ref_face + 1) % rn]
    side_plane_normal = (v2 - v1).normalized()

    ref_face_normal = Vector2(side_plane_normal.y, -side_plane_normal.x)
    ref_face_offset = ref_face_normal.dot(v1)
    neg_side_offset = -side_plane_normal.dot(v1)
    pos_side_offset = side_plane_normal.dot(v2)

    # incident face = most anti-parallel face on the incident polygon
    inc_n = len(inc_verts)
    min_dot = 1e9
    inc_face = 0
    for i in range(inc_n):
        edge = inc_verts[(i + 1) % inc_n] - inc_verts[i]
        nrm = Vector2(edge.y, -edge.x).normalized()
        d = ref_face_normal.dot(nrm)
        if d < min_dot:
            min_dot = d
            inc_face = i
    i1 = inc_verts[inc_face]
    i2 = inc_verts[(inc_face + 1) % inc_n]

    # clip incident face against the two side planes of the reference face
    cp = [i1, i2]
    if not _clip_incident(cp, -side_plane_normal, neg_side_offset):
        return None
    if not _clip_incident(cp, side_plane_normal, pos_side_offset):
        return None

    contacts = []
    for p in cp:
        if ref_face_normal.dot(p) - ref_face_offset <= 0.0:
            contacts.append(p)
    if not contacts:
        return None

    normal = ref_face_normal if not flip else -ref_face_normal
    # penetration ~ distance of first contact below reference face
    pen = -(ref_face_normal.dot(contacts[0]) - ref_face_offset)
    return Manifold(normal, max(pen, 0.0), contacts)


def _clip_incident(cp: List[Vector2], n: Vector2, offset: float) -> bool:
    out = []
    d0, in0 = _clip(cp[0], n, offset)
    d1, in1 = _clip(cp[1], n, offset)
    if in0:
        out.append(cp[0])
    if in1:
        out.append(cp[1])
    if not in0 and in1:
        t = d0 / (d0 - d1)
        out.append(cp[0] + (cp[1] - cp[0]) * t)
    if in0 and not in1:
        t = d0 / (d0 - d1)
        out.append(cp[0] + (cp[1] - cp[0]) * t)
    cp[:] = out
    return len(cp) == 2


# ----------------------------------------------------------------------
# dispatcher
# ----------------------------------------------------------------------
def collide(a_shape, a_pos: Vector2, a_angle: float, a_scale: Vector2,
            b_shape, b_pos: Vector2, b_angle: float, b_scale: Vector2
            ) -> Optional[Manifold]:
    a_verts = a_shape.world_vertices(a_pos, a_angle, a_scale)
    b_verts = b_shape.world_vertices(b_pos, b_angle, b_scale)
    a_circle = isinstance(a_shape, CircleShape)
    b_circle = isinstance(b_shape, CircleShape)

    if a_circle and b_circle:
        return circle_circle(a_pos, a_shape.scaled_radius(a_scale),
                             b_pos, b_shape.scaled_radius(b_scale))
    if a_circle and not b_circle:
        return circle_polygon(a_pos, a_shape.scaled_radius(a_scale), b_verts, flip=False)
    if not a_circle and b_circle:
        m = circle_polygon(b_pos, b_shape.scaled_radius(b_scale), a_verts, flip=True)
        return m
    return polygon_polygon(a_verts, b_verts)
