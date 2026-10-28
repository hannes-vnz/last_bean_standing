"""Drawing between simulation ticks (render interpolation).

The simulation runs at a fixed 60 ticks per second, the screen at whatever the device manages.
Drawing the latest tick directly makes movement stutter whenever a frame gets 0 or 2 ticks, so the
renderer is shown the state `alpha` of the way from the previous tick to the latest one.
No pygame here, so it is testable headless.
"""

from __future__ import annotations

import dataclasses

from ..sim import DT

MAX_JUMP2 = 120.0**2  # farther than this in one tick is a teleport (e.g. a recycled enemy): no blending


def _mix(prev: tuple[float, float] | None, x: float, y: float, a: float) -> tuple[float, float]:
    if prev is None:
        return x, y
    px, py = prev
    if (x - px) ** 2 + (y - py) ** 2 > MAX_JUMP2:
        return x, y
    return px + (x - px) * a, py + (y - py) * a


def interpolate(snap, prev, alpha: float):
    """Snapshot with players, enemies and projectiles moved back to `alpha` between the two ticks."""
    if prev is None or alpha >= 1.0:
        return snap
    players_prev, enemies_prev = prev
    a = max(0.0, alpha)
    back = (1.0 - a) * DT
    players = tuple(p._replace(**dict(zip(("x", "y"), _mix(players_prev.get(p.player_id), p.x, p.y, a), strict=True)))
                    for p in snap.players)  # fmt: skip
    enemies = []
    for e in snap.enemies:
        x, y = _mix(enemies_prev.get(e.eid), e.x, e.y, a)
        enemies.append(e._replace(x=x, y=y))
    projectiles = tuple(pr._replace(x=pr.x - pr.vx * back, y=pr.y - pr.vy * back) for pr in snap.projectiles)
    return dataclasses.replace(snap, players=players, enemies=tuple(enemies), projectiles=projectiles)
