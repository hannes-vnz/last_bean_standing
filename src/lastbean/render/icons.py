"""Icons for weapons, upgrades and items, 20 x 20 canvas pixels, in a frame of their rarity colour.

Weapons and items are 16 x 16 pixel drawings from assets/sprites/icons.json (tools/sprites/items.py).
Upgrades are books ("Bücher" of a stat): a cover in the colour of the stat's category with the stat's
8 x 8 symbol on it (sword = damage, heart = HP, flame = burn, ...). The frame is the rarity colour with
a light and a dark edge; the slot behind the picture is dark, tinted by the rarity.
"""

from __future__ import annotations

import json

import pygame

from .sprites import ASSETS_DIR

SIZE = 20
ART = 16

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
        self._cache: dict[tuple, pygame.Surface] = {}
        self._art = _load_art()
        self._rarity: dict[str, str] = {"weapon:start": "common"}
        self._tome: dict[str, tuple[str, tuple[int, int, int], str | None]] = {}
        for u in content.upgrades:
            stats = [e["stat"] for e in u.effects if "stat" in e]
            first = stats[0] if stats else "damage_pct"
            mark = STAT_GLYPH.get(stats[1]) if len(stats) > 1 else None
            self._tome[u.id] = (STAT_GLYPH.get(first, "star"), CATEGORY.get(first, OFFENSE), mark)
            self._rarity[u.id] = u.rarity
        for i in content.items:
            self._rarity["item:" + i.id] = i.rarity
        for w in content.weapons:
            self._rarity["weapon:" + w.id] = w.rarity

    def get(self, key: str, tier: str | None = None, scale: int = 1) -> pygame.Surface:
        """Icon for an upgrade id, "item:<id>", "weapon:<id>" or "weapon:start". `tier` sets the frame colour
        (default: the thing's own rarity); `scale` enlarges it pixel-exact (cards, chest spinner)."""
        tier = tier or self._rarity.get(key, "common")
        surf = self._cache.get((key, tier, scale))
        if surf is None:
            surf = self._cache.get((key, tier, 1))
            if surf is None:
                surf = self._build(key, tier)
                self._cache[(key, tier, 1)] = surf
            if scale != 1:
                surf = pygame.transform.scale(surf, (SIZE * scale, SIZE * scale))
                self._cache[(key, tier, scale)] = surf
        return surf

    def art(self, key: str) -> pygame.Surface:
        """Just the 16 x 16 picture, without a frame."""
        surf = self._cache.get((key, "art", 0))
        if surf is None:
            surf = self._art.get(key) or self._tome_art(*self._tome.get(key, ("star", OFFENSE, None)))
            self._cache[(key, "art", 0)] = surf
        return surf

    def _build(self, key: str, tier: str) -> pygame.Surface:
        s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
        frame = self.rarity_colors.get(tier, (180, 180, 180))
        hi = tuple(min(255, v + 70) for v in frame)
        lo = tuple(v * 3 // 5 for v in frame)
        slot = tuple((v * 2 + d * 5) // 7 for v, d in zip(frame, (44, 32, 53), strict=True))
        s.fill(self.ink, (1, 0, SIZE - 2, SIZE))
        s.fill(self.ink, (0, 1, SIZE, SIZE - 2))
        s.fill(frame, (1, 1, SIZE - 2, SIZE - 2))
        s.fill(hi, (1, 1, SIZE - 2, 1))  # light top-left edge
        s.fill(hi, (1, 1, 1, SIZE - 2))
        s.fill(lo, (1, SIZE - 2, SIZE - 2, 1))  # dark bottom-right edge
        s.fill(lo, (SIZE - 2, 1, 1, SIZE - 2))
        s.fill(slot, (3, 3, SIZE - 6, SIZE - 6))
        s.fill(tuple(min(255, v + 18) for v in slot), (3, 3, SIZE - 6, (SIZE - 6) // 2))  # soft light from above
        s.blit(self.art(key), ((SIZE - ART) // 2, (SIZE - ART) // 2))
        return s

    def _tome_art(self, glyph: str, cover: tuple[int, int, int], mark: str | None) -> pygame.Surface:
        """A book: coloured cover, darker spine, white pages, the stat's symbol in white on the cover."""
        s = pygame.Surface((ART, ART), pygame.SRCALPHA)
        ink, dark = self.ink, tuple(v * 2 // 3 for v in cover)
        s.fill(ink, (2, 1, 13, 15))
        s.fill((250, 244, 230), (12, 3, 2, 12))  # pages
        s.fill(cover, (3, 2, 10, 13))
        s.fill(dark, (3, 2, 2, 13))  # spine
        s.fill(tuple(min(255, v + 45) for v in cover), (5, 2, 8, 1))
        rows = GLYPHS.get(glyph, GLYPHS["star"])
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    s.set_at((5 + x, 5 + y), (255, 255, 255))
        s.fill((255, 212, 94), (5, 3, 7, 1))  # golden title band
        if mark:
            s.fill(ink, (12, 12, 4, 4))
            s.fill((255, 240, 160), (13, 13, 2, 2))
        return s


def _load_art() -> dict[str, pygame.Surface]:
    try:
        raw = json.loads((ASSETS_DIR / "sprites" / "icons.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for key, spec in raw.items():
        surf = pygame.Surface((spec["w"], spec["h"]), pygame.SRCALPHA)
        pal = {k: _hex(v) for k, v in spec["pal"].items()}
        for y, row in enumerate(spec["rows"]):
            for x, ch in enumerate(row):
                if ch != ".":
                    surf.set_at((x, y), (*pal[ch], 255))
        out[key] = surf
    return out


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
