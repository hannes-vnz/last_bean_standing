"""Run economy (Paket C): seeds (the run's gold), seed chests on the map, breakable pots, items.

All numbers come from `data/items.json` (`economy`); items are passive and stack. Placement
of chests and pots uses its own random stream derived from the run seed, so it differs per
run but never shifts the main simulation stream.
"""

from __future__ import annotations

from dataclasses import dataclass

from .arena import ObstacleMap
from .rng import Rng
from .upgrades import RARITIES


@dataclass(frozen=True, slots=True)
class ItemDef:
    id: str
    rarity: str
    effects: tuple[tuple[str, float], ...]  # (stat, value per stack)

    @classmethod
    def from_content(cls, it) -> ItemDef:
        return cls(it.id, it.rarity, it.effects)


@dataclass(frozen=True, slots=True)
class Economy:
    drop_pct: float
    normal_value: int
    elite_value: int
    boss_value: int
    chest_count: int
    price_start: float
    price_growth_pct: float
    min_rarity: tuple[tuple[str, str], ...]  # (chest kind, min rarity)
    pot_count: int
    pot_contents: tuple[tuple[str, float], ...]
    pot_seeds: tuple[int, int]
    heal_orb_hp: float
    rerolls: int
    banishes: int

    @classmethod
    def from_content(cls, content) -> Economy:
        e = content.economy
        cur, ch, pots = e["currency"], e["chests"], e["pots"]
        return cls(
            float(cur["normal_drop_pct"]),
            int(cur["normal_value"]),
            int(cur["elite_value"]),
            int(cur["boss_value"]),
            int(ch["count"]),
            float(ch["price_start"]),
            float(ch["price_growth_pct"]),
            tuple(ch["item_min_rarity"].items()),
            int(pots["count"]),
            tuple((k, float(v)) for k, v in pots["contents"].items()),
            (int(pots["seeds_min"]), int(pots["seeds_max"])),
            float(e["heal_orb_hp"]),
            int(e["rerolls_per_run"]),
            int(e["banishes_per_run"]),
        )

    def chest_price(self, opened: int) -> int:
        return int(round(self.price_start * (1.0 + self.price_growth_pct / 100.0) ** opened))


@dataclass(slots=True)
class MapChest:
    x: float
    y: float
    kind: str  # "map" (costs seeds), "elite", "boss" (free)


@dataclass(slots=True)
class Pot:
    x: float
    y: float


def scatter(
    rng: Rng, count: int, arena_w: float, arena_h: float, obstacles: ObstacleMap,
    avoid: tuple[float, float], avoid_radius: float, margin: float = 64.0,
) -> list[tuple[float, float]]:  # fmt: skip
    """`count` free spots spread over the arena: not inside obstacles, not right at the start."""
    out: list[tuple[float, float]] = []
    tries = 0
    while len(out) < count and tries < count * 50:
        tries += 1
        x, y = rng.uniform(margin, arena_w - margin), rng.uniform(margin, arena_h - margin)
        if (x - avoid[0]) ** 2 + (y - avoid[1]) ** 2 < avoid_radius**2:
            continue
        if obstacles.push_out(x, y, 20.0) != (x, y):
            continue
        out.append((x, y))
    return out


def roll_item(rng: Rng, items: tuple[ItemDef, ...], weights: dict[str, float], min_rarity: str, luck: float,
              luck_shift: float) -> ItemDef | None:  # fmt: skip
    """Weighted by rarity (luck moves weight up), never below `min_rarity`. Items stack, so all stay in the pool."""
    floor = RARITIES.index(min_rarity)
    pool = [i for i in items if RARITIES.index(i.rarity) >= floor]
    if not pool:
        return None
    w = [weights[i.rarity] * (1.0 + max(0.0, luck) * luck_shift * RARITIES.index(i.rarity)) for i in pool]
    r = rng.random() * sum(w)
    for item, weight in zip(pool, w, strict=True):
        if r < weight:
            return item
        r -= weight
    return pool[-1]


def pick_weighted(rng: Rng, options: tuple[tuple[str, float], ...]) -> str:
    total = sum(w for _, w in options)
    r = rng.random() * total
    for name, w in options:
        if r < w:
            return name
        r -= w
    return options[-1][0]
