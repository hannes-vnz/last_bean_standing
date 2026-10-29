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
# Player zoom: the short side in steps; smaller = closer. Set in Optionen, or mouse wheel and +/-.
ZOOM_STEPS = (240, 270, 300, 330, 360, 400, 440, 480)


def default_short_side(compact: bool) -> int:
    return SHORT_SIDE_COMPACT if compact else SHORT_SIDE


def zoom_step(short: int, steps: int) -> int:
    """Move `steps` zoom steps out (positive) or in (negative), clamped to the allowed range."""
    i = min(range(len(ZOOM_STEPS)), key=lambda k: abs(ZOOM_STEPS[k] - short))
    return ZOOM_STEPS[max(0, min(len(ZOOM_STEPS) - 1, i + steps))]


def logical_size(width: float, height: float, compact: bool = False, short: int | None = None) -> tuple[int, int]:
    short = short or default_short_side(compact)
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


def pixel_perfect_size(css_w: float, css_h: float, dpr: float, short: int) -> tuple[int, int, int]:
    """Browser: canvas size and k such that every canvas pixel is exactly k x k device pixels.

    Stretching by an uneven factor (say 1.3) makes some pixels one and others two screen pixels wide,
    which is most visible on text. k is the whole number that brings the short side closest to
    `short`; the canvas then covers the screen with at most k - 1 device pixels left over."""
    dw, dh = max(1.0, css_w * dpr), max(1.0, css_h * dpr)
    k = max(1, round(min(dw, dh) / short))
    return int(dw // k), int(dh // k), k
