"""Logical canvas size for any screen: phone in portrait, tablet, desktop.

The short side of the canvas is fixed (360 pixels, 300 on small phones so everything is a bit
bigger); the long side follows the screen's aspect ratio. Pixels are always scaled up by whole
numbers, so the pixel art stays sharp. A taller or wider screen simply shows more of the map.
"""

from __future__ import annotations

SHORT_SIDE = 360
SHORT_SIDE_COMPACT = 300  # small phones: zoom in a little
COMPACT_BELOW = 500  # CSS pixels of the shorter screen side
MAX_ASPECT = 2.4  # very long screens get bars instead of an extreme view


def logical_size(width: float, height: float, compact: bool = False) -> tuple[int, int]:
    short = SHORT_SIDE_COMPACT if compact else SHORT_SIDE
    width, height = max(1.0, width), max(1.0, height)
    if width >= height:
        aspect = min(width / height, MAX_ASPECT)
        return _even(short * aspect), short
    aspect = min(height / width, MAX_ASPECT)
    return short, _even(short * aspect)


def is_compact(css_width: float, css_height: float) -> bool:
    return min(css_width, css_height) < COMPACT_BELOW


def _even(v: float) -> int:
    return int(round(v / 2)) * 2
