"""Headless simulation. Never imports pygame (tests/test_sim_has_no_pygame.py).

Scope so far:
- M2: stop-and-shoot, time-based wave budget, enemy scaling, XP orbs, level-up cards.
- M3: static obstacles from the biome data (forest trees block movement and projectiles).
- M4: all phase-1 mob behaviours (enemies.py), enemy projectiles and hazards, elites with
  affixes and chests every few waves, biome boss with phases and a boss chest.
- Paket C2: extra weapons from level-up cards (weapons.py), up to `weapon_slots` incl. the start weapon.
- Paket F: a run is three garden beds (stages). Each bed has its own map, a boss at 2:06 (stages.json) and, when its
  time runs out, the endless "Plagenflut". The boss opens a gate to the next bed; the last boss wins the run.

Determinism: only + - * / and sqrt (correctly rounded in IEEE 754), no trigonometry,
all randomness from `self.rng`, all iteration over lists in insertion order.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import NamedTuple

from .arena import Obstacle, ObstacleMap, obstacles_for_biome
from .economy import Economy, ItemDef, MapChest, Pot, pick_weighted, roll_item, scatter
from .enemies import BEHAVIORS, BOSS_BEHAVIORS, COMPASS_16, apply_affixes, damage_enemy, tick_affixes
from .entities import (
    BossStats,
    CharacterStats,
    EliteRules,
    Enemy,
    EnemyShot,
    Hazard,
    HazardSpec,
    MobStats,
    Pickup,
    Player,
    Projectile,
    XpOrb,
)
from .events import (
    AbilityUsed,
    BeamFired,
    BossKilled,
    BossSpawned,
    ChestDropped,
    ChestLocked,
    ChestOpened,
    EliteSpawned,
    EnemyHit,
    EnemyKilled,
    EnemySpawned,
    Event,
    FloodStarted,
    FloodWarning,
    FloodWave,
    GateOpened,
    HazardActivated,
    ItemGained,
    LevelUp,
    PickupCollected,
    PlayerDied,
    PlayerDodged,
    PlayerHit,
    PlayerRevived,
    PotBroken,
    ProjectileBlocked,
    RunEnded,
    RunStarted,
    SeedsCollected,
    ShotFired,
    ShrineActivated,
    StageStarted,
    SweepSwung,
    UpgradeChosen,
    UpgradeOffered,
    WaveStarted,
    WeaponPulse,
    Zap,
)
from .rng import Rng
from .score import RunResult, ScoreRules, compute_score
from .shrines import SHRINE_KINDS, Shrine, ShrineRules
from .spatial import SpatialHash
from .tuning import (
    ARROW_STORM_DAMAGE,
    ARROW_STORM_SHOTS,
    AURA_RADIUS,
    BOSS_MIN_SPAWN_DISTANCE,
    BOUNCE_DAMAGE,
    BOUNCE_RANGE,
    BULWARK_S,
    BULWARK_SHIELD,
    BURN_S,
    BURN_SHARE,
    CHALLENGE_LOW_HP_SHARE,
    CHEST_PICKUP_RADIUS,
    CHILL_S,
    COURAGE_MIN_RARITY,
    CURSE_CARD_RARITY,
    CURSE_MAX_COPIES,
    DASH_DISTANCE,
    DASH_I_FRAMES_S,
    DODGE_I_FRAMES_S,
    DOT_PULSE_TICKS,
    ELITE_SHRINE_COUNT,
    ENEMY_SHOT_RADIUS,
    EXECUTE_SHARE,
    EXPLOSIVE_HIT_RADIUS,
    EXTRA_ATTACK_DAMAGE,
    GATE_DELAY_S,
    GATE_OFFSET,
    GREED_XP_PCT,
    HOMING_RANGE,
    ICE_AGE_REACH,
    ICE_AGE_S,
    INFERNO_DPS_SHARE,
    INFERNO_RADIUS,
    INFERNO_S,
    KILL_EXPLOSION_DAMAGE,
    KILL_EXPLOSION_RADIUS,
    KILL_HASTE_PCT,
    KILL_HASTE_S,
    KNIFE_FAN_DEG,
    LOW_HP_SHARE,
    MAGNET_DROP_PCT,
    MAGNET_ORB_SPEED,
    ORB_SPEED,
    OVERCHARGE_INTERVAL_S,
    PICKUP_RADIUS,
    PLAYER_RADIUS,
    POISON_MAX_STACKS,
    POISON_S,
    POT_RADIUS,
    PROJECTILE_RADIUS,
    RECYCLE_DISTANCE,
    RECYCLE_EVERY_TICKS,
    REVIVE_HP_SHARE,
    REVIVE_I_FRAMES_S,
    SEPARATE_EVERY_TICKS,
    SHIELD_INTERVAL_S,
    SHOCK_DAMAGE,
    SHOCK_JUMPS,
    SHOCK_RANGE,
    SHOCKWAVE_PUSH,
    SHRAPNEL_DAMAGE,
    SHRAPNEL_PIECES,
    SHRAPNEL_RANGE,
    SHRAPNEL_SPEED,
    SHRINE_START_CLEARANCE,
    SKY_STRIKE_HEIGHT,
    SPREAD_COS,
    SPREAD_SIN,
    START_SHIELD_S,
    STORM_DAMAGE,
    STORM_REACH,
    STORM_S,
    STORM_STRIKES_PER_S,
    SWARM_SPREAD,
    VOLATILE_DELAY_S,
    VOLATILE_RADIUS,
)
from .upgrades import INSTANT_STATS, RARITIES, UpgradeDef, derive_stats, modifier_sums, roll_offer, roll_tier
from .waves import Scaling
from .weapons import (
    WEAPON_PREFIX,
    Bomb,
    Mine,
    Turret,
    WeaponDef,
    WeaponState,
    Zone,
    cos_sin,
    fan_directions,
    orbit_positions,
    rotate,
)

TICK_HZ = 60
META_SPECIAL = frozenset({"rerolls", "banishes", "start_shield_hp", "show_shrines_on_map"})
LEADERBOARD_WAVE_S = 30  # server/app.py and worker check wave = seconds // 30 + 1, whatever the bed pace
DT = 1.0 / TICK_HZ
MAX_SPAWNS_PER_TICK = 8
GRID_CELL = 64.0
INV_SQRT2 = 1.0 / math.sqrt(2.0)
IMPLEMENTED_BEHAVIORS = frozenset(BEHAVIORS)
MAX_TARGET_CHECKS = 8  # nearest enemies tested for a free line of fire
BOSS_CHEST_RARITY = {"boss_chest_epic": "epic", "boss_chest_legendary": "legendary", "boss_chest_rare": "rare"}


@dataclass(frozen=True, slots=True)
class PlayerInput:
    """Input of one player for one tick. move_x/move_y are each -1, 0 or 1.

    `choice` picks an offered upgrade card (0-based index); ignored when nothing is offered.
    `ability` triggers the character's active ability when it is ready.
    """

    player_id: int
    move_x: int = 0
    move_y: int = 0
    choice: int | None = None
    ability: bool = False
    reroll: bool = False  # roll the offered cards again (limited per run)
    banish: int | None = None  # remove that card's upgrade from this run and roll again (limited)


@dataclass(frozen=True, slots=True)
class StageConfig:
    """One garden bed (stages.json): its map, enemy mix (via `biome`), boss and multipliers."""

    id: str = "arena"
    index: int = 1
    name: str = "Arena"
    biome: str = ""
    obstacles: tuple[Obstacle, ...] = ()
    boss: str | None = None
    duration_s: float = 300.0
    hp_mult: float = 1.0
    damage_mult: float = 1.0
    budget_mult: float = 1.0
    tagline: str = ""
    head_start_s: float = 0.0  # waves and enemy kinds start as if this much time had passed


@dataclass(frozen=True, slots=True)
class FloodRules:
    """The endless "Plagenflut" after a bed's time is up; growth compounds every 10 s."""

    warning_s: float = 10.0
    budget_growth: float = 0.4
    hp_growth: float = 0.15
    damage_growth: float = 0.08
    reward_growth: float = 0.25  # XP and seeds per 10 s of flood (linear): the gamble pays
    wave_s: float = 30.0  # a new flood wave every this many seconds
    burst_base: int = 12  # enemies in the ring around the player when a flood wave rolls in
    burst_per_wave: int = 8
    speed_per_wave_pct: float = 8.0  # every flood wave, new enemies are this much faster


@dataclass(frozen=True, slots=True)
class WorldConfig:
    character: CharacterStats
    mobs: tuple[MobStats, ...]
    upgrades: tuple[UpgradeDef, ...]
    scaling: Scaling
    stages: tuple[StageConfig, ...] = (StageConfig(),)
    flood: FloodRules = FloodRules()
    gate_radius: float = 40.0
    bosses: tuple[BossStats, ...] = ()  # every boss the stages may call
    boss_chests: tuple[tuple[str, str], ...] = ()  # (boss id, min rarity of its chest)
    items: tuple[ItemDef, ...] = ()
    weapons: tuple[WeaponDef, ...] = ()
    weapon_slots: int = 1  # including the character's own weapon
    economy: Economy | None = None
    elite: EliteRules | None = None
    rarity_weights: dict[str, float] = field(default_factory=dict)
    card_tier_mult: dict[str, float] = field(default_factory=dict)  # value of a card by its rolled rarity
    level_up_choices: int = 3
    luck_shift: float = 0.0
    arena_w: float = 60 * 32.0
    arena_h: float = 60 * 32.0
    wave_interval_s: int = 30
    spawn_distance: tuple[float, float] = (520.0, 700.0)
    max_alive_enemies: int = 350
    difficulty: float = 1.0  # D, raised by shrines from phase 2 on
    enemy_target: int | None = None  # tests/benchmarks: keep exactly this many alive instead of the budget
    player_count: int = 1
    score: ScoreRules | None = None  # from balance.json; needed for `result()`
    shrines: tuple[ShrineRules, ...] = ()
    # Workshop bonuses bought between runs (meta/workshop.py): stat -> total, plus the specials
    # rerolls, banishes, start_shield_hp and show_shrines_on_map.
    meta_mods: tuple[tuple[str, float], ...] = ()

    @classmethod
    def from_content(
        cls, content, character_id: str = "ranger", player_count: int = 1, max_phase: int = 1, **overrides
    ) -> WorldConfig:
        bal = content.balance
        lo, hi = bal.raw["spawn_distance_px"]
        mobs = tuple(
            MobStats.from_content(content, m.id)
            for m in content.mobs
            if m.impl_phase <= max_phase and m.behavior in IMPLEMENTED_BEHAVIORS
        )
        upgrades = tuple(
            d
            for d in (UpgradeDef.from_content(u) for u in content.upgrades)
            if d.impl_phase <= max_phase and d.unlocked_at_start and d.supported
        )
        bosses = tuple(
            BossStats.from_content(content, b.id)
            for b in content.bosses
            if b.impl_phase <= max_phase and b.id in BOSS_BEHAVIORS
        )
        weapons = tuple(
            WeaponDef.from_content(w, content.weapon_max_level) for w in content.weapons if w.impl_phase <= max_phase
        )
        values = dict(
            character=CharacterStats.from_content(content, character_id),
            weapons=weapons,
            weapon_slots=content.weapon_slots,
            mobs=mobs,
            upgrades=upgrades,
            scaling=Scaling.from_content(content),
            stages=tuple(
                StageConfig(
                    st.id,
                    st.index,
                    st.name,
                    st.biome,
                    obstacles_for_biome(content, st.biome),
                    st.boss,
                    float(st.duration_s),
                    st.hp_mult,
                    st.damage_mult,
                    st.budget_mult,
                    st.tagline,
                    float(st.head_start_s),
                )
                for st in sorted(content.stages, key=lambda st: st.index)
            ),  # fmt: skip
            flood=FloodRules(
                float(content.flood["warning_s"]),
                float(content.flood["budget_growth_per_10s"]),
                float(content.flood["hp_growth_per_10s"]),
                float(content.flood["damage_growth_per_10s"]),
                float(content.flood.get("reward_growth_per_10s", 0.0)),
                float(content.flood.get("wave_s", 30)),
                int(content.flood.get("burst_base", 0)),
                int(content.flood.get("burst_per_wave", 0)),
                float(content.flood.get("speed_per_wave_pct", 0.0)),
            ),
            gate_radius=float(content.gate["radius_px"]),
            bosses=bosses,
            boss_chests=tuple((b.id, BOSS_CHEST_RARITY.get(content.boss(b.id).reward, "epic")) for b in bosses),
            elite=EliteRules.from_content(content),
            items=tuple(ItemDef.from_content(i) for i in content.items),
            economy=Economy.from_content(content) if content.economy else None,
            rarity_weights={k: float(v) for k, v in bal.rarity_weights.items()},
            card_tier_mult={k: float(v) for k, v in bal.raw.get("card_tier_mult", {}).items()},
            level_up_choices=bal.level_up_choices,
            luck_shift=float(bal.raw["luck_shift_per_point"]),
            arena_w=float(bal.arena_tiles[0] * bal.tile_px),
            arena_h=float(bal.arena_tiles[1] * bal.tile_px),
            wave_interval_s=bal.wave_interval_s,
            spawn_distance=(float(lo), float(hi)),
            max_alive_enemies=bal.max_alive_enemies,
            player_count=player_count,
            score=ScoreRules.from_content(content),
            shrines=tuple(
                ShrineRules.from_content(s, len(content.stages)) for s in content.shrines if s.id in SHRINE_KINDS
            ),
        )
        values.update(overrides)
        return cls(**values)


class PlayerView(NamedTuple):
    player_id: int
    x: float
    y: float
    standing: bool
    hp: float
    max_hp: float
    alive: bool
    invulnerable: bool
    kills: int
    level: int
    xp: float
    xp_needed: float
    offer: tuple[tuple[str, int, str], ...]  # (card id, current level, rolled rarity of the card)
    upgrades: tuple[tuple[str, int], ...]
    offer_source: str
    slowed: bool
    ability_ready: float = 1.0  # 0 right after use, 1 when ready again
    seeds: int = 0
    items: tuple[tuple[str, int], ...] = ()
    rerolls: int = 0
    banishes: int = 0
    weapons: tuple[tuple[str, int], ...] = ()  # extra weapons (id, level) in pick order
    shield: float = 0.0
    revives_left: int = 0
    card_tiers: tuple[tuple[str, str], ...] = ()  # best rarity picked per upgrade or "weapon:<id>"
    inferno: bool = False  # Mira's ring of fire is burning
    storm: bool = False  # Vex's thunderstorm is raging


class EnemyView(NamedTuple):
    eid: int
    kind: str
    x: float
    y: float
    radius: float
    hp_frac: float
    elite: bool
    boss: bool
    shield_frac: float
    aim: tuple[float, float] | None = None  # dashers while aiming: direction of the coming dash (warning line)
    status: str = ""  # "poison", "burn" or "chill" for a tint


class ProjectileView(NamedTuple):
    x: float
    y: float
    crit: bool
    weapon: str = ""  # "" for the character's own weapon
    vx: float = 0.0  # units per second (lets the renderer draw between ticks)
    vy: float = 0.0


