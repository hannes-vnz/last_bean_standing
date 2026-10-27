"""Time-based difficulty: wave budget, enemy scaling, XP curve and biome lookup.

All coefficients come from `data/balance.json` (`budget`, `hp_mult`, `damage_mult`,
`speed_mult`, `xp_to_next`). m = minutes since run start, w = wave number.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scaling:
    budget: tuple[float, float, float]  # base, linear, quadratic in w
    hp: tuple[float, float]  # linear, quadratic in m
    damage: tuple[float, float]
    speed: tuple[float, float]  # linear in m, cap
    xp_to_next: tuple[float, float, float]  # base, linear, quadratic in level
    # Co-op hook (DESIGN.md section 18): extra budget per additional player. Value still open, 0 = off.
    budget_per_extra_player: float = 0.0

    @classmethod
    def from_content(cls, content) -> Scaling:
        b = content.balance.raw
        return cls(
            budget=(b["budget"]["base"], b["budget"]["linear"], b["budget"]["quadratic"]),
            hp=(b["hp_mult"]["linear"], b["hp_mult"]["quadratic"]),
            damage=(b["damage_mult"]["linear"], b["damage_mult"]["quadratic"]),
            speed=(b["speed_mult"]["linear"], b["speed_mult"]["cap"]),
            xp_to_next=(b["xp_to_next"]["base"], b["xp_to_next"]["linear"], b["xp_to_next"]["quadratic"]),
        )

    def wave_budget(self, wave: int, difficulty: float = 1.0, player_count: int = 1) -> float:
        base, lin, quad = self.budget
        coop = 1.0 + self.budget_per_extra_player * (player_count - 1)
        return (base + lin * wave + quad * wave * wave) * difficulty * coop

    def hp_mult(self, minutes: float) -> float:
        lin, quad = self.hp
        return 1.0 + lin * minutes + quad * minutes * minutes

    def damage_mult(self, minutes: float) -> float:
        lin, quad = self.damage
        return 1.0 + lin * minutes + quad * minutes * minutes

    def speed_mult(self, minutes: float) -> float:
        lin, cap = self.speed
        return min(1.0 + lin * minutes, cap)

    def xp_needed(self, level: int) -> float:
        base, lin, quad = self.xp_to_next
        return base + lin * level + quad * level * level


@dataclass(frozen=True, slots=True)
class BiomeArea:
    id: str
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


def biome_areas_from_content(content) -> tuple[BiomeArea, ...]:
    t = content.balance.tile_px
    return tuple(BiomeArea(b.id, b.rect_tiles[0] * t, b.rect_tiles[1] * t, b.rect_tiles[2] * t, b.rect_tiles[3] * t)
                 for b in content.biomes)  # fmt: skip


def biome_at(areas: tuple[BiomeArea, ...], x: float, y: float) -> str | None:
    """Smallest area containing the point, so the central clearing wins over the quadrants."""
    best, best_size = None, float("inf")
    for a in areas:
        if a.contains(x, y) and a.w * a.h < best_size:
            best, best_size = a.id, a.w * a.h
    return best
