"""Simulation entities and the stats they are built from.

Stats are plain numbers copied from content (`from_content`), so the simulation
never reads files and stays usable without the data package.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Collision radius of a player in world units. Not in data/ yet (sprite 16 px = 32 units).
PLAYER_RADIUS = 12.0
PROJECTILE_RADIUS = 4.0


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
        )


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
    offer: tuple[str, ...] = ()

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


@dataclass(slots=True)
class XpOrb:
    x: float
    y: float
    value: float