class BombView(NamedTuple):
    x: float  # current position on its arc (ground position, the renderer adds the height)
    y: float
    tx: float
    ty: float
    progress: float  # 0 thrown .. 1 bursting
    radius: float


class EnemyShotView(NamedTuple):
    x: float
    y: float
    lobbed: bool
    tx: float
    ty: float


class HazardView(NamedTuple):
    kind: str
    x: float
    y: float
    radius: float
    armed: bool  # False while it is still a warning


class OrbView(NamedTuple):
    x: float
    y: float
    value: float
    kind: str = "xp"


class BossBar(NamedTuple):
    boss: str
    hp_frac: float
    phase: int


@dataclass(slots=True)
class Snapshot:
    """Read-only view handed to the renderer."""

    tick: int
    time_s: float
    wave: int
    arena_w: float
    arena_h: float
    over: bool
    paused: bool
    difficulty: float
    players: tuple[PlayerView, ...]
    enemies: tuple[EnemyView, ...]
    projectiles: tuple[ProjectileView, ...]
    orbs: tuple[OrbView, ...]
    enemy_shots: tuple[EnemyShotView, ...] = ()
    hazards: tuple[HazardView, ...] = ()
    chests: tuple[tuple[float, float, str], ...] = ()  # (x, y, kind): "map" costs seeds, "elite"/"boss" free
    boss_bar: BossBar | None = None
    pickups: tuple[tuple[str, float, float], ...] = ()
    pots: tuple[tuple[float, float], ...] = ()
    shrines: tuple[tuple[str, float, float, float, float], ...] = ()  # (kind, x, y, radius, charge 0..1)
    chest_price: int = 0
    stage: int = 1  # 1-based number of the garden bed
    stage_name: str = ""
    biome: str = ""
    stage_time_s: float = 0.0
    stage_duration_s: float = 300.0
    flood: bool = False
    flood_wave: int = 0
    shrine_radar: bool = False  # workshop: shrines on the minimap
    reward_mult: float = 1.0
    gate: tuple[float, float] | None = None
    victory: bool = False
    obstacles: tuple = ()  # the bed's obstacles (static per bed, the renderer rebuilds its map when they change)
    orbiters: tuple[tuple[str, float, float], ...] = ()  # (weapon, x, y), e.g. bees
    auras: tuple[tuple[str, float, float, float], ...] = ()  # (weapon, x, y, radius)
    bombs: tuple[BombView, ...] = ()
    zones: tuple[tuple[str, float, float, float, float], ...] = ()  # (weapon, x, y, radius, life left)
    turrets: tuple[tuple[str, float, float, float], ...] = ()  # (weapon, x, y, life left)
    mines: tuple[tuple[str, float, float], ...] = ()


