"""Headless simulation. Never imports pygame (tests/test_sim_has_no_pygame.py).

Scope so far:
- M2: stop-and-shoot, time-based wave budget, enemy scaling, XP orbs, level-up cards.
- M3: static obstacles from the biome data (forest trees block movement and projectiles).
- M4: all phase-1 mob behaviours (enemies.py), enemy projectiles and hazards, elites with
  affixes and chests every few waves, biome boss with phases and a boss chest.
- Paket C2: extra weapons from level-up cards (weapons.py), up to `weapon_slots` incl. the start weapon.

Determinism: only + - * / and sqrt (correctly rounded in IEEE 754), no trigonometry,
all randomness from `self.rng`, all iteration over lists in insertion order.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import NamedTuple

from .arena import Obstacle, ObstacleMap, obstacles_from_content
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
    HazardActivated,
    ItemGained,
    LevelUp,
    PickupCollected,
    PlayerDied,
    PlayerHit,
    PotBroken,
    ProjectileBlocked,
    RunEnded,
    RunStarted,
    SeedsCollected,
    ShotFired,
    UpgradeChosen,
    UpgradeOffered,
    WaveStarted,
    WeaponPulse,
)
from .rng import Rng
from .score import RunResult, ScoreRules, compute_score
from .spatial import SpatialHash
from .tuning import (
    ARROW_STORM_DAMAGE,
    ARROW_STORM_SHOTS,
    BOSS_MIN_SPAWN_DISTANCE,
    CHEST_PICKUP_RADIUS,
    ENEMY_SHOT_RADIUS,
    EXTRA_ATTACK_DAMAGE,
    KILL_EXPLOSION_DAMAGE,
    KILL_EXPLOSION_RADIUS,
    MAGNET_DROP_PCT,
    MAGNET_ORB_SPEED,
    ORB_SPEED,
    PICKUP_RADIUS,
    PLAYER_RADIUS,
    POT_RADIUS,
    PROJECTILE_RADIUS,
    SPREAD_COS,
    SPREAD_SIN,
    SWARM_SPREAD,
    VOLATILE_DELAY_S,
    VOLATILE_RADIUS,
)
from .upgrades import RARITIES, UpgradeDef, derive_stats, modifier_sums, roll_offer
from .waves import BiomeArea, Scaling, biome_areas_from_content, biome_at
from .weapons import WEAPON_PREFIX, Bomb, WeaponDef, WeaponState, fan_directions, orbit_positions, rotate

TICK_HZ = 60
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
class WorldConfig:
    character: CharacterStats
    mobs: tuple[MobStats, ...]
    upgrades: tuple[UpgradeDef, ...]
    scaling: Scaling
    biomes: tuple[BiomeArea, ...] = ()
    obstacles: tuple[Obstacle, ...] = ()
    bosses: tuple[BossStats, ...] = ()
    boss_chests: tuple[tuple[str, str], ...] = ()  # (boss id, min rarity of its chest)
    items: tuple[ItemDef, ...] = ()
    weapons: tuple[WeaponDef, ...] = ()
    weapon_slots: int = 1  # including the character's own weapon
    economy: Economy | None = None
    elite: EliteRules | None = None
    rarity_weights: dict[str, float] = field(default_factory=dict)
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
            if b.impl_phase <= max_phase and b.id in BOSS_BEHAVIORS and b.spawn_time_s is not None
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
            biomes=biome_areas_from_content(content),
            obstacles=obstacles_from_content(content, max_phase),
            bosses=bosses,
            boss_chests=tuple((b.id, BOSS_CHEST_RARITY.get(content.boss(b.id).reward, "epic")) for b in bosses),
            elite=EliteRules.from_content(content),
            items=tuple(ItemDef.from_content(i) for i in content.items),
            economy=Economy.from_content(content) if content.economy else None,
            rarity_weights={k: float(v) for k, v in bal.rarity_weights.items()},
            level_up_choices=bal.level_up_choices,
            luck_shift=float(bal.raw["luck_shift_per_point"]),
            arena_w=float(bal.arena_tiles[0] * bal.tile_px),
            arena_h=float(bal.arena_tiles[1] * bal.tile_px),
            wave_interval_s=bal.wave_interval_s,
            spawn_distance=(float(lo), float(hi)),
            max_alive_enemies=bal.max_alive_enemies,
            player_count=player_count,
            score=ScoreRules.from_content(content),
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
    offer: tuple[tuple[str, int], ...]  # (upgrade id, current level)
    upgrades: tuple[tuple[str, int], ...]
    offer_source: str
    slowed: bool
    ability_ready: float = 1.0  # 0 right after use, 1 when ready again
    seeds: int = 0
    items: tuple[tuple[str, int], ...] = ()
    rerolls: int = 0
    banishes: int = 0
    weapons: tuple[tuple[str, int], ...] = ()  # extra weapons (id, level) in pick order


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


class ProjectileView(NamedTuple):
    x: float
    y: float
    crit: bool
    weapon: str = ""  # "" for the character's own weapon


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
    chest_price: int = 0
    orbiters: tuple[tuple[str, float, float], ...] = ()  # (weapon, x, y), e.g. bees
    auras: tuple[tuple[str, float, float, float], ...] = ()  # (weapon, x, y, radius)
    bombs: tuple[BombView, ...] = ()


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
    pickups: list[Pickup] = field(default_factory=list)
    bombs: list[Bomb] = field(default_factory=list)
    rng: Rng = field(init=False)

    def __post_init__(self) -> None:
        cfg = self.config
        self.rng = Rng(self.seed)
        self.difficulty = cfg.difficulty
        self._next_eid = 0
        self._budget = 0.0
        self._pending_mob: MobStats | None = None
        self._grid = SpatialHash(GRID_CELL)
        self.obstacles = ObstacleMap(cfg.obstacles)
        self._upgrade_defs = {u.id: u for u in cfg.upgrades}
        self._item_defs = {i.id: i for i in cfg.items}
        self._weapon_defs = {w.id: w for w in cfg.weapons}
        self._weapon_cards = tuple(
            UpgradeDef(w.card_id, w.rarity, w.max_level, ("weapon",), (), w.impl_phase, True) for w in cfg.weapons
        )
        self._base_stats = derive_stats(cfg.character, {})
        self.chests_opened = 0
        self._locked_until: dict[int, int] = {}
        self._mobs = {m.id: m for m in cfg.mobs}
        self.boss_stats = {b.id: b for b in cfg.bosses}
        self._boss_chest = dict(cfg.boss_chests)
        self._bosses_due = sorted(cfg.bosses, key=lambda b: b.spawn_time_s)
        self._max_radius = max([m.radius for m in cfg.mobs] + [b.radius for b in cfg.bosses] + [PLAYER_RADIUS])
        if cfg.elite:
            self._max_radius = max(self._max_radius, max((m.radius for m in cfg.mobs), default=0) * cfg.elite.size_mult)
        cx, cy = cfg.arena_w / 2, cfg.arena_h / 2
        if not self.players:
            # Players spawn next to each other in the central clearing.
            stats = derive_stats(cfg.character, {})
            self.players = [
                Player(pid, cx + (pid - (cfg.player_count - 1) / 2) * 32.0, cy, stats.max_hp, stats)
                for pid in range(cfg.player_count)
            ]
        self._pending: list[Event] = [RunStarted(0, None, self.seed)]
        self.bosses_killed = 0
        eco = cfg.economy
        if eco is not None:
            for p in self.players:
                p.rerolls, p.banishes = eco.rerolls, eco.banishes
            if cfg.enemy_target is None:  # tests and benchmarks keep an empty map
                # Own random stream for the layout: differs per run, never shifts the main stream.
                layout = Rng(self.seed ^ 0x5EED5)
                start = (cx, cy)
                spots = scatter(layout, eco.chest_count + eco.pot_count, cfg.arena_w, cfg.arena_h, self.obstacles,
                                start, 220.0)  # fmt: skip
                self.chests = [MapChest(x, y, "map") for x, y in spots[: eco.chest_count]]
                self.pots = [Pot(x, y) for x, y in spots[eco.chest_count :]]

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    @property
    def paused(self) -> bool:
        """Single player: an open upgrade choice pauses the game. Co-op will keep running (section 18)."""
        return self.config.player_count == 1 and any(p.offer for p in self.players if p.alive)

    @property
    def reward_mult(self) -> float:
        return 1.0 + 0.8 * (self.difficulty - 1.0)

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
        self._spawn(events)
        self._spawn_bosses(events)
        self._rebuild_grid()
        self._move_enemies(events)
        self._rebuild_grid()
        self._shoot(events)
        self._use_weapons(events)
        self._move_projectiles(events)
        self._move_enemy_shots(events)
        self._update_hazards(events)
        self._contact_damage(events)
        self._collect_pickups(events)

        self.tick += 1
        # Wave n starts at n * wave_interval_s: 0:00-0:30 is wave 0, boss wave 10 = 5:00 (decided, M0).
        wave = self.tick // (self.config.wave_interval_s * TICK_HZ)
        if wave != self.wave:
            self.wave = wave
            events.append(WaveStarted(self.tick, None, wave))
            elite = self.config.elite
            if elite and self.config.enemy_target is None and wave % elite.every_n_waves == 0:
                self._spawn_elite(events)
        if not any(p.alive for p in self.players):
            self.over = True
            events.append(RunEnded(self.tick, None, self.time_s))
        return events

    # ------------------------------------------------------------------ players

    def _apply_choices(self, inputs: dict[int, PlayerInput], events: list[Event]) -> None:
        for p in self.players:
            inp = inputs.get(p.player_id)
            if not p.offer or inp is None:
                continue
            if inp.reroll and p.rerolls > 0:
                p.rerolls -= 1
                p.offer = ()
                self._offer(p, events)
                continue
            if inp.banish is not None and 0 <= inp.banish < len(p.offer) and p.banishes > 0:
                p.banishes -= 1
                p.banished.add(p.offer[inp.banish])
                p.offer = ()
                self._offer(p, events)
                continue
            if inp.choice is None or not 0 <= inp.choice < len(p.offer):
                continue
            uid = p.offer[inp.choice]
            if uid.startswith(WEAPON_PREFIX):
                level = self._add_weapon(p, uid[len(WEAPON_PREFIX) :])
            else:
                p.upgrades[uid] = level = p.upgrades.get(uid, 0) + 1
                self._recompute(p)
            if p.offer_source == "chest":
                p.pending_chests.pop(0)
            else:
                p.pending_levels -= 1
            p.offer, p.offer_source = (), ""
            events.append(UpgradeChosen(self.tick, p.player_id, uid, level))
            self._offer(p, events)

    def _recompute(self, p: Player) -> None:
        """Stats from character, upgrades and items. Max-HP gains also heal by the same amount."""
        old_max = p.stats.max_hp
        mods = modifier_sums(p.upgrades, self._upgrade_defs, p.items, self._item_defs)
        p.stats = derive_stats(self.config.character, mods)
        p.hp = min(p.stats.max_hp, p.hp + max(0.0, p.stats.max_hp - old_max))

    def _add_weapon(self, p: Player, wid: str) -> int:
        """Pick a weapon card: a new weapon takes a free slot, a known one gains a level."""
        st = next((st for st in p.weapons if st.weapon == wid), None)
        if st is None:
            st = WeaponState(wid)
            p.weapons.append(st)
        else:
            st.level += 1
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
            k = speed * INV_SQRT2 if (mx and my) else speed
            p.vx, p.vy = mx * k, my * k
            p.standing = not (mx or my)
            x, y = self.obstacles.push_out(p.x + p.vx * DT, p.y + p.vy * DT, r)
            p.x = min(max(x, r), cfg.arena_w - r)
            p.y = min(max(y, r), cfg.arena_h - r)
            if p.i_frames > 0:
                p.i_frames = max(0.0, p.i_frames - DT)
            if p.stats.regen_per_s:
                p.hp = min(p.stats.max_hp, p.hp + p.stats.regen_per_s * DT)

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

    def _hurt(self, p: Player, damage: float, events: list[Event], use_i_frames: bool = True) -> None:
        """Damage a player. Hits respect and start i-frames; damage over time does not."""
        if not p.alive or (use_i_frames and p.i_frames > 0):
            return
        dmg = damage * p.stats.damage_taken_mult
        p.hp = max(0.0, p.hp - dmg)
        p.damage_taken += dmg
        if use_i_frames:
            p.i_frames = self.config.character.i_frames_s * p.stats.i_frames_mult
            events.append(PlayerHit(self.tick, p.player_id, dmg, p.hp))
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
        per_wave = cfg.scaling.wave_budget(self.wave, self.difficulty, cfg.player_count)
        # Unspent budget is capped at one wave, so a full arena does not cause a burst later.
        self._budget = min(self._budget + per_wave / wave_ticks, per_wave)
        for _ in range(MAX_SPAWNS_PER_TICK):
            if len(self.enemies) >= cfg.max_alive_enemies:
                return
            x, y = self._spawn_point(alive)
            mob = self._pending_mob or self._pick_mob(biome_at(cfg.biomes, x, y))
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
        t = self.time_s
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
        sc, minutes = self.config.scaling, self.time_s / 60.0
        x, y = self._clamp(*self.obstacles.push_out(x, y, m.radius), m.radius)
        hp = m.hp * sc.hp_mult(minutes)
        dmg = m.damage * sc.damage_mult(minutes) * self.difficulty
        speed = m.speed * sc.speed_mult(minutes)
        e = Enemy(self._next_eid, m.id, x, y, hp, hp, speed, dmg, m.radius, m.xp, m.behavior)
        e.keep_distance, e.shot_interval, e.timer = m.keep_distance, m.shot_interval, m.shot_interval
        self.enemies.append(e)
        events.append(EnemySpawned(self.tick, None, self._next_eid, m.id, biome_at(self.config.biomes, x, y)))
        self._next_eid += 1
        return e

    def _spawn_elite(self, events: list[Event]) -> None:
        alive = [p for p in self.players if p.alive]
        rules = self.config.elite
        if not alive or rules is None:
            return
        x, y = self._spawn_point(alive)
        mob = self._pick_mob(biome_at(self.config.biomes, x, y))
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
        for _ in range(min(rules.affix_count(self.time_s / 60.0), len(pool))):
            affixes.append(pool.pop(self.rng.randint(0, len(pool) - 1)))
        e.affixes = tuple(affixes)
        apply_affixes(e)
        events.append(EliteSpawned(self.tick, None, e.eid, e.kind, e.affixes))

    def _spawn_bosses(self, events: list[Event]) -> None:
        while self._bosses_due and self.time_s >= self._bosses_due[0].spawn_time_s:
            b = self._bosses_due.pop(0)
            p, _ = self._nearest_player(self.config.arena_w / 2, self.config.arena_h / 2)
            if p is None:
                return
            x, y = self._boss_spawn_point(b, p)
            e = Enemy(self._next_eid, b.id, x, y, b.hp, b.hp, b.speed, b.damage, b.radius, 0.0, "boss", boss=b.id)
            self.enemies.append(e)
            self._next_eid += 1
            events.append(BossSpawned(self.tick, None, e.eid, b.id))

    def _boss_spawn_point(self, b: BossStats, p: Player) -> tuple[float, float]:
        """Near the player, preferably in the boss's own biome (the map is too big to make the player walk there).

        Tries the normal spawn ring first, then rings farther out, then gives up on the biome."""
        lo, hi = self.config.spawn_distance
        lo = max(lo, BOSS_MIN_SPAWN_DISTANCE)
        for ring in range(4):
            for _ in range(40):
                dx, dy = self._random_direction()
                dist = self.rng.uniform(lo, hi) * (1.0 + 0.5 * ring)
                x, y = self._clamp(p.x + dx * dist, p.y + dy * dist, b.radius)
                if b.biome is None or biome_at(self.config.biomes, x, y) == b.biome:
                    return self._clamp(*self.obstacles.push_out(x, y, b.radius), b.radius)
        return self._spawn_point([p])

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
        # Separation so enemies form a crowd instead of a single dot.
        g = self._grid
        for e in self.enemies:
            for o in g.query(e.x, e.y, e.radius + self._max_radius):
                if o.eid <= e.eid:
                    continue
                dx, dy = o.x - e.x, o.y - e.y
                d2 = dx * dx + dy * dy
                min_d = e.radius + o.radius
                if 1e-9 < d2 < min_d * min_d:
                    d = math.sqrt(d2)
                    push = (min_d - d) * 0.5 / d
                    e.x -= dx * push
                    e.y -= dy * push
                    o.x += dx * push
                    o.y += dy * push
        obstacles = self.obstacles
        for e in self.enemies:
            e.x, e.y = self._clamp(*obstacles.push_out(e.x, e.y, e.radius), e.radius)

    def _kill(self, e: Enemy, killer: int | None, events: list[Event]) -> None:
        events.append(EnemyKilled(self.tick, killer, e.eid, e.kind, e.x, e.y))
        if e.xp > 0:
            self.orbs.append(XpOrb(e.x, e.y, e.xp * self.reward_mult))
        eco = self.config.economy
        if eco is not None:
            value = eco.boss_value if e.boss else eco.elite_value if e.elite else 0
            if not value and self.rng.random() * 100.0 < eco.drop_pct:
                value = eco.normal_value
            if value:
                self.orbs.append(XpOrb(e.x + 6.0, e.y, float(value), kind="seeds"))
        if e.elite or (not e.boss and self.rng.random() * 100.0 < MAGNET_DROP_PCT):
            self.pickups.append(Pickup("magnet", e.x, e.y))
        for p in self.players:
            if p.player_id == killer:
                p.kills += 1
                if p.stats.heal_per_kill and p.alive:
                    p.hp = min(p.stats.max_hp, p.hp + p.stats.heal_per_kill)
        if e.elite:
            self._drop_chest(e.x, e.y, "elite", events)
            if "volatile" in e.affixes:
                spec = HazardSpec("explosion", VOLATILE_RADIUS, delay=VOLATILE_DELAY_S, burst=e.damage)
                self.add_hazard(spec, e.x, e.y, e.eid)
        if e.boss:
            self.bosses_killed += 1
            events.append(BossKilled(self.tick, killer, e.eid, e.boss, self.time_s))
            self._drop_chest(e.x, e.y, "boss", events)

    def _drop_chest(self, x: float, y: float, kind: str, events: list[Event]) -> None:
        """Elite and boss chests are free and hold at least a rare or epic item (items.json economy)."""
        self.chests.append(MapChest(x, y, kind))
        events.append(ChestDropped(self.tick, None, x, y, kind))

    def _explode(self, e: Enemy, killer: int | None, damage: float, killed: set[int], events: list[Event]) -> None:
        """Item "Samenbombe": a kill bursts and hurts enemies around it (no chain reaction)."""
        r2 = KILL_EXPLOSION_RADIUS**2
        events.append(HazardActivated(self.tick, killer, "seed_burst", e.x, e.y, KILL_EXPLOSION_RADIUS))
        for o in self._grid.query(e.x, e.y, KILL_EXPLOSION_RADIUS + self._max_radius):
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
            p.shot_cooldown += 1.0 / s.attack_rate
            d = math.sqrt(best) or 1.0
            dx, dy = (target.x - p.x) / d, (target.y - p.y) / d
            life = max(1, int(s.range / ch.projectile_speed * TICK_HZ + 0.5))
            damage = s.damage
            if s.far_damage_pct and d > s.far_threshold:  # e.g. Fenn's passive "Weitblick"
                damage *= 1.0 + s.far_damage_pct / 100.0
            if p.standing:  # items like "Tiefe Wurzeln" reward standing still
                damage *= s.standing_damage_mult
            self._fire(p, dx, dy, damage, life, events)
            # Extra attacks fan out alternately left and right of the main shot.
            lx, ly, rx, ry = dx, dy, dx, dy
            for k in range(s.extra_attacks):
                if k % 2 == 0:
                    lx, ly = lx * SPREAD_COS - ly * SPREAD_SIN, lx * SPREAD_SIN + ly * SPREAD_COS
                    self._fire(p, lx, ly, damage * EXTRA_ATTACK_DAMAGE, life, events)
                else:
                    rx, ry = rx * SPREAD_COS + ry * SPREAD_SIN, -rx * SPREAD_SIN + ry * SPREAD_COS
                    self._fire(p, rx, ry, damage * EXTRA_ATTACK_DAMAGE, life, events)

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
              speed: float | None = None, pierce: int | None = None, weapon: str = "") -> None:  # fmt: skip
        s = p.stats
        speed = self.config.character.projectile_speed if speed is None else speed
        dmg, crit = self._roll_crit(p, damage)
        hits = (s.pierce if pierce is None else pierce) + 1
        self.projectiles.append(Projectile(p.player_id, p.x, p.y, dx * speed, dy * speed, dmg, crit, life, hits,
                                           weapon=weapon))  # fmt: skip
        events.append(ShotFired(self.tick, p.player_id, p.x, p.y, dx, dy, weapon))

    def _roll_crit(self, p: Player, damage: float) -> tuple[float, bool]:
        s = p.stats
        crit = self.rng.random() * 100.0 < s.crit_chance_pct
        return damage * (s.crit_mult if crit else 1.0), crit

    def _move_projectiles(self, events: list[Event]) -> None:
        g = self._grid
        reach = PROJECTILE_RADIUS + self._max_radius
        survivors: list[Projectile] = []
        killed: set[int] = set()
        owners = {p.player_id: p for p in self.players}
        for pr in self.projectiles:
            pr.x += pr.vx * DT
            pr.y += pr.vy * DT
            pr.ticks_left -= 1
            if self.obstacles.blocks_point(pr.x, pr.y, PROJECTILE_RADIUS):
                events.append(ProjectileBlocked(self.tick, pr.owner, pr.x, pr.y))
                continue
            for e in g.query(pr.x, pr.y, reach):
                if e.eid in pr.hit_ids or e.eid in killed:
                    continue
                r = e.radius + PROJECTILE_RADIUS
                if (e.x - pr.x) ** 2 + (e.y - pr.y) ** 2 > r * r:
                    continue
                pr.hit_ids.add(e.eid)
                self._weapon_hit(owners.get(pr.owner), pr.owner, e, pr.damage, pr.crit, killed, events)
                pr.hits_left -= 1
                if pr.hits_left <= 0:
                    break
            if pr.ticks_left > 0 and pr.hits_left > 0:
                survivors.append(pr)
        self.projectiles = survivors
        if killed:
            self.enemies = [e for e in self.enemies if e.eid not in killed]
            self._rebuild_grid()

    def _weapon_hit(self, owner: Player | None, owner_id: int, e: Enemy, dmg: float, crit: bool, killed: set[int],
                    events: list[Event]) -> None:  # fmt: skip
        """One hit of any player weapon: elite bonus, armour and shield, kill, "Samenbombe" explosion."""
        if owner is not None and (e.elite or e.boss):
            dmg *= owner.stats.elite_damage_mult
        lost = damage_enemy(e, dmg)
        events.append(EnemyHit(self.tick, owner_id, e.eid, e.x, e.y, lost, crit))
        if e.hp <= 0:
            killed.add(e.eid)
            self._kill(e, owner_id, events)
            if (
                owner is not None
                and owner.stats.explode_on_kill_pct
                and (self.rng.random() * 100.0 < owner.stats.explode_on_kill_pct)
            ):
                self._explode(e, owner_id, dmg * KILL_EXPLOSION_DAMAGE, killed, events)

    # ------------------------------------------------------------------ extra weapons (Paket C2)

    def _use_weapons(self, events: list[Event]) -> None:
        killed: set[int] = set()
        base = self._base_stats
        for p in self.players:
            if not p.alive or not p.weapons:
                continue
            s = p.stats
            damage_mult = s.damage / base.damage * (s.standing_damage_mult if p.standing else 1.0)
            rate_mult = s.attack_rate / base.attack_rate
            for st in p.weapons:
                w = self._weapon_defs[st.weapon]
                v = w.at(st.level)
                v["damage"] *= damage_mult
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
                    if p.stats.thorns and e.hp > 0:  # item "Brennnessel"
                        damage_enemy(e, p.stats.thorns)
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
                if o.kind == "seeds":
                    amount = int(round(o.value * owner.stats.gold_mult))
                    owner.seeds += amount
                    events.append(SeedsCollected(self.tick, owner.player_id, amount))
                elif o.kind == "heal":
                    owner.hp = min(owner.stats.max_hp, owner.hp + o.value)
                else:
                    self._gain_xp(owner, o.value * owner.stats.xp_mult, events)
                continue
            o.x += (owner.x - o.x) / d * step
            o.y += (owner.y - o.y) / d * step
            remaining.append(o)
        self.orbs = remaining

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
        score = compute_score(self.config.score, seconds, p.kills, p.level, self.bosses_killed, self.difficulty)
        return RunResult(
            character=self.config.character.id,
            seed=self.seed,
            seconds=seconds,
            wave=self.wave,
            kills=p.kills,
            level=p.level,
            bosses=self.bosses_killed,
            difficulty=self.difficulty,
            victory=False,
            swarm_seconds=0,
            swarm_mult=1.0,
            damage_taken=p.damage_taken,
            score=score,
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
                    tuple((uid, self.card_levels(p).get(uid, 0)) for uid in p.offer),
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
                )
                for e in self.enemies
            ),  # fmt: skip
            projectiles=tuple(ProjectileView(pr.x, pr.y, pr.crit, pr.weapon) for pr in self.projectiles),
            orbs=tuple(OrbView(o.x, o.y, o.value, o.kind) for o in self.orbs),
            enemy_shots=tuple(EnemyShotView(s.x, s.y, s.lobbed, s.tx, s.ty) for s in self.enemy_shots),
            hazards=tuple(HazardView(h.spec.kind, h.x, h.y, h.spec.radius, h.delay <= 0) for h in self.hazards),
            chests=tuple((c.x, c.y, c.kind) for c in self.chests),
            pots=tuple((pot.x, pot.y) for pot in self.pots),
            chest_price=self.config.economy.chest_price(self.chests_opened) if self.config.economy else 0,
            pickups=tuple((k.kind, k.x, k.y) for k in self.pickups),
            boss_bar=BossBar(boss.boss, boss.hp / boss.max_hp, boss.phase) if boss else None,
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
        return dict(orbiters=tuple(orbiters), auras=tuple(auras), bombs=tuple(bombs))

    def state_hash(self) -> str:
        """Hash over the full simulation state, for determinism tests and later desync detection."""
        h = hashlib.sha256()
        h.update(struct.pack("<qqq?qdd", self.seed, self.tick, self.wave, self.over, self._next_eid, self._budget,
                             self.difficulty))  # fmt: skip
        h.update(struct.pack("<4I", *self.rng.getstate()))
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
        h.update(repr([(p.seeds, sorted(p.items.items()), p.rerolls, p.banishes, sorted(p.banished))
                       for p in self.players]).encode() + struct.pack("<q", self.chests_opened))  # fmt: skip
        h.update(repr([o.kind for o in self.orbs]).encode())
        for k in self.pickups:
            h.update(k.kind.encode() + struct.pack("<2d", k.x, k.y))
        h.update(struct.pack(f"<{len(self.players)}d", *(p.ability_cooldown for p in self.players)))
        h.update(repr([o.magnet_to for o in self.orbs]).encode())
        for p in self.players:
            for st in p.weapons:
                h.update(st.weapon.encode() + struct.pack("<i3d", st.level, st.cooldown, st.ux, st.uy))
                h.update(repr(list(st.hit_ready.items())).encode())
        for b in self.bombs:
            h.update(b.weapon.encode() + struct.pack("<i7d?", b.owner, b.x, b.y, b.tx, b.ty, b.delay, b.radius,
                                                     b.damage, b.crit))  # fmt: skip
        return h.hexdigest()


ABILITIES = {"arrow_storm": World._arrow_storm}
WEAPON_KINDS = {
    "fan": World._weapon_fan,
    "nova": World._weapon_nova,
    "aura": World._weapon_aura,
    "lobbed": World._weapon_lobbed,
}  # "orbit" runs every tick (World._weapon_orbit), not on a cooldown


def _sign(v: int) -> int:
    return -1 if v < 0 else (1 if v > 0 else 0)
