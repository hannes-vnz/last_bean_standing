"""Simulation entities and the stats they are built from.

Stats are plain numbers copied from content (`from_content`), so the simulation
never reads files and stays usable without the data package.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .tuning import BOSS_RADIUS, PLAYER_RADIUS, PROJECTILE_RADIUS  # noqa: F401  (re-exported)


@dataclass(frozen=True, slots=True)
class CharacterStats:
    id: str
    hp: int
    speed: float
    damage: float
    attack_rate: float
    range: float
    crit_chance_pct: float
    crit_mult: float
    projectile_speed: float
    pierce: int
    i_frames_s: float
    pickup_radius: float
    tags: tuple[str, ...] = ()
    passive: tuple[tuple[str, float, float], ...] = ()  # (stat, value, threshold_px) of the passive ability
    active_id: str = ""
    active_cooldown_s: float = 0.0

    @classmethod
    def from_content(cls, content, character_id: str) -> CharacterStats:
        c = content.character(character_id)
        base = content.balance.raw["player_base"]
        return cls(
            id=c.id,
            hp=c.hp,
            speed=float(c.speed),
            damage=float(c.damage),
            attack_rate=c.attack_rate,
            range=float(c.range),
            crit_chance_pct=float(c.crit_chance),
            crit_mult=c.crit_mult,
            projectile_speed=float(c.weapon.projectile_speed),
            pierce=c.weapon.pierce,
            i_frames_s=float(base["i_frames_s"]),
            pickup_radius=float(base["pickup_radius_px"]),
            tags=c.tags,
            passive=tuple(
                (e["stat"], float(e.get("value", 0.0)), float(e.get("threshold_px", 0.0)))
                for e in c.passive.effects
                if "stat" in e
            ),
            active_id=c.active.id,
            active_cooldown_s=float(c.active.cooldown_s or 0.0),
        )


@dataclass(frozen=True, slots=True)
class MobStats:
    id: str
    behavior: str
    hp: float
    speed: float
    damage: float
    radius: float
    cost: float = 1.0
    xp: float = 1.0
    min_time_s: float = 0.0
    biome_weights: tuple[tuple[str, float], ...] = ()
    impl_phase: int = 1
    group_size: int = 1
    keep_distance: float = 0.0
    shot_interval: float = 0.0

    @classmethod
    def from_content(cls, content, mob_id: str) -> MobStats:
        m = content.mob(mob_id)
        return cls(
            m.id,
            m.behavior,
            float(m.hp),
            float(m.speed),
            float(m.damage),
            float(m.radius),
            float(m.cost),
            float(m.xp),
            float(m.min_time_s),
            tuple(m.biome_weights.items()),
            m.impl_phase,
            int(m.extra.get("group_size", 1)),
            float(m.extra.get("keep_distance_px", 0.0)),
            float(m.extra.get("shot_interval_s", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class BossStats:
    id: str
    name: str
    hp: float
    speed: float
    damage: float
    radius: float
    biome: str | None
    spawn_time_s: float
    phase_thresholds: tuple[int, ...]  # at_hp_pct of each phase, descending

    @classmethod
    def from_content(cls, content, boss_id: str) -> BossStats:
        b = content.boss(boss_id)
        return cls(
            b.id,
            b.name,
            float(b.hp),
            float(b.speed),
            float(b.damage),
            BOSS_RADIUS,
            b.biome,
            float(b.spawn_time_s or 0),
            tuple(sorted((p["at_hp_pct"] for p in b.phases), reverse=True)),
        )


@dataclass(frozen=True, slots=True)
class EliteRules:
    every_n_waves: int
    hp_mult: float
    damage_mult: float
    xp_mult: float
    size_mult: float
    affixes_by_minute: tuple[tuple[float, int], ...]  # (from minute, affix count), ascending
    affix_ids: tuple[str, ...]
    chest_min_rarity: str

    @classmethod
    def from_content(cls, content) -> EliteRules:
        e = content.elite
        return cls(
            content.balance.raw["elite_every_n_waves"],
            float(e["hp_mult"]),
            float(e["damage_mult"]),
            float(e["xp_mult"]),
            float(e["size_mult"]),
            tuple(sorted((float(k), int(v)) for k, v in e["affixes_per_elite_by_minute"].items())),
            tuple(a["id"] for a in e["affixes"]),
            content.balance.raw["elite_chest_min_rarity"],
        )

    def affix_count(self, minutes: float) -> int:
        count = 0
        for start, n in self.affixes_by_minute:
            if minutes >= start:
                count = n
        return count


@dataclass(slots=True)
class Stats:
    """Current combat stats of a player: character base values plus upgrades."""

    max_hp: float
    speed: float
    damage: float
    attack_rate: float
    range: float
    crit_chance_pct: float
    crit_mult: float
    pierce: int
    extra_attacks: int
    pickup_radius: float
    regen_per_s: float
    damage_taken_mult: float
    far_damage_pct: float = 0.0  # extra damage on targets farther than far_threshold
    far_threshold: float = 0.0


@dataclass(slots=True)
class Player:
    player_id: int
    x: float
    y: float
    hp: float
    stats: Stats
    vx: float = 0.0
    vy: float = 0.0
    standing: bool = True
    alive: bool = True
    shot_cooldown: float = 0.0
    i_frames: float = 0.0
    kills: int = 0
    level: int = 1
    xp: float = 0.0
    upgrades: dict[str, int] = field(default_factory=dict)
    pending_levels: int = 0
    pending_chests: list[str] = field(default_factory=list)  # min rarity of each unopened chest
    offer: tuple[str, ...] = ()
    offer_source: str = ""  # "level" or "chest"
    slow_pct: float = 0.0
    damage_taken: float = 0.0
    ability_cooldown: float = 0.0

    @property
    def max_hp(self) -> float:
        return self.stats.max_hp


@dataclass(slots=True)
class Enemy:
    eid: int
    kind: str
    x: float
    y: float
    hp: float
    max_hp: float
    speed: float
    damage: float
    radius: float
    xp: float = 0.0
    behavior: str = "chaser"
    timer: float = 0.0
    keep_distance: float = 0.0
    shot_interval: float = 0.0
    elite: bool = False
    affixes: tuple[str, ...] = ()
    shield: float = 0.0
    shield_max: float = 0.0
    since_hit: float = 0.0
    boss: str | None = None
    phase: int = 0
    timers: list[float] = field(default_factory=list)  # boss pattern timers
    volley: int = 0


@dataclass(slots=True)
class Projectile:
    owner: int  # player_id
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    crit: bool
    ticks_left: int
    hits_left: int
    hit_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class HazardSpec:
    kind: str  # "poison", "grip", "explosion"
    radius: float
    delay: float = 0.0  # warning time before it becomes active
    duration: float = 0.0  # active time (0 = one burst)
    dps: float = 0.0
    burst: float = 0.0
    slow_pct: float = 0.0


@dataclass(slots=True)
class Hazard:
    spec: HazardSpec
    x: float
    y: float
    delay: float
    duration: float
    source: int  # enemy id that caused it


@dataclass(slots=True)
class EnemyShot:
    """Enemy projectile. Direct shots hit on contact and are stopped by trees;
    lobbed ones fly over everything and leave a hazard where they land."""

    x: float
    y: float
    vx: float
    vy: float
    damage: float
    ticks_left: int
    source: int
    lobbed: bool = False
    tx: float = 0.0
    ty: float = 0.0
    on_land: HazardSpec | None = None


@dataclass(slots=True)
class XpOrb:
    x: float
    y: float
    value: float
    magnet_to: int | None = None  # player id once a magnet pulls it


@dataclass(slots=True)
class Pickup:
    """Something lying on the map that is used up on touch (magnet; later gold, healing, ...)."""

    kind: str
    x: float
    y: float


@dataclass(slots=True)
class Chest:
    x: float
    y: float
    min_rarity: str
