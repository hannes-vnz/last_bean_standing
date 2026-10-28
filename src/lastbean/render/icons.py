"""Pixel icons for weapons, upgrades and items (Paket F), drawn in code at 12 x 12 canvas pixels.

Each icon is an 8 x 8 symbol for what the thing does (sword = damage, heart = HP, flame = burn, ...)
on a background colour by category, framed in its rarity colour. An upgrade or item uses the
symbol of its first stat and a small corner mark for a second one, so similar ones stay apart.
"""

from __future__ import annotations

import pygame

SIZE = 12

GLYPHS = {
    "sword": ["......##", ".....###", "....###.", "#..###..", ".####...", "..##....", ".#.##...", "#......."],
    "chevrons": ["#...#...", ".#...#..", "..#...#.", "...#...#", "..#...#.", ".#...#..", "#...#...", "........"],
    "crosshair": ["...#....", ".#####..", ".#.#.#..", "#######.", ".#.#.#..", ".#####..", "...#....", "........"],
    "star": ["...##...", "...##...", "########", ".######.", "..####..", ".##..##.", ".#....#.", "........"],
    "heart": [".##..##.", "########", "########", "########", ".######.", "..####..", "...##...", "........"],
    "shield": ["########", "#.####.#", "#.####.#", "########", ".######.", ".######.", "..####..", "...##..."],
    "boot": ["..###...", "..###...", "..###...", "..###...", "..####..", "..#####.", "########", "########"],
    "magnet": ["##....##", "##....##", "##....##", "##....##", "##....##", ".##..##.", "..####..", "........"],
    "book": [".######.", "#......#", "#.####.#", "#......#", "#.####.#", "#......#", ".######.", "........"],
    "clover": [".##..##.", "########", ".######.", "..####..", ".######.", "########", ".##.#.#.", "....#..."],
    "arrow": ["....#...", "....##..", "#######.", "########", "#######.", "....##..", "....#...", "........"],
    "twin": [".#....#.", "###..###", ".#....#.", ".#....#.", ".#....#.", ".#....#.", ".#....#.", "........"],
    "plus": ["...##...", "...##...", "########", "########", "...##...", "...##...", "........", "........"],
    "crown": ["#..##..#", "##.##.##", "########", "########", "########", "........", "########", "........"],
    "root": ["...##...", "...##...", "...##...", "..####..", ".##..##.", "##.##.##", "#..##..#", "........"],
    "spikes": ["#..#..#.", "#..#..#.", "##.##.##", "########", "########", "........", "........", "........"],
    "drop": ["...#....", "..###...", "..###...", ".#####..", ".#####..", ".#####..", "..###...", "........"],
    "hourglass": ["########", ".#....#.", "..#..#..", "...##...", "..#..#..", ".#....#.", "########", "........"],
    "bomb": ["......#.", ".....#..", "..###...", ".#####..", "#######.", "#######.", ".#####..", "..###..."],
    "rings": ["..####..", ".#....#.", "#..##..#", "#.#..#.#", "#.#..#.#", "#..##..#", ".#....#.", "..####.."],
    "flame": ["...#....", "..##....", "..###...", ".#####..", ".##.##..", "##...##.", ".##.##..", "..###..."],
    "snow": ["#..#..#.", ".#.#.#..", "..###...", "#######.", "..###...", ".#.#.#..", "#..#..#.", "........"],
    "bolt": ["....##..", "...##...", "..##....", ".######.", "...##...", "..##....", ".##.....", "#......."],
    "zigzag": ["#.......", ".#....#.", "..#..#.#", "...##...", "..#..#..", ".#....#.", "#......#", "........"],
    "skull": [".######.", "########", "#..##..#", "########", ".######.", ".#.##.#.", ".######.", "........"],
    "battery": ["..####..", ".######.", ".#....#.", ".######.", ".######.", ".######.", ".######.", "........"],
    "feather": ["......##", ".....###", "....###.", "...###..", "..###...", ".#.#....", "#.......", "........"],
    "sprout": ["##....##", "###..###", ".##..##.", "...##...", "...##...", "...##...", "..####..", "........"],
    "seed": ["..###...", ".#####..", "#######.", "#######.", ".#####..", "..###...", "........", "........"],
    "clock": ["..####..", ".#.#..#.", "#..#...#", "#..###.#", "#......#", ".#....#.", "..####..", "........"],
    "dice": ["########", "#.#..#.#", "########", "#..##..#", "########", "#.#..#.#", "########", "........"],
    "cross": ["##....##", ".##..##.", "..####..", "...##...", "..####..", ".##..##.", "##....##", "........"],
    "ball": ["..####..", ".######.", "########", "########", "########", ".######.", "..####..", "........"],
    "burst": ["#.....#.", ".#...#..", "..#.#...", "...#....", "..#.#...", ".#...#..", "#.....#.", "........"],
    # weapons
    "bow": ["..###...", ".#...#..", "#.....#.", "#######.", "#.....#.", ".#...#..", "..###...", "........"],
    "thorn": ["#.......", ".#.#....", "..#.....", "...#.#..", "..#.#...", ".....#.#", "......#.", ".......#"],
    "puff": ["#.#.#.#.", ".#####..", "#######.", ".#####..", "#######.", ".#####..", "#.#.#.#.", "...#...."],
    "cloud": ["........", "..###...", ".#####..", "#######.", "########", ".######.", "........", "........"],
    "bee": [".#..#...", "..##....", "#.##.#..", "######..", "#.##.#..", "######..", ".####...", "........"],
    "sun": ["#..#..#.", ".#####..", "##...##.", "##...##.", "##...##.", ".#####..", "#..#..#.", "........"],
    "pumpkin": ["...#....", "..##....", ".######.", "##.##.##", "##.##.##", "##.##.##", ".######.", "........"],
}

