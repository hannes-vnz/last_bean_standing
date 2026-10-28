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
    # Passive ability: (stat, value, a, b) with a = threshold_px or radius_px, b = max_stacks or damage_pct
    passive: tuple[tuple[str, float, float, float], ...] = ()
    active_id: str = ""
    active_cooldown_s: float = 0.0
    weapon_pattern: str = "single"  # single, single_explosive, fan3, shockwave, chain_lightning
    aoe_radius: float = 0.0
    weapon_extra: tuple[tuple[str, float], ...] = ()  # chain_jumps, slow_pct, ignite_s, ... from characters.json
    # Every number of the passive by name (its stat carries its value), e.g. max_mines, crit_mult (Paket J).
    passive_extra: tuple[tuple[str, float], ...] = ()

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
                (
                    e["stat"],
                    float(e.get("value", 0.0)),
                    float(e.get("threshold_px", e.get("radius_px", 0.0))),
                    float(e.get("max_stacks", e.get("damage_pct", 0.0))),
                )
                for e in c.passive.effects
                if "stat" in e
            ),
            active_id=c.active.id,
            active_cooldown_s=float(c.active.cooldown_s or 0.0),
            weapon_pattern=c.weapon.pattern,
            aoe_radius=float(c.weapon.aoe_radius),
            weapon_extra=tuple((k, float(v)) for k, v in c.weapon.extra.items() if isinstance(v, (int, float))),
            passive_extra=tuple(
                (k, float(v))
                for e in c.passive.effects
                for k, v in ({e["stat"]: e.get("value", 0.0)} | e).items()
                if k not in ("stat", "value") or k == e.get("stat")
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ),
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
    telegraph_s: float = 0.0  # charger: aim time before the dash
    charge_s: float = 0.0
    charge_speed: float = 0.0
    recovery_s: float = 0.0
    explosion_radius: float = 0.0  # exploder
    projectile_speed: float = 0.0  # ranged_direct

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
            float(m.extra.get("telegraph_s", 0.0)),
            float(m.extra.get("charge_s", 0.0)),
            float(m.extra.get("charge_speed", 0.0)),
            float(m.extra.get("recovery_s", 0.0)),
            float(m.extra.get("explosion_radius", 0.0)),
            float(m.extra.get("projectile_speed", 0.0)),
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
    spawn_time_s: float  # seconds after the start of its garden bed
    phase_thresholds: tuple[int, ...]  # at_hp_pct of each phase, descending
    summon_mob: str = ""

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
            str(b.extra.get("summon_mob", "")),
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
    xp_mult: float = 1.0
    gold_mult: float = 1.0
    luck: float = 0.0
    cooldown_mult: float = 1.0
    elite_damage_mult: float = 1.0
    standing_damage_mult: float = 1.0
    thorns: float = 0.0
    heal_per_kill: float = 0.0
    i_frames_mult: float = 1.0
    explode_on_kill_pct: float = 0.0
    # Paket F
    heal_orb_chance_pct: float = 0.0
    area_mult: float = 1.0
    thorns_pct: float = 0.0
    projectile_size_mult: float = 1.0
    projectile_speed_mult: float = 1.0
    dodge_chance_pct: float = 0.0
    armor: float = 0.0
    ignite_chance_pct: float = 0.0
    chill_slow_pct: float = 0.0
    poison_pct_per_s: float = 0.0
    shock_chance_pct: float = 0.0
    bounces: int = 0
    execute_damage_pct: float = 0.0
    lifesteal_pct: float = 0.0
    shield: float = 0.0
    low_hp_damage_pct: float = 0.0
    overcharge_pct: float = 0.0
    explosive_hit_pct: float = 0.0
    aura_dps: float = 0.0
    elemental_mult: float = 1.0
    revives: int = 0
    kill_haste_max_pct: float = 0.0
    shrapnel_chance_pct: float = 0.0
    minions_add: int = 0  # "Gefolgschaft": extra ghosts (will-o'-wisps for other beans)
    orbit_blades: int = 0  # "Kreisende Klingen"
    # Character passives (Paket H)
    burning_damage_mult: float = 1.0  # Mira "Hitzewelle"
    nearby_damage_pct: float = 0.0  # Kaz "Nervenkitzel": per enemy close by ...
    nearby_radius: float = 0.0
    nearby_max: int = 0
    aura_slow_pct: float = 0.0  # Ysa "Frostaura"
    aura_slow_radius: float = 0.0
    strike_every: int = 0  # Vex "Statische Ladung": every n-th shot a lightning strike ...
    strike_damage_pct: float = 0.0


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
    shrine_mods: dict[str, float] = field(default_factory=dict)  # stacked shrine rewards
    shrines_activated: int = 0
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
    seeds: int = 0
    sparkles: int = 0  # Funkelsteine found in this run
    items: dict[str, int] = field(default_factory=dict)
    rerolls: int = 0
    banishes: int = 0
    banished: set[str] = field(default_factory=set)
    weapons: list = field(default_factory=list)  # WeaponState of each extra weapon, in pick order
    upgrade_power: dict[str, float] = field(default_factory=dict)  # summed card_tier_mult of every pick
    card_tiers: dict[str, str] = field(default_factory=dict)  # best rarity picked per card id (for the icon frame)
    offer_tiers: tuple[str, ...] = ()  # rarity rolled for each offered card
    haste_pct: float = 0.0  # "Blutrausch": attack speed from recent kills
    haste_t: float = 0.0
    overcharge_t: float = 0.0
    shield: float = 0.0
    shield_t: float = 0.0
    revives_used: int = 0
    aura_t: float = 0.0
    shots_fired: int = 0
    last_dx: float = 1.0  # last walking direction (dash ability)
    last_dy: float = 0.0
    inferno_t: float = 0.0  # active abilities that last a while
    still_t: float = 0.0  # seconds standing still (Aya)
    focus_t: float = 0.0  # Aya's "Fokus"
    ghosts_t: float = 0.0  # Thorn's "Totenruf"
    minion_t: float = 0.0  # Thorn's ghosts: attack timer
    minion_turn: int = 0  # which ghost attacks next
    mine_t: float = 0.0  # Orm's "Minenleger"
    gravity_t: float = 0.0  # "Schwerkraftbrunnen" timer
    lucky_t: float = 0.0  # ladybug luck: more damage for a while
    blades: object = None  # WeaponState of "Kreisende Klingen", made on first use
    storm_t: float = 0.0
    temp_shield: float = 0.0
    temp_shield_t: float = 0.0

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
    critter: str = ""  # golden_snail, gnome: a garden critter, not a pest (no contact damage, own behaviour)
    life: float = 0.0  # critters that run off after a while
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
    cursed: bool = False  # Fluchstein copy: its death gives a bonus card
    charge_state: int = 0  # dashers: 0 walk, 1 aim (warning line), 2 dash, 3 dazed
    charge_t: float = 0.0
    cdx: float = 0.0  # dash direction
    cdy: float = 0.0
    # Status effects from player hits (Paket F)
    poison_dps: float = 0.0
    poison_t: float = 0.0
    burn_dps: float = 0.0
    burn_t: float = 0.0
    chill_pct: float = 0.0
    chill_t: float = 0.0
    dot_owner: int = 0
    frost_stacks: int = 0


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
    weapon: str = ""  # extra weapon id, "" for the character's own
    radius: float = PROJECTILE_RADIUS
    bounces_left: int = 0
    procs: bool = True  # False for shrapnel: no chain reactions
    explode_r: float = 0.0  # Mira's fireball bursts on impact
    burn_pct: float = 0.0  # ... and sets the burst on fire (share of its damage per second)
    frost: bool = False  # Ysa's frost shot slows and, stacked, freezes
    turn: float = 0.0  # homing: how fast it turns towards the nearest enemy (radians per second, roughly)
    return_at: int = 0  # boomerang: turns back to its owner when ticks_left reaches this
    returning: bool = False
    flies: bool = False  # flies over obstacles (boomerangs, homing shots, turret spines)


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
    kind: str = "xp"  # "xp", "seeds" or "heal": all fly to the player the same way


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
