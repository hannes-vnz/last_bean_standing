"""Touch controls: a floating joystick wherever the thumb lands, plus tap detection.

Positions are canvas pixels. The simulation takes 8 directions (move_x/move_y in -1, 0, 1),
so the stick is reduced to the nearest of them; no trigonometry needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEAD_ZONE = 8.0  # canvas pixels the thumb must move before the bean walks
RADIUS = 36.0  # drawn size of the stick base; the knob is clamped to it
DIAGONAL = 0.38  # a component counts once it is this share of the full deflection (about 22.5 degrees)
TAP_MAX_MOVE = 12.0


@dataclass
class Joystick:
    finger: int
    ox: float
    oy: float
    x: float
    y: float

    def direction(self) -> tuple[int, int]:
        dx, dy = self.x - self.ox, self.y - self.oy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < DEAD_ZONE:
            return 0, 0
        mx = (1 if dx > 0 else -1) if abs(dx) >= DIAGONAL * dist else 0
        my = (1 if dy > 0 else -1) if abs(dy) >= DIAGONAL * dist else 0
        return mx, my

    def knob(self) -> tuple[float, float]:
        dx, dy = self.x - self.ox, self.y - self.oy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= RADIUS:
            return self.x, self.y
        return self.ox + dx / dist * RADIUS, self.oy + dy / dist * RADIUS


class TouchState:
    """Tracks fingers. One finger outside the buttons steers; short touches count as taps."""

    def __init__(self) -> None:
        self.stick: Joystick | None = None
        self._down: dict[int, tuple[float, float]] = {}

    def down(self, finger: int, x: float, y: float, steer: bool) -> None:
        self._down[finger] = (x, y)
        if steer and self.stick is None:
            self.stick = Joystick(finger, x, y, x, y)

    def move(self, finger: int, x: float, y: float) -> None:
        if self.stick and self.stick.finger == finger:
            self.stick.x, self.stick.y = x, y

    def up(self, finger: int, x: float, y: float) -> bool:
        """Release a finger. Returns True when it was a tap (little movement)."""
        start = self._down.pop(finger, None)
        if self.stick and self.stick.finger == finger:
            self.stick = None
        if start is None:
            return False
        return (x - start[0]) ** 2 + (y - start[1]) ** 2 <= TAP_MAX_MOVE**2

    def direction(self) -> tuple[int, int]:
        return self.stick.direction() if self.stick else (0, 0)

    def reset(self) -> None:
        self.stick = None
        self._down.clear()
