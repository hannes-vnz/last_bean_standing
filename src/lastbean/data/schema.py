"""Typed, immutable views of the content in `data/*.json`.

Only fields the game logic relies on are typed. Free-form or not-yet-used parts
(effect lists, boss phases, descriptive texts) stay as plain mappings in `extra`
or dedicated fields and are typed once a milestone needs them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
IMPL_PHASES = (1, 2, 3)


@dataclass(frozen=True, slots=True)
class Balance:
    tick_hz: int
    wave_interval_s: int
    max_wave: int
    swarm_time_s: int
    max_alive_enemies: int
    arena_tiles: tuple[int, int]
    tile_px: int
    boss_waves: dict[int, str]
    mini_boss_times_s: tuple[int, ...]
    rarity_weights: dict[str, int]
    level_up_choices: int
    final_boss_id: str
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class Weapon:
    type: str
    pattern: str
    projectile_speed: int
    pierce: int
    aoe_radius: int
    text: str


@dataclass(frozen=True, slots=True)
class Ability:
    id: str
    name: str
    text: str
    cooldown_s: float | None = None
    effects: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class Character:
    id: str
    name: str
    title: str
    archetype: str
    hp: int
    speed: int
    damage: int
    attack_rate: float
    range: int
    crit_chance: int
    crit_mult: float
    weapon: Weapon
    passive: Ability
    active: Ability
    tags: tuple[str, ...]
    unlock_challenge: str | None
    impl_phase: int
    skins: tuple[str, ...]
    vfx: dict[str, str]


@dataclass(frozen=True, slots=True)
class Upgrade:
    id: str
    name: str
    rarity: str
    max_level: int
    tags: tuple[str, ...]
    text: str
    effects: tuple[dict[str, Any], ...]
    unlocked_at_start: bool
    unlock_challenge: str | None
    impl_phase: int


@dataclass(frozen=True, slots=True)
class Mob:
    id: str
    name: str
    behavior: str
    hp: int
    speed: int
    damage: int
    cost: float
    xp: float
    min_time_s: int
    biome_weights: dict[str, float]
    radius: int
    text: str
    impl_phase: int
    extra: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class Boss:
    id: str
    name: str
    hp: int
    speed: int
    damage: int
    biome: str | None
    spawn_wave: int | None
    spawn_time_s: int | None
    summon: str | None
    phases: tuple[dict[str, Any], ...]
    reward: str
    first_kill_challenge: str
    impl_phase: int
    extra: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class Biome:
    id: str
    name: str
    effect: str
    rect_tiles: tuple[int, int, int, int]
    text: str
    objects: tuple[dict[str, Any], ...]
    palette: dict[str, str | None]
    impl_phase: int
    extra: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class Condition:
    type: str
    stat: str | None
    op: str | None
    value: int | float | None
    extra: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Reward:
    type: str
    id: str
    stones: int


@dataclass(frozen=True, slots=True)
class Challenge:
    id: str
    text: str
    condition: Condition
    reward: Reward


@dataclass(frozen=True, slots=True)
class Skin:
    id: str
    character: str
    name: str
    tint: tuple[int, int, int]
    unlock_challenge: str


@dataclass(frozen=True, slots=True)
class Shrine:
    id: str
    name: str
    count: int
    channel_s: float
    radius_px: int
    difficulty_add: float
    impl_phase: int
    effect: str
    reward: str


@dataclass(frozen=True, slots=True)
class Mode:
    id: str
    name: str
    text: str
    hp_mult: float
    xp_mult: float
    score_mult: float
    unlock_challenge: str


@dataclass(frozen=True, slots=True)
class Style:
    name: str
    ink: str
    player: dict[str, str]
    enemy: dict[str, str]
    player_projectile: dict[str, str]
    enemy_projectile: dict[str, str]
    xp_orb: str
    heal_orb: str
    telegraph: str
    crit_text: str
    reaper: str
    flowers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkshopItem:
    id: str
    name: str
    effect: dict[str, Any]
    max_level: int
    base_cost: int
    text: str


@dataclass(frozen=True, slots=True)
class Shop:
    currency_id: str
    currency_name: str
    workshop: tuple[WorkshopItem, ...]
    run_packs_max_per_run: int
    run_packs: tuple[dict[str, Any], ...]
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    name: str
    rarity: str
    text: str
    effects: tuple[tuple[str, float], ...]  # (stat, value per stack)


@dataclass(frozen=True, slots=True)
class Stage:
    """One garden bed of a run (Paket F): own map, own enemy mix, a boss, then the gate or the flood."""

    id: str
    index: int
    name: str
    biome: str
    duration_s: int
    boss: str
    hp_mult: float
    damage_mult: float
    budget_mult: float
    tagline: str


@dataclass(frozen=True, slots=True)
class ExtraWeapon:
    """A weapon besides the character's own, picked from level-up cards (Paket C2)."""

    id: str
    name: str
    kind: str  # "fan", "nova", "aura", "orbit" or "lobbed"
    rarity: str
    text: str
    level_text: str
    base: dict[str, float]
    per_level: dict[str, float]
    impl_phase: int


@dataclass(frozen=True, slots=True)
class Content:
    balance: Balance
    characters: tuple[Character, ...]
    upgrades: tuple[Upgrade, ...]
    mobs: tuple[Mob, ...]
    bosses: tuple[Boss, ...]
    biomes: tuple[Biome, ...]
    challenges: tuple[Challenge, ...]
    skins: tuple[Skin, ...]
    shrines: tuple[Shrine, ...]
    modes: tuple[Mode, ...]
    style: Style
    shop: Shop
    elite: dict[str, Any] = field(repr=False)
    swarm: dict[str, Any] = field(repr=False)
    items: tuple[Item, ...] = ()
    economy: dict[str, Any] = field(default_factory=dict, repr=False)
    weapons: tuple[ExtraWeapon, ...] = ()
    weapon_slots: int = 1  # including the character's own weapon
    weapon_max_level: int = 1
    stages: tuple[Stage, ...] = ()
    flood: dict[str, Any] = field(default_factory=dict, repr=False)
    gate: dict[str, Any] = field(default_factory=dict, repr=False)
    stat_labels: dict[str, str] = field(default_factory=dict, repr=False)

    def character(self, cid: str) -> Character:
        return _by_id(self.characters, cid)

    def upgrade(self, uid: str) -> Upgrade:
        return _by_id(self.upgrades, uid)

    def mob(self, mid: str) -> Mob:
        return _by_id(self.mobs, mid)

    def boss(self, bid: str) -> Boss:
        return _by_id(self.bosses, bid)

    def biome(self, bid: str) -> Biome:
        return _by_id(self.biomes, bid)

    def challenge(self, cid: str) -> Challenge:
        return _by_id(self.challenges, cid)

    def item(self, iid: str) -> Item:
        return _by_id(self.items, iid)

    def weapon(self, wid: str) -> ExtraWeapon:
        return _by_id(self.weapons, wid)


def _by_id(items, item_id):
    for x in items:
        if x.id == item_id:
            return x
    raise KeyError(item_id)