STAT_GLYPH = {
    "damage_pct": "sword", "attack_speed_pct": "chevrons", "range_pct": "crosshair", "crit_chance_pct": "star",
    "crit_mult_add_pct": "burst", "max_hp_flat": "heart", "max_hp_pct": "heart", "damage_taken_pct": "shield",
    "move_speed_pct": "boot", "pickup_radius_pct": "magnet", "extra_attacks": "twin", "pierce_add": "arrow",
    "regen_per_s": "plus", "xp_gain_pct": "book", "gold_gain_pct": "seed", "luck": "clover", "cooldown_pct": "clock",
    "elite_damage_pct": "crown", "standing_damage_pct": "root", "thorns_flat": "spikes", "thorns_pct": "spikes",
    "heal_per_kill": "drop", "i_frames_pct": "hourglass", "explode_on_kill_pct": "bomb",
    "heal_orb_chance_pct": "heart", "area_pct": "rings", "projectile_size_pct": "ball", "projectile_speed_pct": "arrow",
    "dodge_chance_pct": "feather", "flat_damage_reduction": "shield", "rerolls": "dice", "banishes": "cross",
    "ignite_chance_pct": "flame", "chill_slow_pct": "snow", "poison_pct_per_s": "drop", "shock_chance_pct": "bolt",
    "bounce_add": "zigzag", "execute_damage_pct": "skull", "lifesteal_pct": "drop", "shield_flat": "shield",
    "low_hp_damage_pct": "heart", "overcharge_pct": "battery", "explosive_hit_pct": "bomb", "aura_dps": "rings",
    "elemental_damage_pct": "bolt", "revives": "sprout", "kill_haste_max_pct": "chevrons",
    "shrapnel_chance_pct": "burst",
}  # fmt: skip
WEAPON_GLYPH = {"fan": "thorn", "nova": "sun", "aura": "cloud", "orbit": "bee", "lobbed": "pumpkin"}
WEAPON_ID_GLYPH = {"dandelion": "puff"}

