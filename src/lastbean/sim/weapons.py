"""Extra weapons (Paket C2): picked from level-up cards, up to `slots` including the start weapon.

Each weapon kind is one method in `world.WEAPON_KINDS` (plus the orbit, which runs every tick);
numbers come from `data/weapons.json`.
Level L uses `base + per_level * (L - 1)` (counts rounded down). Damage scales with the player's
damage bonus, cooldowns with the attack speed bonus, crits roll with the player's crit chance.

Determinism: angles go through `cos_sin`, a Taylor series using only + - * /, so the result
is bit-identical on every IEEE 754 platform (math.cos is not guaranteed to be).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

TAU = 2.0 * math.pi
WEAPON_PREFIX = "weapon:"  # level-up cards for weapons are "weapon:<id>"


def cos_sin(angle: float) -> tuple[float, float]:
    """cos and sin without the platform's libm: reduce to [-pi, pi], then 14 Taylor terms."""
    a = angle - TAU * float(int(angle / TAU))
    if a > math.pi:
        a -= TAU
    elif a < -math.pi:
        a += TAU
    a2 = a * a
    c, s = 1.0, a
    term_c, term_s = 1.0, a
    for k in range(1, 14):
        term_c *= -a2 / ((2 * k - 1) * (2 * k))
        term_s *= -a2 / ((2 * k) * (2 * k + 1))
        c += term_c
        s += term_s
    return c, s


@dataclass(frozen=True, slots=True)
class WeaponDef:
    id: str
    kind: str
    rarity: str
    base: tuple[tuple[str, float], ...]
    per_level: tuple[tuple[str, float], ...]
    max_level: int
    impl_phase: int = 1

    @classmethod
    def from_content(cls, w, max_level: int) -> WeaponDef:
        return cls(w.id, w.kind, w.rarity, tuple(w.base.items()), tuple(w.per_level.items()), max_level, w.impl_phase)

    @property
    def card_id(self) -> str:
        return WEAPON_PREFIX + self.id

    def at(self, level: int) -> dict[str, float]:
        """Values at a level (1 = just picked)."""
        values = dict(self.base)
        for key, step in self.per_level:
            values[key] = values[key] + step * (level - 1)
        return values


@dataclass(slots=True)
class WeaponState:
    """Runtime state of one weapon of one player."""

    weapon: str
    level: int = 1
    cooldown: float = 0.0
    ux: float = 1.0  # orbit: direction of the first orbiter (unit vector, rotated each tick)
    uy: float = 0.0
    hit_ready: dict[int, int] = field(default_factory=dict)  # orbit: enemy id -> tick it can be stung again


@dataclass(slots=True)
class Bomb:
    """A lobbed weapon shot in flight; bursts at (tx, ty) when `delay` runs out."""

    owner: int
    weapon: str
    x: float  # start
    y: float
    tx: float
    ty: float
    delay: float
    flight: float
    radius: float
    damage: float
    crit: bool


def fan_directions(dx: float, dy: float, count: int, spread_deg: float) -> list[tuple[float, float]]:
    """`count` unit vectors spread evenly over `spread_deg` around (dx, dy); 360 means a full ring."""
    if count <= 0:
        return []
    if spread_deg >= 360.0:
        step, start = TAU / count, 0.0
    elif count == 1:
        return [(dx, dy)]
    else:
        spread = spread_deg / 360.0 * TAU
        step, start = spread / (count - 1), -spread / 2.0
    out = []
    for k in range(count):
        c, s = cos_sin(start + step * k)
        out.append((dx * c - dy * s, dx * s + dy * c))
    return out


def orbit_positions(st: WeaponState, cx: float, cy: float, count: int, radius: float) -> list[tuple[float, float]]:
    out = []
    for k in range(count):
        c, s = cos_sin(TAU * k / count) if k else (1.0, 0.0)
        out.append((cx + (st.ux * c - st.uy * s) * radius, cy + (st.ux * s + st.uy * c) * radius))
    return out


def rotate(st: WeaponState, turns: float) -> None:
    """Turn the orbit by `turns` full circles and renormalise so rounding does not shrink it."""
    c, s = cos_sin(TAU * turns)
    x, y = st.ux * c - st.uy * s, st.ux * s + st.uy * c
    d = math.sqrt(x * x + y * y)
    st.ux, st.uy = x / d, y / d