@dataclass
class World:
    seed: int
    config: WorldConfig
    tick: int = 0
    wave: int = 0
    over: bool = False
    difficulty: float = field(init=False)
    players: list[Player] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    enemy_shots: list[EnemyShot] = field(default_factory=list)
    hazards: list[Hazard] = field(default_factory=list)
    orbs: list[XpOrb] = field(default_factory=list)
    chests: list[MapChest] = field(default_factory=list)
    pots: list[Pot] = field(default_factory=list)
    shrines: list[Shrine] = field(default_factory=list)
    pickups: list[Pickup] = field(default_factory=list)
    bombs: list[Bomb] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    turrets: list[Turret] = field(default_factory=list)
    mines: list[Mine] = field(default_factory=list)
    stage: int = 0  # index into config.stages
    stage_tick: int = 0
    gate: tuple[float, float] | None = None
    victory: bool = False
    flood_ticks: int = 0
    rng: Rng = field(init=False)

    def __post_init__(self) -> None:
        cfg = self.config
        self.rng = Rng(self.seed)
        self.difficulty = cfg.difficulty
        self._next_eid = 0
        self._budget = 0.0
        self._pending_mob: MobStats | None = None
        self._grid = SpatialHash(GRID_CELL)
        self._despawned: set[int] = set()
        self._upgrade_defs = {u.id: u for u in cfg.upgrades}
        self._item_defs = {i.id: i for i in cfg.items}
        self._weapon_defs = {w.id: w for w in cfg.weapons}
        self._weapon_cards = tuple(
            UpgradeDef(w.card_id, w.rarity, w.max_level, ("weapon",), (), w.impl_phase, True) for w in cfg.weapons
        )
        self._base_stats = derive_stats(cfg.character, {})
        meta = dict(cfg.meta_mods)
        self._meta_stats = {k: v for k, v in meta.items() if k not in META_SPECIAL}
        self.shrine_radar = meta.get("show_shrines_on_map", 0.0) > 0
        self.chests_opened = 0
        self._locked_until: dict[int, int] = {}
        self._mobs = {m.id: m for m in cfg.mobs}
        self.boss_stats = {b.id: b for b in cfg.bosses}
        self._boss_chest = dict(cfg.boss_chests)
        self._boss_spawned = False
        self._gate_ready_tick = 0
        self._max_radius = max([m.radius for m in cfg.mobs] + [b.radius for b in cfg.bosses] + [PLAYER_RADIUS])
        if cfg.elite:
            self._max_radius = max(self._max_radius, max((m.radius for m in cfg.mobs), default=0) * cfg.elite.size_mult)
        cx, cy = cfg.arena_w / 2, cfg.arena_h / 2
        if not self.players:
            # Players spawn next to each other in the central clearing.
            stats = derive_stats(cfg.character, self._meta_stats)
            self.players = [
                Player(pid, cx + (pid - (cfg.player_count - 1) / 2) * 32.0, cy, stats.max_hp, stats)
                for pid in range(cfg.player_count)
            ]
        self._pending: list[Event] = [RunStarted(0, None, self.seed)]
        self.bosses_killed = 0
        self.elites_killed = 0
        self.curse_total = 0  # Fluchstein: boss copies so far (at most CURSE_MAX_COPIES per run)
        self.curse_pending = 0  # copies the next bed boss brings
        # Challenge statistics of this run (meta/challenges.py): crits, poison_damage, low_hp_s,
        # kills_<biome>, flawless_wave (highest run-wide wave without damage), stage2_s.
        self.run_stats: dict[str, float] = {}
        self.bosses_defeated: list[str] = []
        self._wave_hurt = False
        self._run_wave = 0
        if cfg.economy is not None:
            for p in self.players:
                p.rerolls = cfg.economy.rerolls + int(meta.get("rerolls", 0.0))
                p.banishes = cfg.economy.banishes + int(meta.get("banishes", 0.0))
        if meta.get("start_shield_hp", 0.0) > 0:
            for p in self.players:  # workshop "Startschild": a shield that fades after a while
                p.temp_shield, p.temp_shield_t = meta["start_shield_hp"], START_SHIELD_S
        self._setup_stage()
        st = self.stage_cfg
        self._pending.append(StageStarted(0, None, st.index, st.name))

    def _setup_stage(self) -> None:
        """Map of the current bed: obstacles, and chests and pots from their own random stream per bed
        (differs per run and bed, never shifts the main stream)."""
        cfg, eco = self.config, self.config.economy
        self.obstacles = ObstacleMap(self.stage_cfg.obstacles)
        self.chests, self.pots, self.shrines = [], [], []
        if eco is not None and cfg.enemy_target is None:  # tests and benchmarks keep an empty map
            layout = Rng(self.seed ^ 0x5EED5 ^ (self.stage * 0x9E3779B1))
            start = (cfg.arena_w / 2, cfg.arena_h / 2)
            spots = scatter(layout, eco.chest_count + eco.pot_count, cfg.arena_w, cfg.arena_h, self.obstacles,
                            start, 220.0)  # fmt: skip
            self.chests = [MapChest(x, y, "map") for x, y in spots[: eco.chest_count]]
            self.pots = [Pot(x, y) for x, y in spots[eco.chest_count :]]
            kinds = [s for s in cfg.shrines for _ in range(s.on_stage(self.stage, len(cfg.stages)))]
            spots = scatter(Rng(self.seed ^ 0x5A17E ^ (self.stage * 0x9E3779B1)), len(kinds), cfg.arena_w,
                            cfg.arena_h, self.obstacles, start, SHRINE_START_CLEARANCE)  # fmt: skip
            self.shrines = [Shrine(s, x, y) for s, (x, y) in zip(kinds, spots, strict=False)]

    @property
    def stage_cfg(self) -> StageConfig:
        return self.config.stages[self.stage]

    @property
    def stage_time_s(self) -> float:
        return self.stage_tick / TICK_HZ

    @property
    def flood_s(self) -> float:
        """Seconds of Plagenflut in the current bed (0 before its time runs out)."""
        return max(0.0, self.stage_time_s - self.stage_cfg.duration_s)

    def _flood_factor(self, growth: float) -> float:
        """(1 + growth) per started 10 s of flood, compounded, blended linearly inside a step (no pow())."""
        steps, frac = divmod(self.flood_s / 10.0, 1.0)
        f = 1.0
        for _ in range(int(steps)):
            f *= 1.0 + growth
        return f * (1.0 + growth * frac)

    def mob_stats(self, mob_id: str) -> MobStats | None:
        return self._mobs.get(mob_id)

    @property
    def player_radius(self) -> float:
        return PLAYER_RADIUS

    def despawn(self, e: Enemy) -> None:
        """Remove an enemy without a kill (e.g. a pest tomato that burst on its own)."""
        self._despawned.add(e.eid)

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    @property
    def paused(self) -> bool:
        """Single player: an open upgrade choice pauses the game. Co-op will keep running (section 18)."""
        return self.config.player_count == 1 and any(p.offer for p in self.players if p.alive)

    @property
    def reward_mult(self) -> float:
        """XP (and seeds) per kill: shrine difficulty, and the Plagenflut pays more the longer you stay."""
        flood = 1.0 + self.config.flood.reward_growth * self.flood_s / 10.0
        return (1.0 + 0.8 * (self.difficulty - 1.0)) * flood

    # ------------------------------------------------------------------ step

    def step(self, inputs: dict[int, PlayerInput] | list[PlayerInput] | None = None) -> list[Event]:
        """Advance one fixed tick. Missing inputs mean "stand still".

        While paused for an upgrade choice, only the choice is processed and time stands still.
        """
        if self.over:
            return []
        if isinstance(inputs, list):
            inputs = {i.player_id: i for i in inputs}
        inputs = inputs or {}
        events, self._pending = self._pending, []

        self._apply_choices(inputs, events)
        if self.paused:
            return events

        self._move_players(inputs)
        self._use_abilities(inputs, events)
        if self.tick % RECYCLE_EVERY_TICKS == 0:
            self._recycle_far_enemies()
        self._spawn(events)
        self._spawn_bosses(events)
        self._rebuild_grid()
        self._move_enemies(events)
        self._rebuild_grid()
        self._shoot(events)
        self._use_weapons(events)
        self._move_projectiles(events)
        self._tick_statuses(events)
        self._aura(events)
        self._move_enemy_shots(events)
        self._update_hazards(events)
        self._contact_damage(events)
        self._collect_pickups(events)
        if self.gate is not None and self.tick >= self._gate_ready_tick and self._enter_gate(events):
            return events

        self.tick += 1
        self._track_run_stats()
        self.stage_tick += 1
        st = self.stage_cfg
        if self.stage_tick > st.duration_s * TICK_HZ:
            self.flood_ticks += 1
            wave_ticks = int(self.config.flood.wave_s * TICK_HZ)
            if wave_ticks and (self.stage_tick - int(st.duration_s * TICK_HZ)) % wave_ticks == 0:
                self._flood_wave(events)
        elif self.stage_tick == int((st.duration_s - self.config.flood.warning_s) * TICK_HZ):
            events.append(FloodWarning(self.tick, None, st.index))
        elif self.stage_tick == int(st.duration_s * TICK_HZ):
            events.append(FloodStarted(self.tick, None, st.index))
            self._flood_wave(events)
        # Wave n of a bed starts at n * wave_interval_s after the bed began (0:00-0:30 is wave 0).
        wave = self.stage_tick // (self.config.wave_interval_s * TICK_HZ)
        if wave != self.wave:
            self.wave = wave
            events.append(WaveStarted(self.tick, None, wave))
            elite = self.config.elite
            if elite and self.config.enemy_target is None and wave % elite.every_n_waves == 0:
                self._spawn_elite(events)
        if self.victory:
            self.over = True
            events.append(RunEnded(self.tick, None, self.time_s, True))
        elif not any(p.alive for p in self.players):
            self.over = True
            events.append(RunEnded(self.tick, None, self.time_s))
        return events

    @property
    def flood_wave(self) -> int:
        """Number of the current flood wave (0 before the flood)."""
        if self.flood_s <= 0 and self.stage_tick < self.stage_cfg.duration_s * TICK_HZ:
            return 0
        return 1 + int(self.flood_s // self.config.flood.wave_s)

    def _flood_wave(self, events: list[Event]) -> None:
        """A flood wave rolls in: a ring of pests right around every player, faster than the last ones."""
        f, n = self.config.flood, self.flood_wave
        events.append(FloodWave(self.tick, None, self.stage_cfg.index, n, self.reward_mult))
        count = f.burst_base + f.burst_per_wave * (n - 1)
        for p in self.players:
            if not p.alive:
                continue
            for k in range(count):
                if len(self.enemies) >= self.config.max_alive_enemies:
                    return
                mob = self._pick_mob(self.stage_cfg.biome)
                if mob is None:
                    return
                dx, dy = cos_sin(6.283185307179586 * k / count)
                dist = self.config.spawn_distance[0] * 0.75
                self._spawn_enemy(mob, p.x + dx * dist, p.y + dy * dist, events)

    def _enter_gate(self, events: list[Event]) -> bool:
        """A living player in the gate takes everyone to the next bed. Returns True when that happened."""
        gx, gy = self.gate
        r2 = (self.config.gate_radius + PLAYER_RADIUS) ** 2
        if not any(p.alive and (p.x - gx) ** 2 + (p.y - gy) ** 2 <= r2 for p in self.players):
            return False
        # Whatever still lies around is collected on the way (XP, seeds, healing).
        alive = [p for p in self.players if p.alive]
        for o in self.orbs:
            self._collect_orb(alive[0], o, events)
        self.stage += 1
        if self.stage == 1:
            self.run_stats["stage2_s"] = self.time_s
        self.stage_tick = self.wave = 0
        self.gate = None
        self._boss_spawned = False
        self._budget, self._pending_mob = 0.0, None
        self.enemies, self.projectiles, self.enemy_shots, self.hazards = [], [], [], []
        self.orbs, self.pickups, self.bombs = [], [], []
        self.zones, self.turrets, self.mines = [], [], []
        cx, cy = self.config.arena_w / 2, self.config.arena_h / 2
        for p in self.players:
            p.x, p.y = cx + (p.player_id - (self.config.player_count - 1) / 2) * 32.0, cy
            if p.alive:
                p.hp = p.stats.max_hp
        self._setup_stage()
        self._rebuild_grid()
        st = self.stage_cfg
        # A hot start: the first wave's budget is there at once, so the new bed fills up quickly.
        head = int(st.head_start_s // self.config.wave_interval_s)
        self._budget = self.config.scaling.wave_budget(head, self.difficulty, self.config.player_count) * st.budget_mult
        events.append(StageStarted(self.tick, None, st.index, st.name))
        return True

    # ------------------------------------------------------------------ players

    def _apply_choices(self, inputs: dict[int, PlayerInput], events: list[Event]) -> None:
        for p in self.players:
            inp = inputs.get(p.player_id)
            if not p.offer or inp is None:
                continue
            if inp.reroll and p.rerolls > 0:
                p.rerolls -= 1
                p.offer, p.offer_tiers = (), ()
                self._offer(p, events)
                continue
            if inp.banish is not None and 0 <= inp.banish < len(p.offer) and p.banishes > 0:
                p.banishes -= 1
                p.banished.add(p.offer[inp.banish])
                p.offer, p.offer_tiers = (), ()
                self._offer(p, events)
                continue
            if inp.choice is None or not 0 <= inp.choice < len(p.offer):
                continue
            uid = p.offer[inp.choice]
            tier = p.offer_tiers[inp.choice] if len(p.offer_tiers) == len(p.offer) else "common"
            mult = self.config.card_tier_mult.get(tier, 1.0)
            if uid.startswith(WEAPON_PREFIX):
                level = self._add_weapon(p, uid[len(WEAPON_PREFIX) :], mult)
            else:
                p.upgrades[uid] = level = p.upgrades.get(uid, 0) + 1
                p.upgrade_power[uid] = p.upgrade_power.get(uid, 0.0) + mult
                for stat, per_level in self._upgrade_defs[uid].effects:
                    if stat == "rerolls":
                        p.rerolls += max(1, int(per_level * mult))
                    elif stat == "banishes":
                        p.banishes += max(1, int(per_level * mult))
                self._recompute(p)
            if p.offer_source == "chest":
                p.pending_chests.pop(0)
            else:
                p.pending_levels -= 1
            if RARITIES.index(tier) >= RARITIES.index(p.card_tiers.get(uid, "common")):
                p.card_tiers[uid] = tier
            p.offer, p.offer_tiers, p.offer_source = (), (), ""
            events.append(UpgradeChosen(self.tick, p.player_id, uid, level, tier))
            self._offer(p, events)

    def _recompute(self, p: Player) -> None:
        """Stats from character, upgrades and items. Max-HP gains also heal by the same amount."""
        old_max = p.stats.max_hp
        power = {uid: p.upgrade_power.get(uid, float(level)) for uid, level in p.upgrades.items()}
        mods = modifier_sums(power, self._upgrade_defs, p.items, self._item_defs)
        mods = {k: v for k, v in mods.items() if k not in INSTANT_STATS}
        for k, v in self._meta_stats.items():
            mods[k] = mods.get(k, 0.0) + v
        for k, v in p.shrine_mods.items():
            mods[k] = mods.get(k, 0.0) + v
        p.stats = derive_stats(self.config.character, mods)
        p.hp = min(p.stats.max_hp, p.hp + max(0.0, p.stats.max_hp - old_max))

    def _add_weapon(self, p: Player, wid: str, mult: float = 1.0) -> int:
        """Pick a weapon card: a new weapon takes a free slot, a known one gains a level.
        A rarer card also adds damage: + (card_tier_mult - 1) x 100 %."""
        st = next((st for st in p.weapons if st.weapon == wid), None)
        if st is None:
            st = WeaponState(wid)
            p.weapons.append(st)
        else:
            st.level += 1
        st.power += mult - 1.0
        return st.level

    def card_levels(self, p: Player) -> dict[str, int]:
        """Current level of every card id: upgrades plus `weapon:<id>` for owned weapons."""
        levels = dict(p.upgrades)
        for st in p.weapons:
            levels[WEAPON_PREFIX + st.weapon] = st.level
        return levels

    def _weapon_pool(self, p: Player) -> list[UpgradeDef]:
        """Weapon cards on offer: levels for owned weapons, new ones only while a slot is free."""
        owned = {st.weapon for st in p.weapons}
        free = len(p.weapons) < self.config.weapon_slots - 1
        return [c for c, w in zip(self._weapon_cards, self.config.weapons, strict=True) if w.id in owned or free]

    def _give_item(self, p: Player, kind: str, events: list[Event]) -> None:
        eco, cfg = self.config.economy, self.config
        if eco is None or not cfg.items:
            return
        floor = dict(eco.min_rarity).get(kind, "common")
        item = roll_item(self.rng, cfg.items, cfg.rarity_weights, floor, p.stats.luck, cfg.luck_shift)
        if item is None:
            return
        p.items[item.id] = p.items.get(item.id, 0) + 1
        self._recompute(p)
        events.append(ItemGained(self.tick, p.player_id, item.id, p.items[item.id], kind))

    def _offer(self, p: Player, events: list[Event]) -> None:
        """Open the next pending choice: level-ups first, then chests (at least their rarity if available)."""
        cfg = self.config
        while not p.offer and (p.pending_levels > 0 or p.pending_chests):
            pool = [u for u in cfg.upgrades if u.id not in p.banished]
            source = "level"
            levels = p.upgrades
            if p.pending_levels > 0 and self._weapon_cards:
                pool += [c for c in self._weapon_pool(p) if c.id not in p.banished]
                levels = self.card_levels(p)
            if p.pending_levels <= 0:
                source = "chest"
                floor = RARITIES.index(p.pending_chests[0])
                rare_enough = [u for u in pool if RARITIES.index(u.rarity) >= floor]
                open_rare = [u for u in rare_enough if p.upgrades.get(u.id, 0) < u.max_level]
                if open_rare:
                    pool = rare_enough
                else:  # nothing that rare in the pool yet: offer the rarest tiers that are left
                    best = max((RARITIES.index(u.rarity) for u in pool if p.upgrades.get(u.id, 0) < u.max_level),
                               default=0)  # fmt: skip
                    pool = [u for u in pool if RARITIES.index(u.rarity) >= best]
            p.offer = roll_offer(
                self.rng, pool, levels, cfg.rarity_weights, cfg.level_up_choices, p.stats.luck, cfg.luck_shift
            )
            if p.offer:
                p.offer_source = source
                p.offer_tiers = tuple(
                    roll_tier(self.rng, cfg.rarity_weights, p.stats.luck, cfg.luck_shift) for _ in p.offer
                )
                events.append(UpgradeOffered(self.tick, p.player_id, p.offer))
            elif source == "level":
                p.pending_levels = 0  # everything maxed: nothing left to choose
            else:
                p.pending_chests.pop(0)

    def _move_players(self, inputs: dict[int, PlayerInput]) -> None:
        cfg = self.config
        r = PLAYER_RADIUS
        for p in self.players:
            if not p.alive:
                continue
            inp = inputs.get(p.player_id)
            mx = _sign(inp.move_x) if inp else 0
            my = _sign(inp.move_y) if inp else 0
            speed = p.stats.speed * (1.0 - p.slow_pct / 100.0)
            if self._low_hp(p):  # "Letztes Gefecht": faster when nearly beaten
                speed *= 1.0 + p.stats.low_hp_damage_pct / 200.0
            k = speed * INV_SQRT2 if (mx and my) else speed
            p.vx, p.vy = mx * k, my * k
            p.standing = not (mx or my)
            if not p.standing:
                n = INV_SQRT2 if (mx and my) else 1.0
                p.last_dx, p.last_dy = mx * n, my * n
            x, y = self.obstacles.push_out(p.x + p.vx * DT, p.y + p.vy * DT, r)
            p.x = min(max(x, r), cfg.arena_w - r)
            p.y = min(max(y, r), cfg.arena_h - r)
            if p.i_frames > 0:
                p.i_frames = max(0.0, p.i_frames - DT)
            if p.stats.regen_per_s:
                p.hp = min(p.stats.max_hp, p.hp + p.stats.regen_per_s * DT)
            self._tick_player_buffs(p)

    def _tick_player_buffs(self, p: Player) -> None:
        s = p.stats
        if p.haste_t > 0:
            p.haste_t -= DT
            if p.haste_t <= 0:
                p.haste_pct = 0.0
        if s.overcharge_pct and p.overcharge_t > 0:
            p.overcharge_t -= DT
        if p.temp_shield_t > 0:  # Brun's "Bollwerk" lasts a few seconds
            p.temp_shield_t -= DT
            if p.temp_shield_t <= 0:
                p.temp_shield = 0.0
        if p.inferno_t > 0:
            p.inferno_t -= DT
        if p.storm_t > 0:  # Vex's "Gewittersturm": strikes in a steady beat
            p.storm_t -= DT
            if int(p.storm_t * TICK_HZ) % int(TICK_HZ / STORM_STRIKES_PER_S) == 0:
                self._sky_strike(p, s.damage * STORM_DAMAGE, self._pending, STORM_REACH)
        if s.aura_slow_pct and self.tick % 6 == 0:  # Ysa's "Frostaura"
            r2 = s.aura_slow_radius * s.aura_slow_radius
            for e in self._grid.query(p.x, p.y, s.aura_slow_radius):
                if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r2 and (e.chill_t <= 0.1 or e.chill_pct < s.aura_slow_pct):
                    e.chill_pct, e.chill_t = s.aura_slow_pct, 0.15
        if s.shield:  # "Notschild": refills every SHIELD_INTERVAL_S
            p.shield_t -= DT
            if p.shield_t <= 0:
                p.shield, p.shield_t = s.shield, SHIELD_INTERVAL_S

    def _low_hp(self, p: Player) -> bool:
        return p.stats.low_hp_damage_pct > 0 and p.hp < p.stats.max_hp * LOW_HP_SHARE

    def damage_mult(self, p: Player) -> float:
        """Conditional damage bonuses of a player right now (standing still, low HP)."""
        s, m = p.stats, 1.0
        if p.standing:  # items like "Tiefe Wurzeln" reward standing still
            m *= s.standing_damage_mult
        if self._low_hp(p):
            m *= 1.0 + s.low_hp_damage_pct / 100.0
        if s.nearby_damage_pct:  # Kaz's "Nervenkitzel": braver the closer they get
            r2 = s.nearby_radius * s.nearby_radius
            near = sum(
                1 for e in self._grid.query(p.x, p.y, s.nearby_radius) if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r2
            )
            m *= 1.0 + s.nearby_damage_pct / 100.0 * min(near, s.nearby_max)
        return m

    def attack_rate(self, p: Player) -> float:
        return p.stats.attack_rate * (1.0 + p.haste_pct / 100.0)

    def _use_abilities(self, inputs: dict[int, PlayerInput], events: list[Event]) -> None:
        ch = self.config.character
        for p in self.players:
            if not p.alive:
                continue
            if p.ability_cooldown > 0:
                p.ability_cooldown = max(0.0, p.ability_cooldown - DT)
            inp = inputs.get(p.player_id)
            if not inp or not inp.ability or p.ability_cooldown > 0 or ch.active_id not in ABILITIES:
                continue
            p.ability_cooldown = ch.active_cooldown_s * p.stats.cooldown_mult
            ABILITIES[ch.active_id](self, p, events)
            events.append(AbilityUsed(self.tick, p.player_id, ch.active_id, p.x, p.y))

    def _arrow_storm(self, p: Player, events: list[Event]) -> None:
        """Fenn's "Pfeilhagel": arrows in all directions at 60 % damage."""
        s = p.stats
        life = max(1, int(s.range / self.config.character.projectile_speed * TICK_HZ + 0.5))
        step = len(COMPASS_16) // ARROW_STORM_SHOTS if len(COMPASS_16) >= ARROW_STORM_SHOTS else 1
        for k in range(ARROW_STORM_SHOTS):
            dx, dy = COMPASS_16[(k * step) % len(COMPASS_16)]
            self._fire(p, dx, dy, s.damage * ARROW_STORM_DAMAGE, life, events)

    def _inferno(self, p: Player, events: list[Event]) -> None:
        """Mira's "Inferno": a ring of fire around her for a few seconds (pulses in `_aura`)."""
        p.inferno_t = INFERNO_S

    def _shadow_step(self, p: Player, events: list[Event]) -> None:
        """Kaz's "Schattenschritt": a dash in the walking direction, briefly untouchable."""
        cfg, r = self.config, PLAYER_RADIUS
        steps = 8
        for _ in range(steps):  # in small steps, so obstacles still stop the dash
            x, y = self.obstacles.push_out(
                p.x + p.last_dx * DASH_DISTANCE / steps, p.y + p.last_dy * DASH_DISTANCE / steps, r
            )
            p.x, p.y = min(max(x, r), cfg.arena_w - r), min(max(y, r), cfg.arena_h - r)
        p.i_frames = max(p.i_frames, DASH_I_FRAMES_S)

    def _bulwark(self, p: Player, events: list[Event]) -> None:
        """Brun's "Bollwerk": a shield that soaks up damage for a few seconds."""
        p.temp_shield, p.temp_shield_t = BULWARK_SHIELD, BULWARK_S

    def _ice_age(self, p: Player, events: list[Event]) -> None:
        """Ysa's "Eiszeit": every enemy around is frozen solid (bosses only slowed)."""
        r2 = ICE_AGE_REACH * ICE_AGE_REACH
        for e in self.enemies:
            if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r2:
                e.chill_pct, e.chill_t = (60.0 if e.boss else 100.0), ICE_AGE_S

    def _thunderstorm(self, p: Player, events: list[Event]) -> None:
        """Vex's "Gewittersturm": lightning strikes in a steady beat for a few seconds (see `_tick_player_buffs`)."""
        p.storm_t = STORM_S

    def _hurt(self, p: Player, damage: float, events: list[Event], use_i_frames: bool = True) -> None:
        """Damage a player. Hits respect and start i-frames; damage over time does not."""
        if not p.alive or (use_i_frames and p.i_frames > 0):
            return
        s = p.stats
        if use_i_frames and s.dodge_chance_pct and self.rng.random() * 100.0 < s.dodge_chance_pct:
            p.i_frames = DODGE_I_FRAMES_S
            events.append(PlayerDodged(self.tick, p.player_id, p.x, p.y))
            return
        dmg = damage * s.damage_taken_mult
        if use_i_frames and s.armor:
            dmg = max(1.0, dmg - s.armor)
        for attr in ("temp_shield", "shield"):  # Brun's "Bollwerk" first, then "Notschild"
            left = getattr(p, attr)
            if left > 0 and dmg > 0:
                absorbed = min(left, dmg)
                setattr(p, attr, left - absorbed)
                dmg -= absorbed
        p.hp = max(0.0, p.hp - dmg)
        p.damage_taken += dmg
        if dmg > 0:
            self._wave_hurt = True
        if use_i_frames:
            p.i_frames = self.config.character.i_frames_s * s.i_frames_mult
            events.append(PlayerHit(self.tick, p.player_id, dmg, p.hp))
        if p.hp <= 0 and p.revives_used < s.revives:  # "Zweiter Atem", "Gartenzwerg"
            p.revives_used += 1
            p.hp = s.max_hp * REVIVE_HP_SHARE
            p.i_frames = REVIVE_I_FRAMES_S
            events.append(PlayerRevived(self.tick, p.player_id, p.x, p.y))
            return
        if p.hp <= 0:
            p.alive = False
            p.offer, p.pending_levels, p.pending_chests = (), 0, []
            events.append(PlayerDied(self.tick, p.player_id))

    def _nearest_player(self, x: float, y: float) -> tuple[Player | None, float]:
        best, best_d2 = None, math.inf
        for p in self.players:
            if p.alive:
                d2 = (p.x - x) ** 2 + (p.y - y) ** 2
                if d2 < best_d2:
                    best, best_d2 = p, d2
        return best, best_d2

    # ------------------------------------------------------------------ spawning

    def _spawn(self, events: list[Event]) -> None:
        cfg = self.config
        alive = [p for p in self.players if p.alive]
        if not alive or not cfg.mobs:
            return
        if cfg.enemy_target is not None:
            for _ in range(MAX_SPAWNS_PER_TICK):
                if len(self.enemies) >= min(cfg.enemy_target, cfg.max_alive_enemies):
                    return
                x, y = self._spawn_point(alive)
                self._spawn_enemy(cfg.mobs[0], x, y, events)
            return

        wave_ticks = cfg.wave_interval_s * TICK_HZ
        head = int(self.stage_cfg.head_start_s // cfg.wave_interval_s)  # later beds start hot
        per_wave = cfg.scaling.wave_budget(self.wave + head, self.difficulty, cfg.player_count)
        per_wave *= self.stage_cfg.budget_mult
        if self.flood_s > 0:
            per_wave *= self._flood_factor(cfg.flood.budget_growth)
        # Unspent budget is capped at one wave, so a full arena does not cause a burst later.
        self._budget = min(self._budget + per_wave / wave_ticks, per_wave)
        for _ in range(MAX_SPAWNS_PER_TICK):
            if len(self.enemies) >= cfg.max_alive_enemies:
                return
            x, y = self._spawn_point(alive)
            mob = self._pending_mob or self._pick_mob(self.stage_cfg.biome)
            if mob is None:
                return
            if len(self.enemies) + mob.group_size > cfg.max_alive_enemies:
                return
            group_cost = mob.cost * mob.group_size  # groups pay their budget once per member
            if self._budget < group_cost:
                self._pending_mob = mob  # save up for it; position is rolled again when affordable
                return
            self._pending_mob = None
            self._budget -= group_cost
            for i in range(mob.group_size):
                if i == 0:
                    self._spawn_enemy(mob, x, y, events)
                else:
                    ox, oy = self.random_offset(SWARM_SPREAD)
                    self._spawn_enemy(mob, x + ox, y + oy, events)

    def _pick_mob(self, biome: str | None) -> MobStats | None:
        t = self.stage_time_s + self.stage_cfg.head_start_s
        options = [(m, dict(m.biome_weights).get(biome, 0.0)) for m in self.config.mobs if m.min_time_s <= t]
        options = [(m, w) for m, w in options if w > 0]
        if not options:
            return None
        r = self.rng.random() * sum(w for _, w in options)
        for m, w in options:
            if r < w:
                return m
            r -= w
        return options[-1][0]

    def _spawn_point(self, alive: list[Player]) -> tuple[float, float]:
        lo, hi = self.config.spawn_distance
        p = alive[self.rng.randint(0, len(alive) - 1)]
        dx, dy = self._random_direction()
        dist = self.rng.uniform(lo, hi)
        return self._clamp(p.x + dx * dist, p.y + dy * dist, self._max_radius)

    def _clamp(self, x: float, y: float, r: float) -> tuple[float, float]:
        cfg = self.config
        return min(max(x, r), cfg.arena_w - r), min(max(y, r), cfg.arena_h - r)

    def _spawn_enemy(self, m: MobStats, x: float, y: float, events: list[Event]) -> Enemy:
        sc, minutes, st = self.config.scaling, self.stage_time_s / 60.0, self.stage_cfg
        x, y = self._clamp(*self.obstacles.push_out(x, y, m.radius), m.radius)
        hp = m.hp * sc.hp_mult(minutes) * st.hp_mult
        dmg = m.damage * sc.damage_mult(minutes) * self.difficulty * st.damage_mult
        if self.flood_s > 0:
            hp *= self._flood_factor(self.config.flood.hp_growth)
            dmg *= self._flood_factor(self.config.flood.damage_growth)
        speed = m.speed * sc.speed_mult(minutes)
        if self.flood_wave > 1:  # every flood wave brings faster pests
            speed *= 1.0 + self.config.flood.speed_per_wave_pct / 100.0 * (self.flood_wave - 1)
        e = Enemy(self._next_eid, m.id, x, y, hp, hp, speed, dmg, m.radius, m.xp, m.behavior)
        e.keep_distance, e.shot_interval, e.timer = m.keep_distance, m.shot_interval, m.shot_interval
        self.enemies.append(e)
        events.append(EnemySpawned(self.tick, None, self._next_eid, m.id, self.stage_cfg.biome))
        self._next_eid += 1
        return e

    def _spawn_elite(self, events: list[Event]) -> None:
        alive = [p for p in self.players if p.alive]
        rules = self.config.elite
        if not alive or rules is None:
            return
        x, y = self._spawn_point(alive)
        mob = self._pick_mob(self.stage_cfg.biome)
        if mob is None:
            return
        e = self._spawn_enemy(mob, x, y, events)
        e.elite = True
        e.hp = e.max_hp = e.max_hp * rules.hp_mult
        e.damage *= rules.damage_mult
        e.xp *= rules.xp_mult
        e.radius *= rules.size_mult
        pool = list(rules.affix_ids)
        affixes = []
        for _ in range(min(rules.affix_count(self.time_s / 60.0), len(pool))):  # affixes grow over the whole run
            affixes.append(pool.pop(self.rng.randint(0, len(pool) - 1)))
        e.affixes = tuple(affixes)
        apply_affixes(e)
        events.append(EliteSpawned(self.tick, None, e.eid, e.kind, e.affixes))

    def _spawn_bosses(self, events: list[Event]) -> None:
        """The bed's boss arrives at its spawn time (counted from the start of the bed), near the player."""
        st = self.stage_cfg
        b = self.boss_stats.get(st.boss) if st.boss else None
        if self._boss_spawned or b is None or self.stage_time_s < b.spawn_time_s:
            return
        p, _ = self._nearest_player(self.config.arena_w / 2, self.config.arena_h / 2)
        if p is None:
            return
        self._boss_spawned = True
        cursed = self.curse_pending > 0
        for _ in range(1 + self.curse_pending):  # Fluchstein: the boss comes more than once
            x, y = self._boss_spawn_point(b, p)
            hp = b.hp * self.difficulty
            e = Enemy(self._next_eid, b.id, x, y, hp, hp, b.speed, b.damage * self.difficulty, b.radius, 0.0, "boss",
                      boss=b.id)  # fmt: skip
            e.cursed = cursed
            self.enemies.append(e)
            self._next_eid += 1
            events.append(BossSpawned(self.tick, None, e.eid, b.id))
        self.curse_pending = 0

    def _boss_spawn_point(self, b: BossStats, p: Player) -> tuple[float, float]:
        """On the spawn ring around the player, but not closer than BOSS_MIN_SPAWN_DISTANCE."""
        lo, hi = self.config.spawn_distance
        lo = max(lo, BOSS_MIN_SPAWN_DISTANCE)
        dx, dy = self._random_direction()
        dist = self.rng.uniform(lo, max(lo, hi))
        x, y = self._clamp(p.x + dx * dist, p.y + dy * dist, b.radius)
        return self._clamp(*self.obstacles.push_out(x, y, b.radius), b.radius)

    def summon_around(self, boss: Enemy, mob_id: str, count: int, events: list[Event]) -> None:
        mob = self._mobs.get(mob_id)
        if mob is None:
            return
        for _ in range(count):
            ox, oy = self.random_offset(boss.radius * 3)
            self._spawn_enemy(mob, boss.x + ox, boss.y + oy, events)

    def add_hazard(self, spec: HazardSpec, x: float, y: float, source: int) -> None:
        self.hazards.append(Hazard(spec, x, y, spec.delay, spec.duration, source))

    def random_offset(self, radius: float) -> tuple[float, float]:
        dx, dy = self._random_direction()
        r = self.rng.uniform(0.0, radius)
        return dx * r, dy * r

    def _random_direction(self) -> tuple[float, float]:
        """Uniform unit vector by rejection sampling (no trigonometry, so bit-identical everywhere)."""
        while True:
            x, y = self.rng.uniform(-1.0, 1.0), self.rng.uniform(-1.0, 1.0)
            d2 = x * x + y * y
            if 0.01 < d2 <= 1.0:
                d = math.sqrt(d2)
                return x / d, y / d

    # ------------------------------------------------------------------ enemies

    def _rebuild_grid(self) -> None:
        g = self._grid
        g.clear()
        for e in self.enemies:
            g.insert(e, e.x, e.y)

    def _move_enemies(self, events: list[Event]) -> None:
        if not any(p.alive for p in self.players):
            return
        for e in self.enemies:
            p, d2 = self._nearest_player(e.x, e.y)
            d = math.sqrt(d2)
            if e.boss:
                BOSS_BEHAVIORS[e.boss](self, e, p.x, p.y, d, events)
            else:
                BEHAVIORS.get(e.behavior, BEHAVIORS["chaser"])(self, e, p.x, p.y, d, events)
            if e.elite:
                tick_affixes(e)
        self._separate()
        obstacles = self.obstacles
        for e in self.enemies:
            e.x, e.y = self._clamp(*obstacles.push_out(e.x, e.y, e.radius), e.radius)
        if self._despawned:
            self.enemies = [e for e in self.enemies if e.eid not in self._despawned]
            self._despawned.clear()

    def _separate(self) -> None:
        """Push overlapping enemies apart so they form a crowd instead of a single dot.

        Walks the grid cell by cell and compares each cell with itself and 4 of its neighbours
        (every neighbouring pair of cells once), which is far cheaper than one radius query per enemy.
        Pairs farther apart than one cell are skipped; with cells of 64 that only loosens boss/elite pairs.
        Runs every SEPARATE_EVERY_TICKS ticks: one pass already resolves each overlap completely."""
        if self.tick % SEPARATE_EVERY_TICKS:
            return
        g = self._grid
        sqrt = math.sqrt
        for (cx, cy), bucket in g.buckets():
            groups = [(bucket, True)]
            for key in ((cx + 1, cy), (cx - 1, cy + 1), (cx, cy + 1), (cx + 1, cy + 1)):
                other = g.bucket(key)
                if other:
                    groups.append((other, False))
            for i, e in enumerate(bucket):
                er = e.radius
                for others, same in groups:
                    for o in others[i + 1 :] if same else others:
                        dx, dy = o.x - e.x, o.y - e.y
                        d2 = dx * dx + dy * dy
                        min_d = er + o.radius
                        if 1e-9 < d2 < min_d * min_d:
                            d = sqrt(d2)
                            push = (min_d - d) * 0.5 / d
                            e.x -= dx * push
                            e.y -= dy * push
                            o.x += dx * push
                            o.y += dy * push

    def _recycle_far_enemies(self) -> None:
        """Enemies left far behind are moved back to the spawn ring around a player (no new spawn,
        same HP), so the fight stays on screen and the enemy count does not pile up."""
        alive = [p for p in self.players if p.alive]
        if not alive:
            return
        far2 = RECYCLE_DISTANCE * RECYCLE_DISTANCE
        for e in self.enemies:
            if e.boss or e.elite:
                continue
            if all((e.x - p.x) ** 2 + (e.y - p.y) ** 2 > far2 for p in alive):
                x, y = self._spawn_point(alive)
                e.x, e.y = self._clamp(*self.obstacles.push_out(x, y, e.radius), e.radius)

    def _kill(self, e: Enemy, killer: int | None, events: list[Event]) -> None:
        events.append(EnemyKilled(self.tick, killer, e.eid, e.kind, e.x, e.y))
        self._count(f"kills_{self.stage_cfg.biome}")
        if e.boss:
            self.bosses_defeated.append(e.boss)
        if e.elite:
            self.elites_killed += 1
        if e.xp > 0:
            self.orbs.append(XpOrb(e.x, e.y, e.xp * self.reward_mult))
        eco = self.config.economy
        if eco is not None:
            value = eco.boss_value if e.boss else eco.elite_value if e.elite else 0
            if not value and self.rng.random() * 100.0 < eco.drop_pct:
                value = eco.normal_value
            if value:
                self.orbs.append(XpOrb(e.x + 6.0, e.y, float(value) * self.reward_mult, kind="seeds"))
        if e.elite or (not e.boss and self.rng.random() * 100.0 < MAGNET_DROP_PCT):
            self.pickups.append(Pickup("magnet", e.x, e.y))
        for p in self.players:
            if p.player_id == killer:
                p.kills += 1
                if p.stats.heal_per_kill and p.alive:
                    p.hp = min(p.stats.max_hp, p.hp + p.stats.heal_per_kill)
                if p.stats.kill_haste_max_pct:  # "Blutrausch"
                    p.haste_pct = min(p.stats.kill_haste_max_pct, p.haste_pct + KILL_HASTE_PCT)
                    p.haste_t = KILL_HASTE_S
                if p.stats.heal_orb_chance_pct and self.rng.random() * 100.0 < p.stats.heal_orb_chance_pct:
                    heal = self.config.economy.heal_orb_hp if self.config.economy else 15.0
                    self.orbs.append(XpOrb(e.x - 6.0, e.y, heal, kind="heal"))
        if e.elite:
            self._drop_chest(e.x, e.y, "elite", events)
            if "volatile" in e.affixes:
                spec = HazardSpec("explosion", VOLATILE_RADIUS, delay=VOLATILE_DELAY_S, burst=e.damage)
                self.add_hazard(spec, e.x, e.y, e.eid)
        if e.boss:
            self.bosses_killed += 1
            events.append(BossKilled(self.tick, killer, e.eid, e.boss, self.time_s))
            last = self.stage + 1 >= len(self.config.stages)
            if e.cursed:  # Fluchstein reward: a free card one tier above the boss chest
                owner = next((p for p in self.players if p.player_id == killer and p.alive), None)
                owner = owner or next((p for p in self.players if p.alive), None)
                if owner is not None:
                    owner.pending_chests.append(CURSE_CARD_RARITY)
                    self._offer(owner, events)
            if not last:
                self._drop_chest(e.x, e.y, "boss", events)
            if any(o.boss and o.eid != e.eid and o.hp > 0 for o in self.enemies):
                return  # copies of the boss are still standing
            if last:
                self.victory = True  # the last bed's boss: the run is won
            else:
                gx, gy = self._clamp(*self.obstacles.push_out(e.x, e.y + GATE_OFFSET, self.config.gate_radius),
                                     self.config.gate_radius)  # fmt: skip
                self.gate = (gx, gy)
                self._gate_ready_tick = self.tick + int(GATE_DELAY_S * TICK_HZ)
                events.append(GateOpened(self.tick, None, gx, gy))

    def _drop_chest(self, x: float, y: float, kind: str, events: list[Event]) -> None:
        """Elite and boss chests are free and hold at least a rare or epic item (items.json economy)."""
        self.chests.append(MapChest(x, y, kind))
        events.append(ChestDropped(self.tick, None, x, y, kind))

    def _explode(self, e: Enemy, killer: int | None, damage: float, killed: set[int], events: list[Event]) -> None:
        """Item "Samenbombe": a kill bursts and hurts enemies around it (no chain reaction)."""
        owner = next((p for p in self.players if p.player_id == killer), None)
        radius = KILL_EXPLOSION_RADIUS * (owner.stats.area_mult if owner else 1.0)
        r2 = radius**2
        events.append(HazardActivated(self.tick, killer, "seed_burst", e.x, e.y, radius))
        for o in self._grid.query(e.x, e.y, radius + self._max_radius):
            if o.eid == e.eid or o.eid in killed or (o.x - e.x) ** 2 + (o.y - e.y) ** 2 > r2:
                continue
            damage_enemy(o, damage)
            if o.hp <= 0:
                killed.add(o.eid)
                self._kill(o, killer, events)

    # ------------------------------------------------------------------ combat

    def _shoot(self, events: list[Event]) -> None:
        ch = self.config.character
        for p in self.players:
            if not p.alive:
                continue
            s = p.stats
            p.shot_cooldown -= DT
            if p.shot_cooldown > 0:
                continue
            # Auto-fire at the nearest visible enemy, also while moving (decided 28.10.2026).
            target, best = self._pick_target(p)
            if target is None:
                p.shot_cooldown = 0.0
                continue
            p.shot_cooldown += 1.0 / self.attack_rate(p)
            d = math.sqrt(best) or 1.0
            dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
            life = max(1, int(s.range / (max(ch.projectile_speed, 1.0) * s.projectile_speed_mult) * TICK_HZ + 0.5))
            damage = s.damage * self.damage_mult(p)
            if s.far_damage_pct and d > s.far_threshold:  # e.g. Fenn's passive "Weitblick"
                damage *= 1.0 + s.far_damage_pct / 100.0
            big = False
            if s.overcharge_pct and p.overcharge_t <= 0:  # "Überladung": one big shot every few seconds
                p.overcharge_t = OVERCHARGE_INTERVAL_S
                damage *= 1.0 + s.overcharge_pct / 100.0
                big = True
            pattern = ch.weapon_pattern
            p.shots_fired += 1
            if pattern == "shockwave":  # Brun: a ring around him, pushing the pests back
                self._shockwave(p, damage, events)
            elif pattern == "chain_lightning":  # Vex: a bolt that jumps on
                self._chain_bolt(p, target, damage, events)
            else:
                directions = [(dx, dy)]
                if pattern == "fan3":  # Kaz: three knives in a fan
                    directions = fan_directions(dx, dy, 3, KNIFE_FAN_DEG)
                # Extra attacks fan out alternately left and right of the main shot.
                lx, ly, rx, ry = dx, dy, dx, dy
                extra = []
                for k in range(s.extra_attacks):
                    if k % 2 == 0:
                        lx, ly = lx * SPREAD_COS - ly * SPREAD_SIN, lx * SPREAD_SIN + ly * SPREAD_COS
                        extra.append((lx, ly))
                    else:
                        rx, ry = rx * SPREAD_COS + ry * SPREAD_SIN, -rx * SPREAD_SIN + ry * SPREAD_COS
                        extra.append((rx, ry))
                for i, (fx, fy) in enumerate(directions + extra):
                    dmg = damage if i < len(directions) else damage * EXTRA_ATTACK_DAMAGE
                    self._fire(p, fx, fy, dmg, life, events, big=big and i == 0, **self._shot_traits(ch))
            if s.strike_every and p.shots_fired % s.strike_every == 0:  # Vex: "Statische Ladung"
                self._sky_strike(p, s.damage * s.strike_damage_pct / 100.0, events)

    def _shot_traits(self, ch: CharacterStats) -> dict:
        """What the character's own shots do on impact (fireball burst and burn, frost)."""
        if ch.weapon_pattern == "single_explosive":
            extra = dict(ch.weapon_extra)
            return dict(explode_r=ch.aoe_radius, burn_pct=extra.get("ignite_pct", 0.0))
        if dict(ch.weapon_extra).get("slow_pct"):
            return dict(frost=True)
        return {}

    def _shockwave(self, p: Player, damage: float, events: list[Event]) -> None:
        """Brun's shockwave: everything in the ring is hit and pushed outwards."""
        killed: set[int] = set()
        radius = self.config.character.aoe_radius * p.stats.area_mult * (1.0 + 0.15 * p.stats.extra_attacks)
        events.append(WeaponPulse(self.tick, p.player_id, "shockwave", p.x, p.y, radius))
        dmg, crit = self._roll_crit(p, damage)
        for e in self._grid.query(p.x, p.y, radius + self._max_radius):
            ex, ey = e.x - p.x, e.y - p.y
            d = math.sqrt(ex * ex + ey * ey)
            if e.eid in killed or e.hp <= 0 or d > radius + e.radius:
                continue
            self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
            if not e.boss and d > 1e-9:
                e.x += ex / d * SHOCKWAVE_PUSH
                e.y += ey / d * SHOCKWAVE_PUSH
        self._remove_killed(killed)

    def _chain_bolt(self, p: Player, target: Enemy, damage: float, events: list[Event]) -> None:
        """Vex's chain lightning: hits the target and jumps on, a little weaker each time."""
        extra = dict(self.config.character.weapon_extra)
        jumps = int(extra.get("chain_jumps", 2)) + p.stats.extra_attacks
        radius, falloff = extra.get("chain_radius", 160.0), extra.get("chain_falloff", 0.8)
        killed: set[int] = set()
        points, hit, e = [(p.x, p.y), (target.x, target.y)], {target.eid}, target
        dmg, crit = self._roll_crit(p, damage)
        self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        for _ in range(jumps):
            dmg *= falloff
            best, best_d2 = None, radius * radius
            for o in self._grid.query(e.x, e.y, radius):
                d2 = (o.x - e.x) ** 2 + (o.y - e.y) ** 2
                if o.eid not in hit and o.eid not in killed and o.hp > 0 and d2 < best_d2:
                    best, best_d2 = o, d2
            if best is None:
                break
            hit.add(best.eid)
            points.append((best.x, best.y))
            e = best
            self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        events.append(Zap(self.tick, p.player_id, tuple(points)))
        self._remove_killed(killed)

    def _sky_strike(self, p: Player, damage: float, events: list[Event], reach: float | None = None) -> None:
        """A lightning strike from above on a random enemy in reach (Vex's passive and "Gewittersturm")."""
        reach = reach or p.stats.range
        targets = [e for e in self.enemies if e.hp > 0 and (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= reach * reach]
        if not targets:
            return
        e = targets[self.rng.randint(0, len(targets) - 1)]
        killed: set[int] = set()
        self._weapon_hit(p, p.player_id, e, damage, True, killed, events, procs=False)
        events.append(Zap(self.tick, p.player_id, ((e.x, e.y - SKY_STRIKE_HEIGHT), (e.x, e.y))))
        self._remove_killed(killed)

    def _remove_killed(self, killed: set[int]) -> None:
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _pick_target(self, p: Player, reach: float | None = None) -> tuple[Enemy | None, float]:
        """Nearest enemy in range with a free line of fire (trees give cover)."""
        reach = p.stats.range if reach is None else reach
        range2 = reach * reach
        in_range = []
        for e in self.enemies:
            d2 = (e.x - p.x) ** 2 + (e.y - p.y) ** 2
            if d2 <= range2:
                in_range.append((d2, e.eid, e))
        in_range.sort(key=lambda t: (t[0], t[1]))
        for d2, _, e in in_range[:MAX_TARGET_CHECKS]:
            if not self.obstacles.line_blocked(p.x, p.y, e.x, e.y, PROJECTILE_RADIUS):
                return e, d2
        return None, 0.0

    def _fire(self, p: Player, dx: float, dy: float, damage: float, life: int, events: list[Event],
              speed: float | None = None, pierce: int | None = None, weapon: str = "",
              big: bool = False, origin: tuple[float, float] | None = None, **extra) -> Projectile:  # fmt: skip
        s = p.stats
        speed = (self.config.character.projectile_speed if speed is None else speed) * s.projectile_speed_mult
        dmg, crit = self._roll_crit(p, damage)
        hits = (s.pierce if pierce is None else pierce) + 1
        radius = PROJECTILE_RADIUS * s.projectile_size_mult * (2.0 if big else 1.0)
        x, y = origin or (p.x, p.y)
        pr = Projectile(p.player_id, x, y, dx * speed, dy * speed, dmg, crit or big, life, hits, weapon=weapon,
                        radius=radius, bounces_left=s.bounces, **extra)  # fmt: skip
        self.projectiles.append(pr)
        events.append(ShotFired(self.tick, p.player_id, x, y, dx, dy, weapon))
        return pr

    def _roll_crit(self, p: Player, damage: float) -> tuple[float, bool]:
        s = p.stats
        crit = self.rng.random() * 100.0 < s.crit_chance_pct
        if crit:
            self._count("crits")
        return damage * (s.crit_mult if crit else 1.0), crit

    def _move_projectiles(self, events: list[Event]) -> None:
        g = self._grid
        survivors: list[Projectile] = []
        killed: set[int] = set()
        owners = {p.player_id: p for p in self.players}
        for pr in self.projectiles:
            if (pr.turn or pr.return_at) and not self._steer(pr, owners.get(pr.owner)):
                continue  # a boomerang back in its owner's hand
            pr.x += pr.vx * DT
            pr.y += pr.vy * DT
            pr.ticks_left -= 1
            if not pr.flies and self.obstacles.blocks_point(pr.x, pr.y, PROJECTILE_RADIUS):
                events.append(ProjectileBlocked(self.tick, pr.owner, pr.x, pr.y))
                continue
            for e in g.query(pr.x, pr.y, pr.radius + self._max_radius):
                if e.eid in pr.hit_ids or e.eid in killed:
                    continue
                r = e.radius + pr.radius
                if (e.x - pr.x) ** 2 + (e.y - pr.y) ** 2 > r * r:
                    continue
                pr.hit_ids.add(e.eid)
                owner = owners.get(pr.owner)
                self._weapon_hit(owner, pr.owner, e, pr.damage, pr.crit, killed, events, pr.procs)
                if owner is not None and (pr.explode_r or pr.frost):
                    self._impact(owner, pr, e, killed, events)
                pr.hits_left -= 1
                if pr.hits_left <= 0:
                    if pr.bounces_left > 0 and self._bounce(pr, e, killed):
                        continue
                    break
            if pr.ticks_left > 0 and pr.hits_left > 0:
                survivors.append(pr)
        self.projectiles = survivors
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _impact(self, p: Player, pr: Projectile, e: Enemy, killed: set[int], events: list[Event]) -> None:
        """Mira's fireball bursts and sets the area on fire; Ysa's frost shot slows and, three times, freezes."""
        if pr.explode_r:
            radius = pr.explode_r * p.stats.area_mult
            events.append(WeaponPulse(self.tick, p.player_id, "fireball", e.x, e.y, radius))
            burn_t = dict(self.config.character.weapon_extra).get("ignite_s", 3.0)
            for o in self._grid.query(e.x, e.y, radius + self._max_radius):
                r = radius + o.radius
                if o.eid in killed or o.hp <= 0 or (o.x - e.x) ** 2 + (o.y - e.y) ** 2 > r * r:
                    continue
                if o.eid != e.eid:
                    self._weapon_hit(p, p.player_id, o, pr.damage, pr.crit, killed, events, procs=False)
                if o.hp > 0 and pr.burn_pct:
                    dps = pr.damage * pr.burn_pct / 100.0 * p.stats.elemental_mult
                    o.burn_dps, o.burn_t, o.dot_owner = max(o.burn_dps, dps), burn_t, p.player_id
        if pr.frost and e.hp > 0:
            extra = dict(self.config.character.weapon_extra)
            e.frost_stacks += 1
            if e.frost_stacks >= int(extra.get("freeze_stacks", 3)):
                e.frost_stacks = 0
                e.chill_pct, e.chill_t = 100.0, extra.get("freeze_s", 1.2)  # frozen solid
            elif e.chill_t <= 0 or e.chill_pct < extra.get("slow_pct", 30.0):
                e.chill_pct, e.chill_t = extra.get("slow_pct", 30.0), extra.get("slow_s", 2.0)

    def _steer(self, pr: Projectile, owner: Player | None) -> bool:
        """Homing shots turn towards the nearest enemy; boomerangs fly back to their owner.
        Returns False when a boomerang has arrived (it is removed)."""
        speed = math.sqrt(pr.vx * pr.vx + pr.vy * pr.vy) or 1.0
        if pr.return_at:
            if not pr.returning and pr.ticks_left <= pr.return_at:
                pr.returning, pr.hit_ids = True, set()  # hits again on the way back
                pr.ticks_left += 4 * TICK_HZ
            if pr.returning:
                if owner is None:
                    return False
                dx, dy = owner.x - pr.x, owner.y - pr.y
                d = math.sqrt(dx * dx + dy * dy)
                if d < PLAYER_RADIUS + speed * DT:
                    return False
                pr.vx, pr.vy = dx / d * speed, dy / d * speed
            return True
        if (self.tick + pr.owner) % 3:
            return True  # re-aim every third tick
        target, best = None, HOMING_RANGE * HOMING_RANGE
        for e in self._grid.query(pr.x, pr.y, HOMING_RANGE):
            if e.eid in pr.hit_ids:
                continue
            d2 = (e.x - pr.x) ** 2 + (e.y - pr.y) ** 2
            if d2 < best:
                target, best = e, d2
        if target is not None:
            d = math.sqrt(best) or 1.0
            k = min(1.0, pr.turn * DT * 3)
            vx = pr.vx / speed * (1 - k) + (target.x - pr.x) / d * k
            vy = pr.vy / speed * (1 - k) + (target.y - pr.y) / d * k
            n = math.sqrt(vx * vx + vy * vy) or 1.0
            pr.vx, pr.vy = vx / n * speed, vy / n * speed
        return True

    def _bounce(self, pr: Projectile, last: Enemy, killed: set[int]) -> bool:
        """ "Rückprall": turn towards the nearest enemy not hit yet. Returns False when there is none."""
        best, best_d2 = None, BOUNCE_RANGE * BOUNCE_RANGE
        for o in self._grid.query(last.x, last.y, BOUNCE_RANGE):
            if o.eid in pr.hit_ids or o.eid in killed:
                continue
            d2 = (o.x - pr.x) ** 2 + (o.y - pr.y) ** 2
            if d2 < best_d2:
                best, best_d2 = o, d2
        if best is None:
            return False
        speed = math.sqrt(pr.vx * pr.vx + pr.vy * pr.vy)
        d = math.sqrt(best_d2) or 1.0
        pr.vx, pr.vy = (best.x - pr.x) / d * speed, (best.y - pr.y) / d * speed
        pr.bounces_left -= 1
        pr.hits_left = 1
        pr.damage *= BOUNCE_DAMAGE
        pr.ticks_left = max(pr.ticks_left, int(BOUNCE_RANGE / max(speed, 1.0) * TICK_HZ) + 1)
        return True

    def _weapon_hit(self, owner: Player | None, owner_id: int, e: Enemy, dmg: float, crit: bool, killed: set[int],
                    events: list[Event], procs: bool = True) -> None:  # fmt: skip
        """One hit of any player weapon: bonuses, armour and shield, on-hit effects, kill and on-kill effects.

        `procs` is False for damage that on-hit effects caused themselves (explosions, lightning, poison),
        so effects never chain into each other."""
        s = owner.stats if owner is not None else None
        if s is not None:
            if e.elite or e.boss:
                dmg *= s.elite_damage_mult
            if s.execute_damage_pct and e.hp < e.max_hp * EXECUTE_SHARE:  # "Henker"
                dmg *= 1.0 + s.execute_damage_pct / 100.0
            if e.burn_t > 0:  # Mira's "Hitzewelle"
                dmg *= s.burning_damage_mult
        lost = damage_enemy(e, dmg)
        events.append(EnemyHit(self.tick, owner_id, e.eid, e.x, e.y, lost, crit))
        if s is not None and procs:
            if s.lifesteal_pct and owner.alive:
                owner.hp = min(s.max_hp, owner.hp + lost * s.lifesteal_pct / 100.0)
            self._on_hit_effects(owner, e, dmg, killed, events)
        if e.hp <= 0 and e.eid not in killed:
            killed.add(e.eid)
            self._kill(e, owner_id, events)
            if s is None:
                return
            if s.explode_on_kill_pct and self.rng.random() * 100.0 < s.explode_on_kill_pct:
                self._explode(e, owner_id, dmg * KILL_EXPLOSION_DAMAGE * s.area_mult, killed, events)
            if procs and s.shrapnel_chance_pct and self.rng.random() * 100.0 < s.shrapnel_chance_pct:
                self._shrapnel(owner, e, dmg * SHRAPNEL_DAMAGE, events)

    def _on_hit_effects(self, p: Player, e: Enemy, dmg: float, killed: set[int], events: list[Event]) -> None:
        """Status effects and chance effects of one hit. Each roll only happens when the stat exists,
        so a build without them draws exactly the same random numbers as before."""
        s, elem = p.stats, p.stats.elemental_mult
        if e.hp > 0:
            if s.ignite_chance_pct and self.rng.random() * 100.0 < s.ignite_chance_pct:
                e.burn_dps, e.burn_t, e.dot_owner = max(e.burn_dps, dmg * BURN_SHARE * elem), BURN_S, p.player_id
            if s.poison_pct_per_s:
                add = dmg * s.poison_pct_per_s / 100.0 * elem
                e.poison_dps = min(e.poison_dps + add, add * POISON_MAX_STACKS) if e.poison_t > 0 else add
                e.poison_t, e.dot_owner = POISON_S, p.player_id
            if s.chill_slow_pct:
                e.chill_pct, e.chill_t = max(e.chill_pct if e.chill_t > 0 else 0.0, s.chill_slow_pct), CHILL_S
        if s.shock_chance_pct and self.rng.random() * 100.0 < s.shock_chance_pct:
            self._shock(p, e, dmg * SHOCK_DAMAGE * elem, killed, events)
        if s.explosive_hit_pct:
            radius = EXPLOSIVE_HIT_RADIUS * s.area_mult
            events.append(HazardActivated(self.tick, p.player_id, "seed_burst", e.x, e.y, radius))
            for o in self._grid.query(e.x, e.y, radius + self._max_radius):
                r = radius + o.radius
                if o.eid != e.eid and o.eid not in killed and o.hp > 0 and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= r * r:
                    self._weapon_hit(p, p.player_id, o, dmg * s.explosive_hit_pct / 100.0, False, killed, events,
                                     procs=False)  # fmt: skip

    def _shock(self, p: Player, e: Enemy, dmg: float, killed: set[int], events: list[Event]) -> None:
        """A lightning bolt jumps from the hit enemy to the nearest others (SHOCK_JUMPS of them)."""
        points = [(e.x, e.y)]
        hit = {e.eid}
        x, y = e.x, e.y
        for _ in range(SHOCK_JUMPS):
            best, best_d2 = None, SHOCK_RANGE * SHOCK_RANGE
            for o in self._grid.query(x, y, SHOCK_RANGE):
                if o.eid in hit or o.eid in killed or o.hp <= 0:
                    continue
                d2 = (o.x - x) ** 2 + (o.y - y) ** 2
                if d2 < best_d2:
                    best, best_d2 = o, d2
            if best is None:
                break
            hit.add(best.eid)
            points.append((best.x, best.y))
            x, y = best.x, best.y
            self._weapon_hit(p, p.player_id, best, dmg, False, killed, events, procs=False)
        if len(points) > 1:
            events.append(Zap(self.tick, p.player_id, tuple(points)))

    def _shrapnel(self, p: Player, e: Enemy, dmg: float, events: list[Event]) -> None:
        """ "Splitterhagel": splinters fly from the fallen enemy in all directions (no further effects)."""
        life = max(1, int(SHRAPNEL_RANGE / SHRAPNEL_SPEED * TICK_HZ))
        step = len(COMPASS_16) // SHRAPNEL_PIECES
        for k in range(SHRAPNEL_PIECES):
            dx, dy = COMPASS_16[(k * step) % len(COMPASS_16)]
            self.projectiles.append(Projectile(p.player_id, e.x, e.y, dx * SHRAPNEL_SPEED, dy * SHRAPNEL_SPEED, dmg,
                                               False, life, 1, {e.eid}, "shrapnel", procs=False))  # fmt: skip

    def _tick_statuses(self, events: list[Event]) -> None:
        """Poison and burn hurt in half-second pulses (one number instead of sixty), chill wears off."""
        killed: set[int] = set()
        owners = {p.player_id: p for p in self.players}
        for e in self.enemies:
            if e.chill_t > 0:
                e.chill_t -= DT
            if e.poison_t <= 0 and e.burn_t <= 0:
                continue
            e.poison_t -= DT
            e.burn_t -= DT
            if (self.tick + e.eid) % DOT_PULSE_TICKS:
                continue
            dps = (e.poison_dps if e.poison_t > 0 else 0.0) + (e.burn_dps if e.burn_t > 0 else 0.0)
            if e.poison_t > 0 and e.eid not in killed:
                self._count("poison_damage", min(e.hp, e.poison_dps * DOT_PULSE_TICKS * DT))
            if dps > 0 and e.eid not in killed:
                self._weapon_hit(owners.get(e.dot_owner), e.dot_owner, e, dps * DOT_PULSE_TICKS * DT, False, killed,
                                 events, procs=False)  # fmt: skip
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _aura(self, events: list[Event]) -> None:
        """ "Brennnesselkranz": damage around the player in half-second pulses."""
        killed: set[int] = set()
        for p in self.players:
            if not p.alive or not (p.stats.aura_dps or p.inferno_t > 0):
                continue
            p.aura_t -= DT
            if p.aura_t > 0:
                continue
            p.aura_t = DOT_PULSE_TICKS * DT
            dmg = p.stats.aura_dps * DOT_PULSE_TICKS * DT * p.stats.damage / self._base_stats.damage
            radius = AURA_RADIUS * p.stats.area_mult
            if p.inferno_t > 0:  # Mira's "Inferno": a big ring of fire for a few seconds
                dmg += p.stats.damage * INFERNO_DPS_SHARE * DOT_PULSE_TICKS * DT
                radius = max(radius, INFERNO_RADIUS * p.stats.area_mult)
            for e in self._grid.query(p.x, p.y, radius + self._max_radius):
                r = radius + e.radius
                if e.eid not in killed and e.hp > 0 and (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r * r:
                    self._weapon_hit(p, p.player_id, e, dmg, False, killed, events, procs=False)
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    # ------------------------------------------------------------------ extra weapons (Paket C2)

    def _use_weapons(self, events: list[Event]) -> None:
        killed: set[int] = set()
        base = self._base_stats
        for p in self.players:
            if not p.alive or not p.weapons:
                continue
            s = p.stats
            damage_mult = s.damage / base.damage * self.damage_mult(p)
            rate_mult = self.attack_rate(p) / base.attack_rate
            for st in p.weapons:
                w = self._weapon_defs[st.weapon]
                v = w.at(st.level)
                v["damage"] *= damage_mult * (1.0 + st.power)
                if "radius" in v and w.kind != "orbit":
                    v["radius"] *= s.area_mult
                if w.kind == "orbit":
                    self._weapon_orbit(p, st, v, rate_mult, killed, events)
                    continue
                st.cooldown -= DT
                if st.cooldown > 0:
                    continue
                if WEAPON_KINDS[w.kind](self, p, st, v, killed, events):
                    st.cooldown += v["cooldown_s"] / rate_mult
                else:
                    st.cooldown = 0.0  # nothing to hit: ready again as soon as something is
        self._land_bombs(killed, events)
        self._update_placed(killed, events)
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _area_damage(self, p: Player, x: float, y: float, radius: float, damage: float, killed: set[int],
                     events: list[Event]) -> int:  # fmt: skip
        """Hit every enemy touching the circle (no cover). Returns the number of enemies hit."""
        dmg, crit = self._roll_crit(p, damage)
        hits = 0
        for e in self._grid.query(x, y, radius + self._max_radius):
            if e.eid in killed or e.hp <= 0:
                continue
            r = radius + e.radius
            if (e.x - x) ** 2 + (e.y - y) ** 2 > r * r:
                continue
            hits += 1
            self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        return hits

    def _any_enemy_in(self, x: float, y: float, radius: float, killed: set[int]) -> bool:
        for e in self._grid.query(x, y, radius + self._max_radius):
            r = radius + e.radius
            if e.eid not in killed and (e.x - x) ** 2 + (e.y - y) ** 2 <= r * r:
                return True
        return False

    def _weapon_fan(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Thorns or seeds in a fan (or full ring) towards the nearest visible enemy."""
        reach = v["range"] * p.stats.range / self._base_stats.range
        target, d2 = self._pick_target(p, reach)
        if target is None:
            return False
        d = math.sqrt(d2) or 1.0
        dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
        life = max(1, int(reach / v["speed"] * TICK_HZ + 0.5))
        for fx, fy in fan_directions(dx, dy, int(v["count"]), v["spread_deg"]):
            self._fire(p, fx, fy, v["damage"], life, events, v["speed"], int(v["pierce"]), st.weapon)
        return True

    def _weapon_nova(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        if not self._any_enemy_in(p.x, p.y, v["radius"], killed):
            return False
        events.append(WeaponPulse(self.tick, p.player_id, st.weapon, p.x, p.y, v["radius"]))
        self._area_damage(p, p.x, p.y, v["radius"], v["damage"], killed, events)
        return True

    def _weapon_aura(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        return self._area_damage(p, p.x, p.y, v["radius"], v["damage"], killed, events) > 0

    def _weapon_lobbed(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Throw at random enemies in reach (over trees); the burst comes after a visible warning."""
        reach = v["range"] * p.stats.range / self._base_stats.range
        r2 = reach * reach
        targets = [e for e in self.enemies if e.eid not in killed and (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r2]
        if not targets:
            return False
        flight = v["flight_s"]
        for _ in range(int(v["count"])):
            e = targets[self.rng.randint(0, len(targets) - 1)]
            dmg, crit = self._roll_crit(p, v["damage"])
            self.bombs.append(Bomb(p.player_id, st.weapon, p.x, p.y, e.x, e.y, flight, flight, v["radius"], dmg, crit))
        return True

    def _weapon_chain(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Glühwürmchen: a bolt hits the nearest enemy and jumps on to the next ones, weaker each time."""
        target, _ = self._pick_target(p, v["range"] * p.stats.range / self._base_stats.range)
        if target is None:
            return False
        points, hit, e, dmg = [(p.x, p.y), (target.x, target.y)], {target.eid}, target, v["damage"]
        roll, crit = self._roll_crit(p, dmg)
        self._weapon_hit(p, p.player_id, e, roll, crit, killed, events)
        for _ in range(int(v["jumps"])):
            dmg *= v["falloff"]
            best, best_d2 = None, v["jump_range"] ** 2
            for o in self._grid.query(e.x, e.y, v["jump_range"]):
                if o.eid in hit or o.eid in killed or o.hp <= 0:
                    continue
                d2 = (o.x - e.x) ** 2 + (o.y - e.y) ** 2
                if d2 < best_d2:
                    best, best_d2 = o, d2
            if best is None:
                break
            hit.add(best.eid)
            points.append((best.x, best.y))
            e = best
            roll, crit = self._roll_crit(p, dmg)
            self._weapon_hit(p, p.player_id, e, roll, crit, killed, events, procs=False)
        events.append(Zap(self.tick, p.player_id, tuple(points)))
        return True

    def _weapon_boomerang(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Ahornbumerang: flies out through everything, then comes back to you and hits again."""
        reach = v["range"] * p.stats.range / self._base_stats.range
        target, d2 = self._pick_target(p, reach)
        if target is None:
            return False
        d = math.sqrt(d2) or 1.0
        out = max(2, int(reach / v["speed"] * TICK_HZ))
        for fx, fy in fan_directions((target.x - p.x) / d, (target.y - p.y) / d, int(v["count"]), 40.0):
            self._fire(p, fx, fy, v["damage"], 2 * out, events, v["speed"], 999, st.weapon, return_at=out, flies=True)
        return True

    def _weapon_trail(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Brennnesselspur: only while walking, a patch of nettles grows where you were."""
        if p.standing:
            return False
        dmg, _ = self._roll_crit(p, v["damage"])
        self.zones.append(Zone(p.player_id, st.weapon, p.x, p.y, v["radius"], dmg, v["duration_s"]))
        return True

    def _weapon_turret(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Kaktuswächter: plant a cactus where you stand; the oldest withers when there are too many."""
        own = [t for t in self.turrets if t.owner == p.player_id and t.weapon == st.weapon]
        if len(own) >= int(v["count"]):
            self.turrets.remove(own[0])
        reach = v["range"] * p.stats.range / self._base_stats.range
        self.turrets.append(Turret(p.player_id, st.weapon, p.x, p.y, v["life_s"], max(0.15, v["fire_s"]), 0.0,
                                   v["damage"], reach, v["speed"]))  # fmt: skip
        return True

    def _weapon_beam(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Brennglasstrahl: a straight beam through every enemy on the line, plants do not stop it."""
        length = v["length"] * p.stats.range / self._base_stats.range
        target, d2 = self._pick_target(p, length)
        if target is None:
            return False
        d = math.sqrt(d2) or 1.0
        dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
        x2, y2 = p.x + dx * length, p.y + dy * length
        width = v["width"] * p.stats.area_mult
        dmg, crit = self._roll_crit(p, v["damage"])
        for e in self._grid.query((p.x + x2) / 2, (p.y + y2) / 2, length / 2 + self._max_radius):
            if e.eid in killed or e.hp <= 0:
                continue
            t = (e.x - p.x) * dx + (e.y - p.y) * dy
            if 0 <= t <= length and abs((e.x - p.x) * dy - (e.y - p.y) * dx) <= width + e.radius:
                self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        events.append(BeamFired(self.tick, p.player_id, st.weapon, p.x, p.y, x2, y2, width))
        return True

    def _weapon_mine(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Knoblauchminen: only while walking, drop a clove (up to `count` lie around)."""
        if p.standing:
            return False
        if sum(1 for m in self.mines if m.owner == p.player_id and m.weapon == st.weapon) >= int(v["count"]):
            return False
        self.mines.append(Mine(p.player_id, st.weapon, p.x, p.y, v["life_s"], v["damage"], v["radius"], v["trigger"]))
        return True

    def _weapon_homing(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Libellenschwarm: shots that look for their own target and fly over plants."""
        reach = v["range"] * p.stats.range / self._base_stats.range
        target, d2 = self._pick_target(p, reach)
        if target is None:
            return False
        d = math.sqrt(d2) or 1.0
        life = max(2, int(reach * 1.6 / v["speed"] * TICK_HZ))
        for fx, fy in fan_directions((target.x - p.x) / d, (target.y - p.y) / d, int(v["count"]), 120.0):
            self._fire(p, fx, fy, v["damage"], life, events, v["speed"], 0, st.weapon, turn=v["turn"], flies=True)
        return True

    def _weapon_sweep(self, p: Player, st: WeaponState, v: dict, killed: set[int], events: list[Event]) -> bool:
        """Sichel: a sweep in a half circle towards the nearest enemy."""
        radius = v["radius"]
        target, d2 = self._pick_target(p, radius + self._max_radius)
        if target is None:
            return False
        d = math.sqrt(d2) or 1.0
        dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
        min_dot, _ = cos_sin(v["arc_deg"] / 360.0 * math.pi)
        dmg, crit = self._roll_crit(p, v["damage"])
        for e in self._grid.query(p.x, p.y, radius + self._max_radius):
            if e.eid in killed or e.hp <= 0:
                continue
            ex, ey = e.x - p.x, e.y - p.y
            de = math.sqrt(ex * ex + ey * ey)
            if de > radius + e.radius:
                continue
            if de < e.radius + PLAYER_RADIUS or (ex * dx + ey * dy) / de >= min_dot:
                self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        events.append(SweepSwung(self.tick, p.player_id, st.weapon, p.x, p.y, dx, dy, radius, v["arc_deg"]))
        return True

    def _update_placed(self, killed: set[int], events: list[Event]) -> None:
        """Nettle patches pulse, cacti shoot, garlic cloves wait for a foot."""
        owners = {p.player_id: p for p in self.players}
        if self.zones:
            pulse = self.tick % DOT_PULSE_TICKS == 0
            keep = []
            for z in self.zones:
                z.life -= DT
                owner = owners.get(z.owner)
                if pulse and owner is not None:
                    for e in self._grid.query(z.x, z.y, z.radius + self._max_radius):
                        r = z.radius + e.radius
                        if e.eid not in killed and e.hp > 0 and (e.x - z.x) ** 2 + (e.y - z.y) ** 2 <= r * r:
                            self._weapon_hit(owner, z.owner, e, z.damage, False, killed, events, procs=False)
                if z.life > 0:
                    keep.append(z)
            self.zones = keep
        if self.turrets:
            keep_t = []
            for t in self.turrets:
                t.life -= DT
                t.reload -= DT
                owner = owners.get(t.owner)
                if t.reload <= 0 and owner is not None and owner.alive:
                    best, best_d2 = None, t.reach * t.reach
                    for e in self._grid.query(t.x, t.y, t.reach):
                        d2 = (e.x - t.x) ** 2 + (e.y - t.y) ** 2
                        if e.eid not in killed and e.hp > 0 and d2 < best_d2:
                            best, best_d2 = e, d2
                    if best is not None:
                        t.reload = t.fire_s
                        d = math.sqrt(best_d2) or 1.0
                        life = max(2, int(t.reach / t.speed * TICK_HZ) + 2)
                        self._fire(owner, (best.x - t.x) / d, (best.y - t.y) / d, t.damage, life, events, t.speed, 0,
                                   t.weapon, origin=(t.x, t.y), flies=True)  # fmt: skip
                if t.life > 0:
                    keep_t.append(t)
            self.turrets = keep_t
        if self.mines:
            keep_m = []
            for m in self.mines:
                m.life -= DT
                owner = owners.get(m.owner)
                tripped = any(
                    e.eid not in killed and (e.x - m.x) ** 2 + (e.y - m.y) ** 2 <= (m.trigger + e.radius) ** 2
                    for e in self._grid.query(m.x, m.y, m.trigger + self._max_radius)
                )
                if tripped and owner is not None:
                    radius = m.radius * owner.stats.area_mult
                    events.append(WeaponPulse(self.tick, m.owner, m.weapon, m.x, m.y, radius))
                    dmg, crit = self._roll_crit(owner, m.damage)
                    for e in self._grid.query(m.x, m.y, radius + self._max_radius):
                        r = radius + e.radius
                        if e.eid not in killed and e.hp > 0 and (e.x - m.x) ** 2 + (e.y - m.y) ** 2 <= r * r:
                            self._weapon_hit(owner, m.owner, e, dmg, crit, killed, events)
                elif m.life > 0:
                    keep_m.append(m)
            self.mines = keep_m

    def _land_bombs(self, killed: set[int], events: list[Event]) -> None:
        if not self.bombs:
            return
        owners = {p.player_id: p for p in self.players}
        flying: list[Bomb] = []
        for b in self.bombs:
            b.delay -= DT
            if b.delay > 0:
                flying.append(b)
                continue
            events.append(WeaponPulse(self.tick, b.owner, b.weapon, b.tx, b.ty, b.radius))
            owner = owners.get(b.owner)
            for e in self._grid.query(b.tx, b.ty, b.radius + self._max_radius):
                r = b.radius + e.radius
                if e.eid in killed or e.hp <= 0 or (e.x - b.tx) ** 2 + (e.y - b.ty) ** 2 > r * r:
                    continue
                self._weapon_hit(owner, b.owner, e, b.damage, b.crit, killed, events)
        self.bombs = flying

    def _weapon_orbit(self, p: Player, st: WeaponState, v: dict, rate_mult: float, killed: set[int],
                      events: list[Event]) -> None:  # fmt: skip
        """Orbiters circle the player and sting each enemy at most once per cooldown."""
        rotate(st, v["turns_per_s"] * DT)
        hit_r = v["hit_radius"]
        wait = max(1, int(v["cooldown_s"] / rate_mult * TICK_HZ + 0.5))
        ready = st.hit_ready
        for bx, by in orbit_positions(st, p.x, p.y, int(v["count"]), v["radius"]):
            for e in self._grid.query(bx, by, hit_r + self._max_radius):
                if e.eid in killed or e.hp <= 0 or ready.get(e.eid, 0) > self.tick:
                    continue
                r = hit_r + e.radius
                if (e.x - bx) ** 2 + (e.y - by) ** 2 > r * r:
                    continue
                ready[e.eid] = self.tick + wait
                dmg, crit = self._roll_crit(p, v["damage"])
                self._weapon_hit(p, p.player_id, e, dmg, crit, killed, events)
        if len(ready) > 256:  # forget enemies that are gone or long ready again
            st.hit_ready = {eid: t for eid, t in ready.items() if t > self.tick}

    def _move_enemy_shots(self, events: list[Event]) -> None:
        survivors: list[EnemyShot] = []
        for s in self.enemy_shots:
            s.x += s.vx * DT
            s.y += s.vy * DT
            s.ticks_left -= 1
            if s.lobbed:
                if s.ticks_left <= 0 and s.on_land is not None:
                    self.add_hazard(s.on_land, s.tx, s.ty, s.source)
                    events.append(HazardActivated(self.tick, None, s.on_land.kind, s.tx, s.ty, s.on_land.radius))
                elif s.ticks_left > 0:
                    survivors.append(s)
                continue
            if self.obstacles.blocks_point(s.x, s.y, ENEMY_SHOT_RADIUS):
                continue
            hit = False
            for p in self.players:
                r = PLAYER_RADIUS + ENEMY_SHOT_RADIUS
                if p.alive and (p.x - s.x) ** 2 + (p.y - s.y) ** 2 <= r * r:
                    self._hurt(p, s.damage, events)
                    hit = True
                    break
            if not hit and s.ticks_left > 0:
                survivors.append(s)
        self.enemy_shots = survivors

    def _update_hazards(self, events: list[Event]) -> None:
        for p in self.players:
            p.slow_pct = 0.0
        survivors: list[Hazard] = []
        for h in self.hazards:
            spec = h.spec
            if h.delay > 0:
                h.delay -= DT
                if h.delay <= 0:
                    events.append(HazardActivated(self.tick, None, spec.kind, h.x, h.y, spec.radius))
                    if spec.burst:
                        for p in self._players_in(h.x, h.y, spec.radius):
                            self._hurt(p, spec.burst, events)
                survivors.append(h)
                continue
            for p in self._players_in(h.x, h.y, spec.radius):
                if spec.dps:
                    self._hurt(p, spec.dps * DT, events, use_i_frames=False)
                if spec.slow_pct:
                    p.slow_pct = max(p.slow_pct, spec.slow_pct)
            h.duration -= DT
            if h.duration > 0:
                survivors.append(h)
        self.hazards = survivors

    def _players_in(self, x: float, y: float, radius: float) -> list[Player]:
        r = radius + PLAYER_RADIUS
        return [p for p in self.players if p.alive and (p.x - x) ** 2 + (p.y - y) ** 2 <= r * r]

    def _contact_damage(self, events: list[Event]) -> None:
        g = self._grid
        reach = PLAYER_RADIUS + self._max_radius
        thorn_kills: set[int] = set()
        for p in self.players:
            if not p.alive or p.i_frames > 0:
                continue
            for e in g.query(p.x, p.y, reach):
                r = e.radius + PLAYER_RADIUS
                if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 <= r * r:
                    before = p.hp
                    self._hurt(p, e.damage, events)
                    if "vampiric" in e.affixes:
                        e.hp = min(e.max_hp, e.hp + (before - p.hp))
                    reflect = p.stats.thorns + (before - p.hp) * p.stats.thorns_pct / 100.0
                    if reflect > 0 and e.hp > 0:  # "Brennnessel", "Dornenpanzer"
                        damage_enemy(e, reflect)
                        if e.hp <= 0:
                            thorn_kills.add(e.eid)
                            self._kill(e, p.player_id, events)
                    break
        if thorn_kills:
            self.enemies = [e for e in self.enemies if e.eid not in thorn_kills]
            self._rebuild_grid()

    def _collect_pickups(self, events: list[Event]) -> None:
        alive = [p for p in self.players if p.alive]
        if not alive:
            return
        if self.chests:
            self._open_chests(alive, events)
        if self.pots:
            self._break_pots(alive, events)
        if self.shrines:
            self._charge_shrines(alive, events)
        if self.pickups:
            remaining_pickups = []
            for k in self.pickups:
                r2 = (PICKUP_RADIUS + PLAYER_RADIUS) ** 2
                owner = next((p for p in alive if (p.x - k.x) ** 2 + (p.y - k.y) ** 2 <= r2), None)
                if owner is None:
                    remaining_pickups.append(k)
                    continue
                events.append(PickupCollected(self.tick, owner.player_id, k.kind, k.x, k.y))
                if k.kind == "magnet":
                    for o in self.orbs:
                        o.magnet_to = owner.player_id
            self.pickups = remaining_pickups
        if not self.orbs:
            return
        remaining: list[XpOrb] = []
        by_id = {p.player_id: p for p in alive}
        for o in self.orbs:
            owner, best = None, math.inf
            magnet = by_id.get(o.magnet_to) if o.magnet_to is not None else None
            if magnet is not None:
                owner, best = magnet, (magnet.x - o.x) ** 2 + (magnet.y - o.y) ** 2
            else:
                for p in alive:
                    d2 = (p.x - o.x) ** 2 + (p.y - o.y) ** 2
                    if d2 <= p.stats.pickup_radius * p.stats.pickup_radius and d2 < best:
                        owner, best = p, d2
            if owner is None:
                remaining.append(o)
                continue
            step = (MAGNET_ORB_SPEED if magnet is not None else ORB_SPEED) * DT
            d = math.sqrt(best)
            if d <= PLAYER_RADIUS + step:
                self._collect_orb(owner, o, events)
                continue
            o.x += (owner.x - o.x) / d * step
            o.y += (owner.y - o.y) / d * step
            remaining.append(o)
        self.orbs = remaining

    def _collect_orb(self, owner: Player, o: XpOrb, events: list[Event]) -> None:
        if o.kind == "seeds":
            amount = int(round(o.value * owner.stats.gold_mult))
            owner.seeds += amount
            events.append(SeedsCollected(self.tick, owner.player_id, amount))
        elif o.kind == "heal":
            owner.hp = min(owner.stats.max_hp, owner.hp + o.value)
        else:
            self._gain_xp(owner, o.value * owner.stats.xp_mult, events)

    def _open_chests(self, alive: list[Player], events: list[Event]) -> None:
        """Touch a chest to open it. Map chests cost seeds (price grows per opened chest); others are free."""
        eco = self.config.economy
        remaining = []
        r2 = (CHEST_PICKUP_RADIUS + PLAYER_RADIUS) ** 2
        for c in self.chests:
            owner = next((p for p in alive if (p.x - c.x) ** 2 + (p.y - c.y) ** 2 <= r2), None)
            if owner is None:
                remaining.append(c)
                continue
            if c.kind == "map" and eco is not None:
                price = eco.chest_price(self.chests_opened)
                if owner.seeds < price:
                    if self.tick >= self._locked_until.get(owner.player_id, 0):
                        events.append(ChestLocked(self.tick, owner.player_id, price))
                        self._locked_until[owner.player_id] = self.tick + TICK_HZ
                    remaining.append(c)
                    continue
                owner.seeds -= price
                self.chests_opened += 1
            events.append(ChestOpened(self.tick, owner.player_id, c.kind))
            self._give_item(owner, c.kind, events)
        self.chests = remaining

    def _count(self, key: str, amount: float = 1.0) -> None:
        self.run_stats[key] = self.run_stats.get(key, 0.0) + amount

    def _track_run_stats(self) -> None:
        """Per tick: seconds at low HP, and run-wide waves (on the leaderboard clock) passed without damage."""
        for p in self.players:
            if p.alive and p.hp < CHALLENGE_LOW_HP_SHARE * p.max_hp:
                self._count("low_hp_s", DT)
        wave = int(self.time_s // LEADERBOARD_WAVE_S) + 1
        if wave != self._run_wave:
            if self._run_wave and not self._wave_hurt:
                self.run_stats["flawless_wave"] = max(self.run_stats.get("flawless_wave", 0.0), self._run_wave)
            self._run_wave, self._wave_hurt = wave, False

    def _charge_shrines(self, alive: list[Player], events: list[Event]) -> None:
        """Standing in a shrine's circle charges it (the Gier-Schrein only while standing still);
        outside, the charge drains twice as fast. A full shrine raises D, rewards and disappears."""
        remaining = []
        for sh in self.shrines:
            r = sh.rules
            r2 = r.radius * r.radius
            owner = next((p for p in alive if (p.x - sh.x) ** 2 + (p.y - sh.y) ** 2 <= r2
                          and (p.standing or not r.still)), None)  # fmt: skip
            if owner is None:
                sh.charge = max(0, sh.charge - 2)
                remaining.append(sh)
                continue
            sh.charge += 1
            if sh.charge < round(r.channel_s * TICK_HZ):
                remaining.append(sh)
                continue
            self.difficulty += r.difficulty_add
            owner.shrines_activated += 1
            if r.id == "greed":
                owner.shrine_mods["xp_gain_pct"] = owner.shrine_mods.get("xp_gain_pct", 0.0) + GREED_XP_PCT
                self._recompute(owner)
            elif r.id == "courage":
                owner.pending_chests.append(COURAGE_MIN_RARITY)
                self._offer(owner, events)
            elif r.id == "curse" and self.curse_total < CURSE_MAX_COPIES:
                self.curse_total += 1
                self.curse_pending += 1  # the next bed boss brings a copy
            elif r.id == "elite":
                for _ in range(ELITE_SHRINE_COUNT):
                    self._spawn_elite(events)
            events.append(ShrineActivated(self.tick, owner.player_id, r.id, r.name, sh.x, sh.y, self.difficulty))
        self.shrines = remaining

    def _break_pots(self, alive: list[Player], events: list[Event]) -> None:
        eco = self.config.economy
        remaining = []
        r2 = (POT_RADIUS + PLAYER_RADIUS) ** 2
        for pot in self.pots:
            owner = next((p for p in alive if (p.x - pot.x) ** 2 + (p.y - pot.y) ** 2 <= r2), None)
            if owner is None or eco is None:
                remaining.append(pot)
                continue
            content = pick_weighted(self.rng, eco.pot_contents)
            if content == "seeds":
                amount = self.rng.randint(*eco.pot_seeds)
                self.orbs.append(XpOrb(pot.x, pot.y, float(amount), kind="seeds"))
            elif content == "heal":
                self.orbs.append(XpOrb(pot.x, pot.y, eco.heal_orb_hp, kind="heal"))
            elif content == "magnet":
                self.pickups.append(Pickup("magnet", pot.x, pot.y))
            events.append(PotBroken(self.tick, owner.player_id, pot.x, pot.y, content))
        self.pots = remaining

    def _gain_xp(self, p: Player, value: float, events: list[Event]) -> None:
        p.xp += value
        sc = self.config.scaling
        while p.xp >= sc.xp_needed(p.level):
            p.xp -= sc.xp_needed(p.level)
            p.level += 1
            p.pending_levels += 1
            events.append(LevelUp(self.tick, p.player_id, p.level))
        self._offer(p, events)

    # ------------------------------------------------------------------ results

    def result(self, player_id: int = 0) -> RunResult:
        """Score and stats of one player's run so far (final once the run is over)."""
        p = next(p for p in self.players if p.player_id == player_id)
        seconds = int(self.time_s)
        if self.config.score is None:
            raise ValueError("WorldConfig.score is missing (use WorldConfig.from_content)")
        flood = self.flood_ticks // TICK_HZ
        score = compute_score(self.config.score, seconds, p.kills, p.level, self.bosses_killed, self.difficulty,
                              self.victory, flood)  # fmt: skip
        return RunResult(
            character=self.config.character.id,
            seed=self.seed,
            seconds=seconds,
            wave=seconds // LEADERBOARD_WAVE_S,  # the leaderboard's wave clock (30 s), checked against the time
            kills=p.kills,
            level=p.level,
            bosses=self.bosses_killed,
            difficulty=self.difficulty,
            victory=self.victory,
            swarm_seconds=flood,
            swarm_mult=1.0,
            damage_taken=p.damage_taken,
            score=score,
            stage=self.stage_cfg.index,
            elites=self.elites_killed,
            chests=self.chests_opened,
            shrines=p.shrines_activated,
            stats=dict(self.run_stats),
            boss_ids=list(self.bosses_defeated),
            owned=sorted(set(p.upgrades) | set(p.items)),
        )

    # ------------------------------------------------------------------ views

    def snapshot(self) -> Snapshot:
        sc = self.config.scaling
        ch = self.config.character
        boss = next((e for e in self.enemies if e.boss), None)
        return Snapshot(
            tick=self.tick,
            time_s=self.time_s,
            wave=self.wave,
            arena_w=self.config.arena_w,
            arena_h=self.config.arena_h,
            over=self.over,
            paused=self.paused,
            difficulty=self.difficulty,
            players=tuple(
                PlayerView(
                    p.player_id,
                    p.x,
                    p.y,
                    p.standing,
                    p.hp,
                    p.stats.max_hp,
                    p.alive,
                    p.i_frames > 0,
                    p.kills,
                    p.level,
                    p.xp,
                    sc.xp_needed(p.level),
                    tuple(
                        (uid, self.card_levels(p).get(uid, 0), tier)
                        for uid, tier in zip(p.offer, p.offer_tiers or ("common",) * len(p.offer), strict=True)
                    ),
                    tuple(p.upgrades.items()),
                    p.offer_source,
                    p.slow_pct > 0,
                    1.0 - p.ability_cooldown / (ch.active_cooldown_s * p.stats.cooldown_mult)
                    if ch.active_cooldown_s
                    else 1.0,
                    p.seeds,
                    tuple(p.items.items()),
                    p.rerolls,
                    p.banishes,
                    tuple((st.weapon, st.level) for st in p.weapons),
                    p.shield + p.temp_shield,
                    max(0, p.stats.revives - p.revives_used),
                    tuple(p.card_tiers.items()),
                    p.inferno_t > 0,
                    p.storm_t > 0,
                )
                for p in self.players
            ),
            enemies=tuple(
                EnemyView(
                    e.eid,
                    e.kind,
                    e.x,
                    e.y,
                    e.radius,
                    e.hp / e.max_hp,
                    e.elite,
                    e.boss is not None,
                    e.shield / e.shield_max if e.shield_max else 0.0,
                    (e.cdx, e.cdy) if e.charge_state == 1 else None,
                    "frozen"
                    if e.chill_t > 0 and e.chill_pct >= 100
                    else "burn"
                    if e.burn_t > 0
                    else "poison"
                    if e.poison_t > 0
                    else "chill"
                    if e.chill_t > 0
                    else "",
                )
                for e in self.enemies
            ),  # fmt: skip
            projectiles=tuple(ProjectileView(pr.x, pr.y, pr.crit, pr.weapon, pr.vx, pr.vy) for pr in self.projectiles),
            orbs=tuple(OrbView(o.x, o.y, o.value, o.kind) for o in self.orbs),
            enemy_shots=tuple(EnemyShotView(s.x, s.y, s.lobbed, s.tx, s.ty) for s in self.enemy_shots),
            hazards=tuple(HazardView(h.spec.kind, h.x, h.y, h.spec.radius, h.delay <= 0) for h in self.hazards),
            chests=tuple((c.x, c.y, c.kind) for c in self.chests),
            pots=tuple((pot.x, pot.y) for pot in self.pots),
            shrines=tuple(
                (sh.rules.id, sh.x, sh.y, sh.rules.radius, sh.charge / (sh.rules.channel_s * TICK_HZ))
                for sh in self.shrines
            ),  # fmt: skip
            chest_price=self.config.economy.chest_price(self.chests_opened) if self.config.economy else 0,
            pickups=tuple((k.kind, k.x, k.y) for k in self.pickups),
            boss_bar=BossBar(boss.boss, boss.hp / boss.max_hp, boss.phase) if boss else None,
            stage=self.stage_cfg.index,
            stage_name=self.stage_cfg.name,
            biome=self.stage_cfg.biome,
            stage_time_s=self.stage_time_s,
            stage_duration_s=self.stage_cfg.duration_s,
            flood=self.flood_s > 0,
            shrine_radar=self.shrine_radar,
            flood_wave=self.flood_wave,
            reward_mult=self.reward_mult,
            gate=self.gate,
            victory=self.victory,
            obstacles=self.stage_cfg.obstacles,
            **self._weapon_views(),
        )

    def _weapon_views(self) -> dict:
        orbiters, auras = [], []
        for p in self.players:
            if not p.alive:
                continue
            for st in p.weapons:
                w = self._weapon_defs[st.weapon]
                if w.kind == "orbit":
                    v = w.at(st.level)
                    spots = orbit_positions(st, p.x, p.y, int(v["count"]), v["radius"])
                    orbiters += [(st.weapon, x, y) for x, y in spots]
                elif w.kind == "aura":
                    auras.append((st.weapon, p.x, p.y, w.at(st.level)["radius"]))
        bombs = []
        for b in self.bombs:
            t = 1.0 - b.delay / b.flight if b.flight > 0 else 1.0
            bombs.append(BombView(b.x + (b.tx - b.x) * t, b.y + (b.ty - b.y) * t, b.tx, b.ty, t, b.radius))
        return dict(
            orbiters=tuple(orbiters),
            auras=tuple(auras),
            bombs=tuple(bombs),
            zones=tuple((z.weapon, z.x, z.y, z.radius, z.life) for z in self.zones),
            turrets=tuple((t.weapon, t.x, t.y, t.life) for t in self.turrets),
            mines=tuple((m.weapon, m.x, m.y) for m in self.mines),
        )

    def positions(self) -> tuple[dict[int, tuple[float, float]], dict[int, tuple[float, float]]]:
        """Player and enemy positions now; taken before a step, they let the renderer draw between ticks."""
        return {p.player_id: (p.x, p.y) for p in self.players}, {e.eid: (e.x, e.y) for e in self.enemies}

    def state_hash(self) -> str:
        """Hash over the full simulation state, for determinism tests and later desync detection."""
        h = hashlib.sha256()
        h.update(struct.pack("<qqq?qdd", self.seed, self.tick, self.wave, self.over, self._next_eid, self._budget,
                             self.difficulty))  # fmt: skip
        h.update(struct.pack("<4I", *self.rng.getstate()))
        h.update(repr((self.stage, self.stage_tick, self.gate, self.victory, self.flood_ticks, self._boss_spawned,
                       self._gate_ready_tick)).encode())  # fmt: skip
        h.update((self._pending_mob.id if self._pending_mob else "").encode())
        for p in self.players:
            h.update(
                struct.pack(
                    "<i7d?iidid", p.player_id, p.x, p.y, p.vx, p.vy, p.hp, p.shot_cooldown, p.i_frames, p.alive,
                    p.kills, p.level, p.xp, p.pending_levels, p.slow_pct,
                )
            )  # fmt: skip
            h.update(repr((sorted(p.upgrades.items()), p.offer, p.pending_chests)).encode())
        for e in self.enemies:
            h.update(struct.pack("<i6d", e.eid, e.x, e.y, e.hp, e.shield, e.timer, e.speed))
            h.update(struct.pack("<i", e.frost_stacks))
            h.update(struct.pack("<i9d", e.charge_state, e.charge_t, e.cdx, e.cdy, e.poison_dps, e.poison_t,
                                 e.burn_dps, e.burn_t, e.chill_pct, e.chill_t))  # fmt: skip
            h.update(repr((e.affixes, e.phase, e.timers, e.volley)).encode())
        for pr in self.projectiles:
            h.update(struct.pack("<i4d2i", pr.owner, pr.x, pr.y, pr.vx, pr.vy, pr.ticks_left, pr.hits_left))
        for s in self.enemy_shots:
            h.update(struct.pack("<4di?", s.x, s.y, s.vx, s.vy, s.ticks_left, s.lobbed))
        for hz in self.hazards:
            h.update(struct.pack("<4d", hz.x, hz.y, hz.delay, hz.duration))
        for o in self.orbs:
            h.update(struct.pack("<3d", o.x, o.y, o.value))
        for c in self.chests:
            h.update(struct.pack("<2d", c.x, c.y) + c.kind.encode())
        for pot in self.pots:
            h.update(struct.pack("<2d", pot.x, pot.y))
        for sh in self.shrines:
            h.update(sh.rules.id.encode() + struct.pack("<2di", sh.x, sh.y, sh.charge))
        h.update(struct.pack("<d2i", self.difficulty, self.curse_total, self.curse_pending))
        h.update(repr([(p.seeds, sorted(p.items.items()), p.rerolls, p.banishes, sorted(p.banished))
                       for p in self.players]).encode() + struct.pack("<q", self.chests_opened))  # fmt: skip
        h.update(repr([o.kind for o in self.orbs]).encode())
        for k in self.pickups:
            h.update(k.kind.encode() + struct.pack("<2d", k.x, k.y))
        h.update(struct.pack(f"<{len(self.players)}d", *(p.ability_cooldown for p in self.players)))
        for p in self.players:
            h.update(
                repr(
                    (p.shots_fired, p.last_dx, p.last_dy, p.inferno_t, p.storm_t, p.temp_shield, p.temp_shield_t)
                ).encode()
            )
            h.update(repr((sorted(p.upgrade_power.items()), p.offer_tiers, sorted(p.card_tiers.items()), p.haste_pct,
                           p.haste_t, p.overcharge_t, p.shield, p.shield_t, p.revives_used,
                           p.aura_t)).encode())  # fmt: skip
        h.update(repr([o.magnet_to for o in self.orbs]).encode())
        for p in self.players:
            for st in p.weapons:
                h.update(st.weapon.encode() + struct.pack("<i4d", st.level, st.cooldown, st.ux, st.uy, st.power))
                h.update(repr(list(st.hit_ready.items())).encode())
        h.update(repr([(z.x, z.y, z.life, z.damage) for z in self.zones]).encode())
        h.update(repr([(t.x, t.y, t.life, t.reload) for t in self.turrets]).encode())
        h.update(repr([(m.x, m.y, m.life) for m in self.mines]).encode())
        h.update(repr([(pr.returning, pr.return_at, pr.turn) for pr in self.projectiles]).encode())
        for b in self.bombs:
            h.update(b.weapon.encode() + struct.pack("<i7d?", b.owner, b.x, b.y, b.tx, b.ty, b.delay, b.radius,
                                                     b.damage, b.crit))  # fmt: skip
        return h.hexdigest()


ABILITIES = {
    "arrow_storm": World._arrow_storm,
    "inferno": World._inferno,
    "shadow_step": World._shadow_step,
    "bulwark": World._bulwark,
    "ice_age": World._ice_age,
    "thunderstorm": World._thunderstorm,
}
WEAPON_KINDS = {
    "fan": World._weapon_fan,
    "nova": World._weapon_nova,
    "aura": World._weapon_aura,
    "lobbed": World._weapon_lobbed,
    "chain": World._weapon_chain,
    "boomerang": World._weapon_boomerang,
    "trail": World._weapon_trail,
    "turret": World._weapon_turret,
    "beam": World._weapon_beam,
    "mine": World._weapon_mine,
    "homing": World._weapon_homing,
    "sweep": World._weapon_sweep,
}  # "orbit" runs every tick (World._weapon_orbit), not on a cooldown


def _sign(v: int) -> int:
    return -1 if v < 0 else (1 if v > 0 else 0)