# Background by what a bonus is about (pastel), glyph in white with an ink shadow.
OFFENSE, DEFENSE, UTILITY = (238, 128, 150), (120, 168, 232), (110, 200, 160)
ELEMENT, WEAPON = (176, 136, 232), (240, 178, 90)
CATEGORY = {
    **{k: DEFENSE for k in ("max_hp_flat", "max_hp_pct", "damage_taken_pct", "regen_per_s", "thorns_flat", "thorns_pct",
                            "heal_per_kill", "i_frames_pct", "heal_orb_chance_pct", "dodge_chance_pct",
                            "flat_damage_reduction", "lifesteal_pct", "shield_flat", "revives")},
    **{k: UTILITY for k in ("move_speed_pct", "pickup_radius_pct", "xp_gain_pct", "gold_gain_pct", "luck",
                            "cooldown_pct", "rerolls", "banishes")},
    **{k: ELEMENT for k in ("ignite_chance_pct", "chill_slow_pct", "poison_pct_per_s", "shock_chance_pct",
                            "elemental_damage_pct")},
}  # fmt: skip


class IconBank:
    """Builds and caches icon surfaces. Needs the content's upgrades, items and weapons."""

    def __init__(self, content, ink: tuple[int, int, int], rarity_colors: dict[str, tuple[int, int, int]]) -> None:
        self.ink = ink
        self.rarity_colors = rarity_colors
        self._cache: dict[tuple[str, str], pygame.Surface] = {}
        self._spec: dict[str, tuple[str, tuple[int, int, int], str | None, str]] = {}
        for u in content.upgrades:
            stats = [e["stat"] for e in u.effects if "stat" in e]
            self._spec[u.id] = self._stat_spec(stats, u.rarity)
        for i in content.items:
            self._spec["item:" + i.id] = self._stat_spec([stat for stat, _ in i.effects], i.rarity)
        for w in content.weapons:
            glyph = WEAPON_ID_GLYPH.get(w.id, WEAPON_GLYPH.get(w.kind, "sword"))
            self._spec["weapon:" + w.id] = (glyph, WEAPON, None, w.rarity)
        self._spec["weapon:start"] = ("bow", WEAPON, None, "common")

    @staticmethod
    def _stat_spec(stats: list[str], rarity: str) -> tuple[str, tuple[int, int, int], str | None, str]:
        first = stats[0] if stats else "damage_pct"
        mark = STAT_GLYPH.get(stats[1]) if len(stats) > 1 else None
        return STAT_GLYPH.get(first, "star"), CATEGORY.get(first, OFFENSE), mark, rarity

    def get(self, key: str, tier: str | None = None) -> pygame.Surface:
        """Icon for an upgrade id, "item:<id>", "weapon:<id>" or "weapon:start"; `tier` overrides the frame colour."""
        spec = self._spec.get(key, ("star", OFFENSE, None, "common"))
        tier = tier or spec[3]
        surf = self._cache.get((key, tier))
        if surf is None:
            surf = self._build(*spec[:3], tier)
            self._cache[(key, tier)] = surf
        return surf

    def _build(self, glyph: str, bg: tuple[int, int, int], mark: str | None, tier: str) -> pygame.Surface:
        s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
        frame = self.rarity_colors.get(tier, (236, 236, 236))
        s.fill(self.ink, (1, 0, SIZE - 2, SIZE))
        s.fill(self.ink, (0, 1, SIZE, SIZE - 2))
        s.fill(frame, (1, 1, SIZE - 2, SIZE - 2))
        s.fill(bg, (2, 2, SIZE - 4, SIZE - 4))
        rows = GLYPHS.get(glyph, GLYPHS["star"])
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    if y + 1 < 8 and rows[y + 1][x] != "#":
                        s.set_at((2 + x, 3 + y), _shade(bg))  # little drop shadow under the glyph
                    s.set_at((2 + x, 2 + y), (255, 255, 255))
        if mark:  # second stat: a 2 x 2 dot in the corner, coloured by its category
            s.fill(self.ink, (SIZE - 4, SIZE - 4, 3, 3))
            s.fill((255, 240, 160), (SIZE - 3, SIZE - 3, 1, 1))
        return s


def _shade(c: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(int(v * 0.65) for v in c)
