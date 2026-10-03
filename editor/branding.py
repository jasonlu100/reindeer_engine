"""Reindeer Engine visual identity.

Provides a programmatically drawn logo (an antler emblem on a rounded badge)
so the editor and packaged games carry a consistent brand mark without shipping
external image assets.  The same pixmap is used for the application icon, the
About dialog and the editor viewport watermark.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (QPixmap, QIcon, QPainter, QPen, QBrush, QColor,
                           QLinearGradient, QPainterPath)


def make_logo_pixmap(size: int = 256) -> QPixmap:
    """Return a ``size`` x ``size`` pixmap of the Reindeer Engine emblem."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # ---- rounded badge background (deep forest green gradient) ----
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#2E5E4E"))
    grad.setColorAt(1.0, QColor("#163027"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    radius = size * 0.20
    p.drawRoundedRect(0, 0, size, size, radius, radius)

    # ---- gold antler emblem ----
    gold = QColor("#F4C15D")
    p.setBrush(Qt.NoBrush)
    pen = QPen(gold, max(2, size * 0.055), Qt.SolidLine,
               Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    cx = size * 0.5
    cy = size * 0.52
    s = size

    def _antler(sign: int) -> None:
        # main stem (bottom-centre -> upper tip), slightly leaning outward
        base = QPointF(cx + sign * 0.04 * s, cy + 0.30 * s)
        k1 = QPointF(cx + sign * 0.10 * s, cy + 0.02 * s)
        k2 = QPointF(cx + sign * 0.14 * s, cy - 0.22 * s)
        tip = QPointF(cx + sign * 0.18 * s, cy - 0.38 * s)
        stem = QPainterPath()
        stem.moveTo(base)
        stem.lineTo(k1)
        stem.lineTo(k2)
        stem.lineTo(tip)
        p.drawPath(stem)
        # two side branches
        p.drawLine(QPointF(cx + sign * 0.11 * s, cy - 0.06 * s),
                   QPointF(cx + sign * 0.30 * s, cy - 0.02 * s))
        p.drawLine(QPointF(cx + sign * 0.14 * s, cy - 0.18 * s),
                   QPointF(cx + sign * 0.32 * s, cy - 0.18 * s))

    _antler(+1)
    _antler(-1)

    # small "head" dot where the antlers meet
    p.setBrush(QBrush(gold))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(cx, cy + 0.30 * s), size * 0.045, size * 0.045)

    p.end()
    return pix


_LOGO_CACHE: dict = {}


def engine_logo(size: int = 256) -> QPixmap:
    """Cached logo pixmap for a given size."""
    if size not in _LOGO_CACHE:
        _LOGO_CACHE[size] = make_logo_pixmap(size)
    return _LOGO_CACHE[size]


def engine_icon() -> QIcon:
    """Return a :class:`QIcon` built from the engine logo."""
    return QIcon(engine_logo(256))
